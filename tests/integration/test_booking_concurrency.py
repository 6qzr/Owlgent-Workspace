"""Verify that two patients cannot book the same slot concurrently.

Issue #15: Book a slot without double booking.
Uses a real PostgreSQL database.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from clinic_assistant.domain import BookingStatus
from clinic_assistant.repository.bookings import BookingsRepository, SlotTaken
from clinic_assistant.repository.db import DictPool

pytestmark = pytest.mark.integration


async def test_two_concurrent_bookings_only_one_succeeds(
    pool: DictPool,
) -> None:
    """Only one of two simultaneous bookings can hold a slot."""

    conversation_a = uuid4()
    conversation_b = uuid4()

    doctor_id: int | None = None
    slot_id: int | None = None

    try:
        # -----------------------------------------
        # PART 1: CREATE TEST DATA
        # -----------------------------------------

        async with pool.connection() as conn:
            # Create a doctor for this test.
            cursor = await conn.execute(
                """
                INSERT INTO doctors (name, specialty)
                VALUES (%s, %s)
                RETURNING id
                """,
                (f"Concurrency Doctor {uuid4()}", "Test Specialty"),
            )

            doctor = await cursor.fetchone()
            assert doctor is not None
            doctor_id = int(doctor["id"])

            # Create a future appointment slot.
            start = datetime.now(UTC) + timedelta(days=30)

            cursor = await conn.execute(
                """
                INSERT INTO slots (
                    doctor_id,
                    starts_at,
                    ends_at
                )
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (
                    doctor_id,
                    start,
                    start + timedelta(minutes=30),
                ),
            )

            slot = await cursor.fetchone()
            assert slot is not None
            slot_id = int(slot["id"])

            # Create two separate patient conversations.
            await conn.execute(
                """
                INSERT INTO conversations (id)
                VALUES (%s), (%s)
                """,
                (
                    conversation_a,
                    conversation_b,
                ),
            )

        # -----------------------------------------
        # PART 2: TWO PATIENTS BOOK AT THE SAME TIME
        # -----------------------------------------

        repository = BookingsRepository(pool)

        results = await asyncio.gather(
            repository.create(
                slot_id=slot_id,
                conversation_id=conversation_a,
                patient_name="Patient A",
                patient_phone="90000001",
                status=BookingStatus.CONFIRMED,
            ),
            repository.create(
                slot_id=slot_id,
                conversation_id=conversation_b,
                patient_name="Patient B",
                patient_phone="90000002",
                status=BookingStatus.CONFIRMED,
            ),
            return_exceptions=True,
        )

        # -----------------------------------------
        # PART 3: CHECK RESULTS
        # -----------------------------------------

        # Exactly one request must succeed.
        successes = [result for result in results if type(result) is int]

        # The other request must raise SlotTaken.
        conflicts = [result for result in results if isinstance(result, SlotTaken)]

        assert len(successes) == 1
        assert len(conflicts) == 1

        # Verify PostgreSQL contains exactly one active booking.
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM bookings
                WHERE slot_id = %s
                  AND status IN (
                      'confirmed',
                      'pending_approval'
                  )
                """,
                (slot_id,),
            )

            row = await cursor.fetchone()

        assert row is not None
        assert row["total"] == 1

    finally:
        # -----------------------------------------
        # PART 4: CLEAN UP TEST DATA
        # -----------------------------------------

        async with pool.connection() as conn:
            # Remove the test booking.
            if slot_id is not None:
                await conn.execute(
                    "DELETE FROM bookings WHERE slot_id = %s",
                    (slot_id,),
                )

            # Remove the two test conversations.
            await conn.execute(
                """
                DELETE FROM conversations
                WHERE id IN (%s, %s)
                """,
                (conversation_a, conversation_b),
            )

            # Remove the test slot.
            if slot_id is not None:
                await conn.execute(
                    "DELETE FROM slots WHERE id = %s",
                    (slot_id,),
                )

            # Remove the test doctor.
            if doctor_id is not None:
                await conn.execute(
                    "DELETE FROM doctors WHERE id = %s",
                    (doctor_id,),
                )
