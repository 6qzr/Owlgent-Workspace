"""SQL for the conversations table; the conversation service never writes SQL itself."""

import asyncio
from uuid import UUID

from clinic_assistant.repository.db import DictPool

# Covers getting a connection and running the query (AGENTS.md: every DB call has a timeout).
DB_TIMEOUT_SECONDS = 5.0


async def insert_conversation(pool: DictPool, conversation_id: UUID) -> None:
    """Store a new conversation row; other tables reference it by foreign key."""
    async with asyncio.timeout(DB_TIMEOUT_SECONDS), pool.connection() as conn:
        await conn.execute("INSERT INTO conversations (id) VALUES (%s)", (conversation_id,))


async def conversation_exists(pool: DictPool, conversation_id: UUID) -> bool:
    """Tell whether a conversation with this id was ever created."""
    async with asyncio.timeout(DB_TIMEOUT_SECONDS), pool.connection() as conn:
        cursor = await conn.execute("SELECT 1 FROM conversations WHERE id = %s", (conversation_id,))
        return await cursor.fetchone() is not None
