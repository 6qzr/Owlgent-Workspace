"""PostgreSQL checkpointer for conversation state (ADR 0001)."""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from clinic_assistant.domain import ApprovalAction, Intent
from clinic_assistant.repository.db import DictPool

# Our own types stored in ConversationState (intent, pending_action.action). Without this list
# LangGraph warns on load, and in strict mode returns them as plain str, so `is Intent.X` checks
# would silently fail after a restart. Add any new enum the state stores here.
CHECKPOINT_TYPES: tuple[type, ...] = (Intent, ApprovalAction)


def checkpoint_serializer() -> JsonPlusSerializer:
    """Restore our enums from checkpoints; refuse any other type LangGraph doesn't mark safe."""
    return JsonPlusSerializer(
        allowed_msgpack_modules=[(t.__module__, t.__name__) for t in CHECKPOINT_TYPES]
    )


async def open_checkpointer(pool: DictPool) -> AsyncPostgresSaver:
    """Wrap the shared pool in AsyncPostgresSaver and create its tables if missing."""
    saver = AsyncPostgresSaver(conn=pool, serde=checkpoint_serializer())
    await saver.setup()
    return saver
