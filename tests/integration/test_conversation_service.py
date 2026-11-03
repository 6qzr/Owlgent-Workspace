"""The conversation service against real PostgreSQL: rows, checkpoints and error mapping."""

from uuid import uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from clinic_assistant.agent.checkpointer import open_checkpointer
from clinic_assistant.agent.graph import ConversationGraph, build_graph
from clinic_assistant.agent.nodes import Update
from clinic_assistant.agent.nodes.classify import Classification
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.config import Settings
from clinic_assistant.domain import Intent
from clinic_assistant.llm import FakeLLM, LLMError
from clinic_assistant.repository import conversations
from clinic_assistant.repository.db import DictPool, create_pool
from clinic_assistant.services.conversation import (
    AwaitingApproval,
    ConversationNotFound,
    ConversationService,
    ConversationView,
    DatabaseUnavailable,
    TurnStatus,
)

pytestmark = pytest.mark.integration

OTHER = Classification(intent=Intent.OTHER, confidence=0.9)


@pytest.fixture
async def saver(pool: DictPool) -> AsyncPostgresSaver:
    return await open_checkpointer(pool)


# A tiny graph that always stops at await_staff, like the approval branch.
def paused_graph(saver: AsyncPostgresSaver) -> ConversationGraph:
    async def await_staff(state: ConversationState) -> Update:
        interrupt({"approval_id": 1})
        return {}

    builder = StateGraph(ConversationState)
    builder.add_node("await_staff", await_staff)
    builder.add_edge(START, "await_staff")
    builder.add_edge("await_staff", END)
    return builder.compile(checkpointer=saver)


async def test_created_conversation_is_stored_and_empty(
    pool: DictPool, saver: AsyncPostgresSaver
) -> None:
    service = ConversationService(build_graph(FakeLLM(), saver), pool)

    conversation_id = await service.create_conversation()

    assert await conversations.conversation_exists(pool, conversation_id)
    assert await service.get_conversation(conversation_id) == ConversationView(
        [], TurnStatus.ANSWERED
    )


async def test_unknown_conversation_is_not_found(pool: DictPool, saver: AsyncPostgresSaver) -> None:
    service = ConversationService(build_graph(FakeLLM(), saver), pool)

    with pytest.raises(ConversationNotFound):
        await service.send_message(uuid4(), "Hello")
    with pytest.raises(ConversationNotFound):
        await service.get_conversation(uuid4())


async def test_history_grows_across_turns(pool: DictPool, saver: AsyncPostgresSaver) -> None:
    llm = FakeLLM([OTHER, OTHER])
    service = ConversationService(build_graph(llm, saver), pool)
    conversation_id = await service.create_conversation()

    first = await service.send_message(conversation_id, "Hello")
    second = await service.send_message(conversation_id, "Are you there?")

    assert first.reply and second.reply
    assert second.status is TurnStatus.ANSWERED
    assert len(llm.calls[1]) == 1 + 3  # system prompt + both patient turns and one reply
    view = await service.get_conversation(conversation_id)
    assert [m.role for m in view.messages] == ["patient", "assistant"] * 2


async def test_paused_conversation_refuses_new_messages(
    pool: DictPool, saver: AsyncPostgresSaver
) -> None:
    service = ConversationService(paused_graph(saver), pool)
    conversation_id = await service.create_conversation()

    result = await service.send_message(conversation_id, "Cancel booking 7")

    assert result.status is TurnStatus.AWAITING_APPROVAL
    assert result.reply is None
    with pytest.raises(AwaitingApproval):
        await service.send_message(conversation_id, "Any news?")
    assert (await service.get_conversation(conversation_id)).status is TurnStatus.AWAITING_APPROVAL


async def test_llm_failure_is_raised_as_llm_error(
    pool: DictPool, saver: AsyncPostgresSaver
) -> None:
    service = ConversationService(build_graph(FakeLLM([LLMError("down")]), saver), pool)
    conversation_id = await service.create_conversation()

    with pytest.raises(LLMError):
        await service.send_message(conversation_id, "Hello")


async def test_database_failure_is_database_unavailable(settings: Settings) -> None:
    closed_pool = create_pool(settings)  # never opened, so every query fails
    service = ConversationService(build_graph(FakeLLM()), closed_pool)

    with pytest.raises(DatabaseUnavailable):
        await service.create_conversation()
