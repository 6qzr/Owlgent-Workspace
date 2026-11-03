"""Test Issue #14: finding free appointment slots."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes.slots import find_slots
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.repository.slots import SlotsRepository


def make_repository() -> MagicMock:
    """Create a fake repository without PostgreSQL."""

    repository = MagicMock(spec=SlotsRepository)

    # Simulate the async database method.
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

    # Simulate a free appointment returned by PostgreSQL.
    repository.find_free_slots.return_value = [
        {
            "id": 1,
            "doctor_name": "Dr. Sara",
            "specialty": "Dentistry",
            "starts_at": datetime(2026, 11, 10, 8, 0, tzinfo=UTC),
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


async def test_find_slots_no_results() -> None:
    """Show a friendly message when no slots exist."""

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
    """Ask for a valid date when the input is incorrect."""

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
    assert "YYYY-MM-DD" in result["reply"]

    repository.find_free_slots.assert_not_awaited()
