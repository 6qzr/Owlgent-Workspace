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
    """Create a mocked bookings repository."""
    repository = MagicMock(spec=BookingsRepository)
    repository.get_slot_start = AsyncMock(return_value=starts_at)
    repository.create = AsyncMock(return_value=101)
    return repository


def make_state() -> ConversationState:
    """Create a valid patient booking request."""
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
    """Create LangGraph configuration for testing."""
    return {
        "configurable": {
            "bookings_repository": repository,
            "thread_id": str(uuid4()),
        }
    }


async def test_future_booking_confirmed() -> None:
    """Future-day bookings are confirmed immediately."""
    future = datetime.now(OMAN_TIMEZONE) + timedelta(days=2)
    repository = make_repository(future)

    result = await prepare_booking(
        make_state(),
        make_config(repository),
    )

    assert result["booking_id"] == 101
    assert result["pending_action"] is None
    assert "reply" not in result

    repository.get_slot_start.assert_awaited_once_with(20)
    assert repository.create.await_args.kwargs["slot_id"] == 20
    assert repository.create.await_args.kwargs["status"] == BookingStatus.CONFIRMED

    final_reply = await confirm_booking({"messages": [], "booking_id": result["booking_id"]})

    assert "confirmed" in final_reply["reply"].lower()
    assert "101" in final_reply["reply"]


async def test_same_day_booking_needs_approval() -> None:
    """Same-day booking is held for staff approval."""
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

    assert result["booking_id"] == 101

    assert result["pending_action"] == {
        "action": ApprovalAction.BOOK,
        "booking_id": 101,
    }

    assert repository.create.await_args.kwargs["status"] == BookingStatus.PENDING_APPROVAL


async def test_slot_no_longer_available() -> None:
    """Reject missing or expired appointment slots."""
    repository = make_repository(datetime.now(OMAN_TIMEZONE))
    repository.get_slot_start.return_value = None

    result = await prepare_booking(
        make_state(),
        make_config(repository),
    )

    assert result["booking_id"] is None
    assert result["pending_action"] is None
    assert "reply" not in result

    repository.create.assert_not_awaited()

    final_reply = await confirm_booking({"messages": [], "booking_id": result["booking_id"]})

    assert final_reply["reply"] == SLOT_UNAVAILABLE


async def test_slot_taken() -> None:
    """Handle a slot booked by another patient."""
    future = datetime.now(OMAN_TIMEZONE) + timedelta(days=2)
    repository = make_repository(future)

    repository.create.side_effect = SlotTaken("Slot already booked")

    result = await prepare_booking(
        make_state(),
        make_config(repository),
    )

    assert result["booking_id"] is None
    assert result["pending_action"] is None
    assert "reply" not in result

    final_reply = await confirm_booking({"messages": [], "booking_id": result["booking_id"]})

    assert final_reply["reply"] == SLOT_UNAVAILABLE


async def test_confirm_booking_reply() -> None:
    """The final node creates the confirmation response."""
    state: ConversationState = {
        "messages": [],
        "booking_id": 101,
    }

    result = await confirm_booking(state)

    assert result["reply"] == ("Your appointment is confirmed. Your booking number is 101.")
    assert result["messages"][0].content == result["reply"]


async def test_confirm_booking_unavailable() -> None:
    """The final node reports an unavailable slot."""
    state: ConversationState = {
        "messages": [],
        "booking_id": None,
    }

    result = await confirm_booking(state)

    assert result["reply"] == SLOT_UNAVAILABLE
    assert result["messages"][0].content == SLOT_UNAVAILABLE


def test_same_day_uses_oman_date() -> None:
    """Compare appointment dates using the Oman timezone."""
    today = datetime.now(OMAN_TIMEZONE).date()

    same_day = datetime(
        today.year,
        today.month,
        today.day,
        12,
        tzinfo=OMAN_TIMEZONE,
    )

    next_day = same_day + timedelta(days=1)

    assert is_same_day(same_day)
    assert not is_same_day(next_day)
