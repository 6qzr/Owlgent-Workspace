"""SQL for emergency_flags: messages the safety gate flagged for front-desk staff (FR-6)."""

import asyncio
from datetime import datetime
from typing import TypedDict
from uuid import UUID

from clinic_assistant.repository.db import DictPool

# Covers getting a connection and running the query (AGENTS.md: every DB call has a timeout).
DB_TIMEOUT_SECONDS = 5.0


class EmergencyFlag(TypedDict):
    """One flagged message, as staff see it."""

    id: int
    conversation_id: UUID
    message: str
    created_at: datetime


class EmergencyFlagsRepository:
    """Store and list emergency flags on the shared pool."""

    def __init__(self, pool: DictPool) -> None:
        self.pool = pool

    async def insert(self, conversation_id: UUID, message: str) -> int:
        """Store a flag for staff and return its id."""
        async with asyncio.timeout(DB_TIMEOUT_SECONDS), self.pool.connection() as conn:
            cursor = await conn.execute(
                "INSERT INTO emergency_flags (conversation_id, message) "
                "VALUES (%s, %s) RETURNING id",
                (conversation_id, message),
            )
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("emergency flag was not stored")
        return int(row["id"])

    async def list_recent(self, limit: int = 50) -> list[EmergencyFlag]:
        """Newest flags first, so staff see the latest emergency at the top."""
        async with asyncio.timeout(DB_TIMEOUT_SECONDS), self.pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, conversation_id, message, created_at FROM emergency_flags "
                "ORDER BY created_at DESC, id DESC LIMIT %s",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [
            EmergencyFlag(
                id=row["id"],
                conversation_id=row["conversation_id"],
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
