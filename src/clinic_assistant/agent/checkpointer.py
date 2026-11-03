"""PostgreSQL checkpointer for conversation state (ADR 0001)."""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from clinic_assistant.repository.db import DictPool


async def open_checkpointer(pool: DictPool) -> AsyncPostgresSaver:
    """Wrap the shared pool in AsyncPostgresSaver and create its tables if missing."""
    saver = AsyncPostgresSaver(conn=pool)
    await saver.setup()
    return saver
