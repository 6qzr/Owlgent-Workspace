"""Unit tests for the bookings repository."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest
from psycopg.errors import UniqueViolation

from clinic_assistant.domain import BookingStatus
from clinic_assistant.repository.bookings import (
    BookingsRepository,
    SlotTaken,
)


def make_repository() -> tuple[BookingsRepository, MagicMock]:
    """Create a repository with a mocked database connection."""

    # Fake database cursor.
    cursor = MagicMock()
    cursor.fetchone = AsyncMock()

    # Fake database connection.
    connection = MagicMock()
    connection.execute = AsyncMock(return_value=cursor)

    # Fake database pool.
    pool = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=connection)

    return BookingsRepository(pool), connection


@pytest.mark.parametrize(
    "status",
    [
        BookingStatus.CONFIRMED,
        BookingStatus.PENDING_APPROVAL,
    ],
)
async def test_create_booking(status: BookingStatus) -> None:
    """Verify a booking is created with the correct status."""

    repository, connection = make_repository()
    conversation_id = uuid4()

    # Simulate PostgreSQL returning a booking ID.
    cursor = connection.execute.return_value
    cursor.fetchone.return_value = {"id": 10}

    result = await repository.create(
        slot_id=5,
        conversation_id=conversation_id,
        patient_name="Sara",
        patient_phone="90000000",
        status=status,
    )

    # Check the returned booking ID.
    assert result == 10

    # Verify the SQL and parameters.
    sql, params = connection.execute.await_args.args

    assert "INSERT INTO bookings" in sql
    assert "RETURNING id" in sql

    assert params == (
        5,
        conversation_id,
        "Sara",
        "90000000",
        status.value,
    )


async def test_slot_already_taken() -> None:
    """Convert duplicate active bookings into SlotTaken."""

    repository, connection = make_repository()

    # Simulate PostgreSQL raising a unique constraint error.
    connection.execute.side_effect = UniqueViolation("duplicate booking")

    with patch.object(
        UniqueViolation,
        "diag",
        new_callable=PropertyMock,
    ) as diag:
        diag.return_value = MagicMock(constraint_name="unique_active_booking_per_slot")

        # The repository must raise SlotTaken.
        with pytest.raises(SlotTaken, match="already booked"):
            await repository.create(
                slot_id=5,
                conversation_id=uuid4(),
                patient_name="Sara",
                patient_phone="90000000",
                status=BookingStatus.CONFIRMED,
            )


async def test_other_unique_violation_is_not_slot_taken() -> None:
    """Preserve unrelated PostgreSQL constraint errors."""

    repository, connection = make_repository()

    connection.execute.side_effect = UniqueViolation("different constraint")

    with patch.object(
        UniqueViolation,
        "diag",
        new_callable=PropertyMock,
    ) as diag:
        diag.return_value = MagicMock(constraint_name="another_unique_constraint")

        # An unrelated constraint should remain a UniqueViolation.
        with pytest.raises(UniqueViolation):
            await repository.create(
                slot_id=5,
                conversation_id=uuid4(),
                patient_name="Sara",
                patient_phone="90000000",
                status=BookingStatus.CONFIRMED,
            )


async def test_missing_returned_booking() -> None:
    """Raise an error when PostgreSQL returns no booking."""

    repository, connection = make_repository()

    # Simulate an insert with no returned row.
    cursor = connection.execute.return_value
    cursor.fetchone.return_value = None

    with pytest.raises(
        RuntimeError,
        match="Could not create booking",
    ):
        await repository.create(
            slot_id=5,
            conversation_id=uuid4(),
            patient_name="Sara",
            patient_phone="90000000",
            status=BookingStatus.CONFIRMED,
        )
