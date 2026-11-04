"""find_cancellable_booking enforces ownership and status in SQL, on a real PostgreSQL (#17)."""

from uuid import uuid4

import pytest

from clinic_assistant.repository.approvals import ApprovalsRepository
from clinic_assistant.repository.db import DictPool

from .conftest import SeededBooking

pytestmark = pytest.mark.integration


async def test_own_confirmed_booking_is_found(
    pool: DictPool, confirmed_booking: SeededBooking
) -> None:
    found = await ApprovalsRepository(pool).find_cancellable_booking(
        confirmed_booking.booking_id, confirmed_booking.conversation_id
    )

    assert found is not None
    assert found["id"] == confirmed_booking.booking_id


async def test_another_conversations_booking_is_not_found(
    pool: DictPool, confirmed_booking: SeededBooking
) -> None:
    repository = ApprovalsRepository(pool)

    assert await repository.find_cancellable_booking(confirmed_booking.booking_id, uuid4()) is None


async def test_a_cancelled_booking_is_not_found(
    pool: DictPool, confirmed_booking: SeededBooking
) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = %s",
            (confirmed_booking.booking_id,),
        )

    found = await ApprovalsRepository(pool).find_cancellable_booking(
        confirmed_booking.booking_id, confirmed_booking.conversation_id
    )

    assert found is None
