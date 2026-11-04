"""Prepare cancellation of the patient's own booking.

Issue #17: Cancellation always needs staff approval.
"""

from uuid import UUID

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import CLARIFYING, Update, reply_update
from clinic_assistant.agent.nodes.approval import get_repository
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.domain import ApprovalAction

NOT_FOUND = "I couldn't find a booking with that number in this conversation."

MISSING_BOOKING_ID = "Please provide the booking number you want to cancel."


async def prepare_cancel(
    state: ConversationState,
    config: RunnableConfig,
) -> Update:
    """Check ownership before requesting staff approval."""

    # Get the booking number extracted from the patient message.
    booking_id = state.get("entities", {}).get("booking_id")

    # A cancellation needs a booking number.
    if booking_id is None or booking_id <= 0:
        return {
            "pending_action": None,
            **reply_update(MISSING_BOOKING_ID, kind=CLARIFYING),
        }

    # The conversation ID is stored as LangGraph's thread ID.
    thread_id = config.get("configurable", {}).get("thread_id")

    if thread_id is None:
        raise RuntimeError("Conversation thread ID is missing")

    conversation_id = UUID(str(thread_id))

    # Get the repository connected to PostgreSQL.
    repository = get_repository(config)

    # Only find confirmed bookings owned by this conversation.
    booking = await repository.find_cancellable_booking(
        booking_id=booking_id,
        conversation_id=conversation_id,
    )

    # Refuse unknown, cancelled, or other patients' bookings.
    if booking is None:
        return {
            "pending_action": None,
            **reply_update(NOT_FOUND),
        }

    # Do not cancel the booking here.
    # The existing approval workflow must make the decision.
    return {
        "pending_action": {
            "action": ApprovalAction.CANCEL,
            "booking_id": booking_id,
        }
    }
