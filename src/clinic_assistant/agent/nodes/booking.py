"""Prepare appointment bookings and handle same-day approval."""

from datetime import datetime

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import Update, configured, conversation_id, reply_update
from clinic_assistant.agent.nodes.slots import OMAN_TIMEZONE
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.domain import ApprovalAction, BookingStatus
from clinic_assistant.repository.bookings import BookingsRepository, SlotTaken

SLOT_UNAVAILABLE = (
    "Sorry, this appointment is no longer available. Please choose another free slot."
)


def is_same_day(starts_at: datetime) -> bool:
    """Compare the appointment date with today's date in Oman."""
    return starts_at.astimezone(OMAN_TIMEZONE).date() == datetime.now(OMAN_TIMEZONE).date()


async def prepare_booking(
    state: ConversationState,
    config: RunnableConfig,
) -> Update:
    """Store a booking and prepare staff approval when required."""
    entities = state["entities"]
    choice = entities["slot_choice"]
    slot_id = state["slots_offered"][choice - 1]

    repository = configured(config, "bookings_repository", BookingsRepository)

    starts_at = await repository.get_slot_start(slot_id)

    if starts_at is None:
        return {"booking_id": None, "pending_action": None}

    status = BookingStatus.PENDING_APPROVAL if is_same_day(starts_at) else BookingStatus.CONFIRMED

    try:
        booking_id = await repository.create(
            slot_id=slot_id,
            conversation_id=conversation_id(config),
            patient_name=entities["patient_name"],
            patient_phone=entities["patient_phone"],
            status=status,
        )
    except SlotTaken:
        return {"booking_id": None, "pending_action": None}

    if status == BookingStatus.PENDING_APPROVAL:
        return {
            "booking_id": booking_id,
            "pending_action": {
                "action": ApprovalAction.BOOK,
                "booking_id": booking_id,
            },
        }

    return {"booking_id": booking_id, "pending_action": None}


async def confirm_booking(state: ConversationState) -> Update:
    """Create the final patient-facing booking response."""
    booking_id = state.get("booking_id")

    if booking_id is None:
        return reply_update(SLOT_UNAVAILABLE)

    return reply_update(f"Your appointment is confirmed. Your booking number is {booking_id}.")
