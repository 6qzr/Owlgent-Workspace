"""Prepare appointment bookings and handle same-day approval."""

from datetime import datetime
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.nodes.slots import OMAN_TIMEZONE
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.domain import ApprovalAction, BookingStatus
from clinic_assistant.repository.bookings import BookingsRepository, SlotTaken

SLOT_UNAVAILABLE = (
    "Sorry, this appointment is no longer available. Please choose another free slot."
)


def get_repository(config: RunnableConfig) -> BookingsRepository:
    """Get the bookings repository injected by LangGraph."""

    repository = config.get("configurable", {}).get("bookings_repository")

    if not isinstance(repository, BookingsRepository):
        raise RuntimeError("Bookings repository is not configured")

    return repository


def is_same_day(starts_at: datetime) -> bool:
    """Check whether the appointment is today in Oman."""

    appointment_day = starts_at.astimezone(OMAN_TIMEZONE).date()
    today = datetime.now(OMAN_TIMEZONE).date()

    return appointment_day == today


async def prepare_booking(
    state: ConversationState,
    config: RunnableConfig,
) -> Update:
    """Create a booking and request staff approval when needed."""

    entities = state.get("entities", {})
    offered_slots = state.get("slots_offered", [])

    choice = entities.get("slot_choice")
    patient_name = entities.get("patient_name")
    patient_phone = entities.get("patient_phone")

    # The patient must choose from their offered slots.
    if (
        choice is None
        or not 1 <= choice <= len(offered_slots)
        or not patient_name
        or not patient_phone
    ):
        return {
            "pending_action": None,
            "reply": ("Please choose a slot and provide your name and phone number."),
        }

    # Convert the 1-based choice into the actual database slot ID.
    slot_id = offered_slots[choice - 1]

    thread_id = config.get("configurable", {}).get("thread_id")

    if thread_id is None:
        raise RuntimeError("Conversation thread ID is missing")

    conversation_id = UUID(str(thread_id))
    repository = get_repository(config)

    # Look up the real slot time in PostgreSQL.
    starts_at = await repository.get_slot_start(slot_id)

    if starts_at is None:
        return {
            "pending_action": None,
            "reply": SLOT_UNAVAILABLE,
        }

    # Same-day appointments require staff approval.
    status = BookingStatus.PENDING_APPROVAL if is_same_day(starts_at) else BookingStatus.CONFIRMED

    try:
        booking_id = await repository.create(
            slot_id=slot_id,
            conversation_id=conversation_id,
            patient_name=patient_name,
            patient_phone=patient_phone,
            status=status,
        )

    except SlotTaken:
        # Another patient booked the slot first.
        return {
            "pending_action": None,
            "reply": SLOT_UNAVAILABLE,
        }

    if status == BookingStatus.PENDING_APPROVAL:
        # The existing approval workflow handles the decision.
        return {
            "pending_action": {
                "action": ApprovalAction.BOOK,
                "booking_id": booking_id,
            },
        }

    # Future-day bookings are confirmed immediately.
    return {
        "pending_action": None,
        "reply": (f"Your appointment is confirmed. Your booking number is {booking_id}."),
    }


async def confirm_booking(state: ConversationState) -> Update:
    """Send the result of a future-day booking attempt."""

    return reply_update(state.get("reply", "Your booking request could not be completed."))
