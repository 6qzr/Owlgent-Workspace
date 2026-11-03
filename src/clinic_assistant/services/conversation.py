"""Conversation use cases: start one, send a message through the graph, read the history.

State lives in the checkpoint under thread_id = conversation_id (ADR 0001). Only the new
message is sent in; nodes bound what reaches the model. Results come from a before/after diff.
"""

import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import psycopg
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.graph import ConversationGraph
from clinic_assistant.agent.nodes import CLARIFYING, reply_kind
from clinic_assistant.domain import Intent
from clinic_assistant.llm import LLMError
from clinic_assistant.repository import conversations
from clinic_assistant.repository.db import DictPool

logger = logging.getLogger(__name__)

ROLE_BY_MESSAGE_TYPE = {"human": "patient", "ai": "assistant"}


class ConversationNotFound(Exception):
    """No conversation with this id was created; the API maps this to 404."""


class AwaitingApproval(Exception):
    """The conversation is paused for a staff decision; the API maps this to 409."""


class DatabaseUnavailable(Exception):
    """PostgreSQL failed or timed out; the API maps this to 503."""


class TurnStatus(StrEnum):
    """Outcome of a turn (docs/architecture.md §4)."""

    ANSWERED = "answered"
    CLARIFYING = "clarifying"
    AWAITING_APPROVAL = "awaiting_approval"
    EMERGENCY = "emergency"


@dataclass(frozen=True)
class TurnResult:
    """What one patient message produced; only values written during this turn."""

    status: TurnStatus
    reply: str | None = None
    sources: list[str] = field(default_factory=list)
    approval_id: int | None = None


@dataclass(frozen=True)
class HistoryMessage:
    """One stored message, labelled by who said it."""

    role: str
    content: str


@dataclass(frozen=True)
class ConversationView:
    """The full stored history of a conversation and its current status."""

    messages: list[HistoryMessage]
    status: TurnStatus


def thread_config(conversation_id: UUID) -> RunnableConfig:
    """Checkpointer config: one LangGraph thread per conversation."""
    return {"configurable": {"thread_id": str(conversation_id)}}


def turn_status(
    state: Mapping[str, Any], paused: bool, reply: BaseMessage | None = None
) -> TurnStatus:
    """Derive the status from the state, the pause, and the kind marked on this turn's reply.

    Order matters: a pause or an emergency outranks a clarifying question.
    """
    if paused:
        return TurnStatus.AWAITING_APPROVAL
    if state.get("emergency") or state.get("intent") == Intent.EMERGENCY:
        return TurnStatus.EMERGENCY
    if reply is not None and reply_kind(reply) == CLARIFYING:
        return TurnStatus.CLARIFYING
    return TurnStatus.ANSWERED


def changed[T](before: Mapping[str, Any], after: Mapping[str, Any], key: str, empty: T) -> T:
    """Return the field's value if this turn changed it, else `empty`."""
    value = after.get(key, empty)
    return empty if value == before.get(key, empty) else value


def new_reply_message(before: Mapping[str, Any], after: Mapping[str, Any]) -> AIMessage | None:
    """The last assistant message added during this turn, if any."""
    added = after.get("messages", [])[len(before.get("messages", [])) :]
    replies = [message for message in added if isinstance(message, AIMessage)]
    return replies[-1] if replies else None


def new_reply(before: Mapping[str, Any], after: Mapping[str, Any]) -> str | None:
    """Text of the last assistant message added during this turn, if any."""
    message = new_reply_message(before, after)
    return message.text if message is not None else None


def last_reply_message(messages: Sequence[AnyMessage]) -> AIMessage | None:
    """The newest assistant message in a stored history, if any."""
    return next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)


def turn_result(before: Mapping[str, Any], after: Mapping[str, Any], paused: bool) -> TurnResult:
    """Build the turn result from the state diff, so stale fields never leak."""
    return TurnResult(
        status=turn_status(after, paused, new_reply_message(before, after)),
        reply=new_reply(before, after),
        sources=changed(before, after, "sources", []),
        approval_id=changed(before, after, "approval_id", None),
    )


def to_history(messages: Sequence[AnyMessage]) -> list[HistoryMessage]:
    """Label stored messages as patient or assistant for the API."""
    return [
        HistoryMessage(role=ROLE_BY_MESSAGE_TYPE.get(m.type, m.type), content=m.text)
        for m in messages
    ]


@asynccontextmanager
async def database_errors(action: str, conversation_id: UUID | None = None) -> AsyncIterator[None]:
    """Turn PostgreSQL failures and timeouts into DatabaseUnavailable plus a log line."""
    try:
        yield
    except (psycopg.Error, TimeoutError) as exc:
        logger.error("Database failed to %s (conversation %s): %r", action, conversation_id, exc)
        raise DatabaseUnavailable(f"Database unavailable while trying to {action}") from exc


class ConversationService:
    """Use cases behind the conversation routes; built per request from app.state.runtime."""

    def __init__(self, graph: ConversationGraph, pool: DictPool) -> None:
        self._graph = graph
        self._pool = pool

    async def create_conversation(self) -> UUID:
        """Create a conversation with a server-generated UUID."""
        conversation_id = uuid4()
        async with database_errors("create a conversation", conversation_id):
            await conversations.insert_conversation(self._pool, conversation_id)
        return conversation_id

    async def send_message(self, conversation_id: UUID, text: str) -> TurnResult:
        """Run one patient message through the graph and report what this turn produced."""
        config = thread_config(conversation_id)
        async with database_errors("load the conversation", conversation_id):
            await self._require(conversation_id)
            before = await self._graph.aget_state(config)
        if before.next:
            raise AwaitingApproval(f"Conversation {conversation_id} is waiting for staff")
        try:
            async with database_errors("save the conversation", conversation_id):
                await self._graph.ainvoke({"messages": [HumanMessage(text)]}, config)
                after = await self._graph.aget_state(config)
        except LLMError as exc:
            logger.error("LLM failed in conversation %s: %s", conversation_id, exc)
            raise
        return turn_result(before.values, after.values, paused=bool(after.next))

    async def get_conversation(self, conversation_id: UUID) -> ConversationView:
        """Return the full stored history; it is never trimmed."""
        async with database_errors("read the conversation", conversation_id):
            await self._require(conversation_id)
            snapshot = await self._graph.aget_state(thread_config(conversation_id))
        messages = snapshot.values.get("messages", [])
        return ConversationView(
            messages=to_history(messages),
            status=turn_status(snapshot.values, bool(snapshot.next), last_reply_message(messages)),
        )

    async def _require(self, conversation_id: UUID) -> None:
        """Raise ConversationNotFound unless the conversation row exists."""
        if not await conversations.conversation_exists(self._pool, conversation_id):
            raise ConversationNotFound(f"Conversation {conversation_id} not found")
