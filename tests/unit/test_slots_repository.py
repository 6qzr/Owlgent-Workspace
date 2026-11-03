"""Test the free-slots repository without PostgreSQL."""

from datetime import date
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

from clinic_assistant.repository.db import DictPool
from clinic_assistant.repository.slots import SlotsRepository


def make_fake_pool(
    rows: list[dict[str, Any]],
) -> tuple[DictPool, AsyncMock]:
    """Create a fake database pool and cursor."""

    # Fake cursor that returns the provided rows.
    cursor = MagicMock()
    cursor.execute = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=rows)

    # Fake PostgreSQL connection.
    connection = MagicMock()
    connection.cursor.return_value.__aenter__.return_value = cursor

    # Fake connection pool.
    pool = MagicMock()
    pool.connection.return_value.__aenter__.return_value = connection

    return cast(DictPool, pool), cast(AsyncMock, cursor.execute)


async def test_returns_free_slots() -> None:
    """Repository returns the slots supplied by PostgreSQL."""

    expected = [
        {
            "id": 1,
            "doctor_id": 3,
            "doctor_name": "Dr. Sara",
            "specialty": "Dentistry",
        }
    ]

    pool, execute = make_fake_pool(expected)
    repository = SlotsRepository(pool)

    result = await repository.find_free_slots()

    assert result == expected

    # Confirm that the SQL query was executed.
    assert execute.await_args is not None

    # Check that the SQL excludes active bookings.
    sql = execute.await_args.args[0]

    assert "NOT EXISTS" in sql
    assert "pending_approval" in sql
    assert "confirmed" in sql
    assert "CURRENT_TIMESTAMP" in sql


async def test_filter_by_specialty() -> None:
    """Search for a particular specialty."""

    pool, execute = make_fake_pool([])
    repository = SlotsRepository(pool)

    await repository.find_free_slots(specialty="Dentistry")

    # Confirm that the SQL query was executed.
    assert execute.await_args is not None

    sql, params = execute.await_args.args

    assert "d.specialty ILIKE %s" in sql
    assert params == ["Dentistry"]


async def test_filter_by_doctor() -> None:
    """Search for a doctor by ID and name."""

    pool, execute = make_fake_pool([])
    repository = SlotsRepository(pool)

    await repository.find_free_slots(
        doctor_id=3,
        doctor_name="Dr. Sara",
    )

    # Confirm that the SQL query was executed.
    assert execute.await_args is not None

    sql, params = execute.await_args.args

    assert "d.id = %s" in sql
    assert "d.name ILIKE %s" in sql
    assert params == [3, "Dr. Sara"]


async def test_filter_by_date() -> None:
    """Search using the appointment date in Oman."""

    pool, execute = make_fake_pool([])
    repository = SlotsRepository(pool)

    await repository.find_free_slots(booking_date=date(2026, 11, 10))

    # Confirm that the SQL query was executed.
    assert execute.await_args is not None

    sql, params = execute.await_args.args

    assert "Asia/Muscat" in sql
    assert params == [date(2026, 11, 10)]


async def test_no_available_slots() -> None:
    """An empty database result should return an empty list."""

    pool, _ = make_fake_pool([])
    repository = SlotsRepository(pool)

    result = await repository.find_free_slots()

    assert result == []
