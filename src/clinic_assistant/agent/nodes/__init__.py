"""Graph nodes, one module per slice; each owner replaces the stub body in their own file."""

from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig

type Update = dict[str, Any]

# Stored on the reply message itself, so it belongs to exactly one turn and never goes stale.
# response_metadata is kept in the checkpoint but never sent to the model.
REPLY_KIND = "reply_kind"
CLARIFYING = "clarifying"


def reply_update(text: str, kind: str | None = None) -> Update:
    """Update for a node that ends the turn: the reply text, also appended to the history.

    `kind` marks special replies (e.g. CLARIFYING) so the service can report the turn's status.
    """
    metadata = {REPLY_KIND: kind} if kind else {}
    return {"reply": text, "messages": [AIMessage(text, response_metadata=metadata)]}


def configured[T](config: RunnableConfig, key: str, kind: type[T]) -> T:
    """The object graph.py injected under `key`; a missing or wrong one is a wiring bug."""
    value = config.get("configurable", {}).get(key)
    if not isinstance(value, kind):
        raise RuntimeError(f"{key} is not configured")
    return value


def conversation_id(config: RunnableConfig) -> UUID:
    """This run's conversation: the graph thread id is the conversation id (ADR 0001)."""
    thread_id = config.get("configurable", {}).get("thread_id")
    if thread_id is None:
        raise RuntimeError("Conversation thread ID is missing")
    return UUID(str(thread_id))


def reply_kind(message: BaseMessage) -> str | None:
    """The kind a node attached to its reply, or None for an ordinary answer."""
    kind = message.response_metadata.get(REPLY_KIND)
    return kind if isinstance(kind, str) else None
