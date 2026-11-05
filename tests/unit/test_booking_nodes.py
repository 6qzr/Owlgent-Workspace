"""Unit tests for Issue #15 booking nodes."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes.booking import (
    SLOT_UNAVAILABLE,
    confirm_booking,
    is_same_day,
    prepare_booking,
)
from clinic_assistant.agent.nodes.slots import OMAN_TIMEZONE
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.domain import ApprovalAction, BookingStatus
from clinic_assistant.repository.bookings import BookingsRepository, SlotTaken


def make_repository(starts_at: datetime) -> MagicMock:
    """Create a mocked booking repository."""
    repository = MagicMock(spec=BookingsRepository)
    repository.get_slot_start = AsyncMock(return_value=starts_at)
    repository.create = AsyncMock(return_value=101)
    return repository


def make_state() -> ConversationState:
    """Create a patient request for the second offered slot."""
    return {
        "messages": [],
        "slots_offered": [10, 20],
        "entities": {
            "slot_choice": 2,
            "patient_name": "Sara",
            "patient_phone": "90000000",
        },
    }


def make_config(repository: MagicMock) -> RunnableConfig:
    """Inject the repository and conversation ID."""
    return {
        "configurable": {
            "bookings_repository": repository,
            "thread_id": str(uuid4()),
        }
    }


async def test_future_booking_confirmed() -> None:
    """Future-day bookings should be confirmed immediately."""
    future = datetime.now(OMAN_TIMEZONE) + timedelta(days=2)
    repository = make_repository(future)
    config = make_config(repository)

    result = await prepare_booking(make_state(), config)

    assert result["pending_action"] is None
    assert "confirmed" in result["reply"].lower()
    assert "101" in result["reply"]

    repository.get_slot_start.assert_awaited_once_with(20)

    assert repository.create.await_args.kwargs["status"] == BookingStatus.CONFIRMED
    assert repository.create.await_args.kwargs["slot_id"] == 20


async def test_same_day_booking_needs_approval() -> None:
    """A same-day booking must wait for staff approval."""
    today = datetime.now(OMAN_TIMEZONE).date()
    starts_at = datetime(
        today.year,
        today.month,
        today.day,
        12,
        0,
        tzinfo=OMAN_TIMEZONE,
    )
    repository = make_repository(starts_at)

    result = await prepare_booking(
        make_state(),
        make_config(repository),
    )

    assert result["pending_action"] == {
        "action": ApprovalAction.BOOK,
        "booking_id": 101,
    }

    assert repository.create.await_args.kwargs["status"] == BookingStatus.PENDING_APPROVAL


async def test_invalid_slot_choice() -> None:
    """A patient cannot choose a slot outside the offered list."""
    repository = make_repository(datetime.now(OMAN_TIMEZONE) + timedelta(days=2))
    state = make_state()
    state["entities"]["slot_choice"] = 3

    result = await prepare_booking(
        state,
        make_config(repository),
    )

    assert result["pending_action"] is None
    assert "choose a slot" in result["reply"].lower()
    repository.create.assert_not_awaited()


async def test_slot_no_longer_available() -> None:
    """Reject a missing or expired appointment."""
    repository = make_repository(datetime.now(OMAN_TIMEZONE))
    repository.get_slot_start.return_value = None

    result = await prepare_booking(
        make_state(),
        make_config(repository),
    )

    assert result["pending_action"] is None
    assert result["reply"] == SLOT_UNAVAILABLE
    repository.create.assert_not_awaited()


async def test_slot_taken() -> None:
    """Tell the patient if another booking took the slot."""
    future = datetime.now(OMAN_TIMEZONE) + timedelta(days=2)
    repository = make_repository(future)
    repository.create.side_effect = SlotTaken("Slot already booked")

    result = await prepare_booking(
        make_state(),
        make_config(repository),
    )

    assert result["pending_action"] is None
    assert result["reply"] == SLOT_UNAVAILABLE


async def test_confirm_booking_reply() -> None:
    """Confirm the booking with a patient-facing message."""
    state: ConversationState = {
        "messages": [],
        "reply": "Your appointment is confirmed. Your booking number is 101.",
    }

    result = await confirm_booking(state)

    assert "confirmed" in result["reply"]
    assert result["messages"][0].content == result["reply"]


def test_same_day_uses_oman_date() -> None:
    """Compare the appointment date in Oman, not UTC."""
    today = datetime.now(OMAN_TIMEZONE).date()

    same_day = datetime(today.year, today.month, today.day, 12, tzinfo=OMAN_TIMEZONE)
    next_day = same_day + timedelta(days=1)

    assert is_same_day(same_day)
    assert not is_same_day(next_day)
