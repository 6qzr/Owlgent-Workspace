"""find_cancellable_booking enforces ownership and status in SQL, on a real PostgreSQL (#17)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from clinic_assistant.repository.approvals import ApprovalsRepository
from clinic_assistant.repository.db import DictPool

pytestmark = pytest.mark.integration


@pytest.fixture
async def booking(pool: DictPool) -> AsyncIterator[tuple[int, UUID]]:
    """A confirmed booking on its own doctor and slot; removed after the test."""
    owner = uuid4()
    starts_at = datetime.now(UTC) + timedelta(days=30)
    async with pool.connection() as conn:
        await conn.execute("INSERT INTO conversations (id) VALUES (%s)", (owner,))
        cur = await conn.execute(
            "INSERT INTO doctors (name, specialty) VALUES (%s, 'Test') RETURNING id",
            (f"Ownership Test Doctor {owner}",),
        )
        doctor = await cur.fetchone()
        assert doctor is not None
        cur = await conn.execute(
            "INSERT INTO slots (doctor_id, starts_at, ends_at) VALUES (%s, %s, %s) RETURNING id",
            (doctor["id"], starts_at, starts_at + timedelta(minutes=30)),
        )
        slot = await cur.fetchone()
        assert slot is not None
        cur = await conn.execute(
            "INSERT INTO bookings (slot_id, conversation_id, patient_name, patient_phone, status)"
            " VALUES (%s, %s, 'Sara Ali', '91234567', 'confirmed') RETURNING id",
            (slot["id"], owner),
        )
        row = await cur.fetchone()
        assert row is not None
    try:
        yield row["id"], owner
    finally:
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("DELETE FROM bookings WHERE id = %s", (row["id"],))
            await conn.execute("DELETE FROM slots WHERE id = %s", (slot["id"],))
            await conn.execute("DELETE FROM doctors WHERE id = %s", (doctor["id"],))
            await conn.execute("DELETE FROM conversations WHERE id = %s", (owner,))


async def test_own_confirmed_booking_is_found(pool: DictPool, booking: tuple[int, UUID]) -> None:
    booking_id, owner = booking

    found = await ApprovalsRepository(pool).find_cancellable_booking(booking_id, owner)

    assert found is not None
    assert found["id"] == booking_id


async def test_another_conversations_booking_is_not_found(
    pool: DictPool, booking: tuple[int, UUID]
) -> None:
    booking_id, _ = booking

    assert await ApprovalsRepository(pool).find_cancellable_booking(booking_id, uuid4()) is None


async def test_a_cancelled_booking_is_not_found(pool: DictPool, booking: tuple[int, UUID]) -> None:
    booking_id, owner = booking
    async with pool.connection() as conn:
        await conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = %s", (booking_id,))

    assert await ApprovalsRepository(pool).find_cancellable_booking(booking_id, owner) is None
