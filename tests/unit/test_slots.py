"""Test Issue #14: finding free appointment slots."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes.slots import (
    OMAN_TIMEZONE,
    find_slots,
    parse_booking_day,
)
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.repository.slots import SlotsRepository


def make_repository() -> MagicMock:
    """Create a fake repository without PostgreSQL."""

    # Create a fake repository with the same methods.
    repository = MagicMock(spec=SlotsRepository)

    # Return no slots by default.
    repository.find_free_slots = AsyncMock(return_value=[])

    return repository


def make_config(repository: MagicMock) -> RunnableConfig:
    """Give the node its fake repository."""

    return {
        "configurable": {
            "slots_repository": repository,
        }
    }


async def test_find_slots_success() -> None:
    """The patient should receive available appointments."""

    repository = make_repository()

    # Simulate a free appointment from the database.
    repository.find_free_slots.return_value = [
        {
            "id": 1,
            "doctor_name": "Dr. Sara",
            "specialty": "Dentistry",
            "starts_at": datetime(
                2026,
                11,
                10,
                8,
                0,
                tzinfo=UTC,
            ),
        }
    ]

    state: ConversationState = {
        "messages": [],
        "entities": {
            "specialty": "Dentistry",
            "booking_day": "2026-11-10",
        },
    }

    result = await find_slots(state, make_config(repository))

    assert result["slots_offered"] == [1]
    assert "Dr. Sara" in result["reply"]
    assert "Dentistry" in result["reply"]

    repository.find_free_slots.assert_awaited_once()


async def test_offered_slots_are_numbered_in_booking_order() -> None:
    """Number N in the reply is slots_offered[N - 1], which is what the patient books by."""
    repository = make_repository()
    start = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
    repository.find_free_slots.return_value = [
        {"id": 7, "doctor_name": "Dr. Sara", "specialty": "Dentistry", "starts_at": start},
        {"id": 3, "doctor_name": "Dr. Ali", "specialty": "Dentistry", "starts_at": start},
    ]
    state: ConversationState = {"messages": [], "entities": {"specialty": "Dentistry"}}

    result = await find_slots(state, make_config(repository))

    assert result["slots_offered"] == [7, 3]
    assert "1. Dr. Sara" in result["reply"]
    assert "2. Dr. Ali" in result["reply"]
    assert "reply with the number" in result["reply"]


async def test_find_slots_no_results() -> None:
    """Show a friendly reply when no slots are available."""

    repository = make_repository()

    state: ConversationState = {
        "messages": [],
        "entities": {
            "specialty": "Dentistry",
        },
    }

    result = await find_slots(state, make_config(repository))

    assert result["slots_offered"] == []
    assert "no free appointments" in result["reply"].lower()

    repository.find_free_slots.assert_awaited_once()


async def test_find_slots_missing_specialty() -> None:
    """Ask the patient to choose a doctor or specialty."""

    repository = make_repository()

    state: ConversationState = {
        "messages": [],
        "entities": {},
    }

    result = await find_slots(state, make_config(repository))

    assert result["slots_offered"] == []
    assert "doctor or specialty" in result["reply"].lower()

    repository.find_free_slots.assert_not_awaited()


async def test_find_slots_invalid_date() -> None:
    """Ask the patient for a valid date."""

    repository = make_repository()

    state: ConversationState = {
        "messages": [],
        "entities": {
            "specialty": "Dentistry",
            "booking_day": "wrong-date",
        },
    }

    result = await find_slots(state, make_config(repository))

    assert result["slots_offered"] == []
    assert "valid date" in result["reply"]

    repository.find_free_slots.assert_not_awaited()


def test_parse_booking_day_weekdays() -> None:
    """Convert weekday names to their next matching date."""

    # Get today's date in Oman.
    today = datetime.now(OMAN_TIMEZONE).date()

    weekdays = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    # Test every weekday.
    for weekday in weekdays:
        result = parse_booking_day(weekday)

        assert result is not None

        # Result must match the requested weekday.
        assert result.strftime("%A") == weekday

        # Result must be within the next seven days.
        assert today <= result <= today + timedelta(days=6)

    # If the patient says today's weekday, return today.
    assert parse_booking_day(today.strftime("%A")) == today


async def test_find_slots_with_weekday() -> None:
    """Search for appointments using a weekday name."""

    repository = make_repository()

    state: ConversationState = {
        "messages": [],
        "entities": {
            "specialty": "Dentistry",
            "booking_day": "Thursday",
        },
    }

    await find_slots(state, make_config(repository))

    # Check that the repository receives the correct date.
    expected_date = parse_booking_day("Thursday")

    repository.find_free_slots.assert_awaited_once_with(
        doctor_name=None,
        specialty="Dentistry",
        booking_date=expected_date,
    )
