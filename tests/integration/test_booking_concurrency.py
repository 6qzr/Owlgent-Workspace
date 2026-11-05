"""Verify that two patients cannot book the same slot concurrently.

Issue #15: Book a slot without double booking.
Uses a real PostgreSQL database.
"""

import asyncio
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from clinic_assistant.domain import BookingStatus
from clinic_assistant.repository.bookings import BookingsRepository, SlotTaken
from clinic_assistant.repository.db import DictPool

if TYPE_CHECKING:
    from .conftest import FreeSlot

pytestmark = pytest.mark.integration


async def test_two_concurrent_bookings_only_one_succeeds(
    pool: DictPool,
    free_slot: FreeSlot,
) -> None:
    """Exactly one patient can reserve a slot."""
    conversation_a = uuid4()
    conversation_b = uuid4()

    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO conversations (id)
            VALUES (%s), (%s)
            """,
            (conversation_a, conversation_b),
        )

    try:
        repository = BookingsRepository(pool)

        results = await asyncio.gather(
            repository.create(
                slot_id=free_slot.slot_id,
                conversation_id=conversation_a,
                patient_name="Patient A",
                patient_phone="90000001",
                status=BookingStatus.CONFIRMED,
            ),
            repository.create(
                slot_id=free_slot.slot_id,
                conversation_id=conversation_b,
                patient_name="Patient B",
                patient_phone="90000002",
                status=BookingStatus.CONFIRMED,
            ),
            return_exceptions=True,
        )

        successes = [result for result in results if type(result) is int]
        conflicts = [result for result in results if isinstance(result, SlotTaken)]

        assert len(successes) == 1
        assert len(conflicts) == 1

        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM bookings
                WHERE slot_id = %s
                  AND status IN ('confirmed', 'pending_approval')
                """,
                (free_slot.slot_id,),
            )
            row = await cursor.fetchone()

        assert row is not None
        assert row["total"] == 1

    finally:
        async with pool.connection() as conn, conn.transaction():
            await conn.execute(
                "DELETE FROM bookings WHERE slot_id = %s",
                (free_slot.slot_id,),
            )
            await conn.execute(
                """
                DELETE FROM conversations
                WHERE id IN (%s, %s)
                """,
                (conversation_a, conversation_b),
            )
