"""Prepare cancellation of the patient's own booking.

Issue #17: Cancellation always needs staff approval.
"""

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import (
    CLARIFYING,
    Update,
    configured,
    conversation_id,
    reply_update,
)
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.domain import ApprovalAction
from clinic_assistant.repository.approvals import ApprovalsRepository

NOT_FOUND = "I couldn't find a booking with that number in this conversation."
MISSING_BOOKING_ID = "Please provide the booking number you want to cancel."


async def prepare_cancel(
    state: ConversationState,
    config: RunnableConfig,
) -> Update:
    """Check booking ownership before requesting staff approval."""

    booking_id = state.get("entities", {}).get("booking_id")

    if booking_id is None or booking_id <= 0:
        return {
            "pending_action": None,
            **reply_update(MISSING_BOOKING_ID, kind=CLARIFYING),
        }

    repository = configured(
        config,
        "approval_repository",
        ApprovalsRepository,
    )

    booking = await repository.find_cancellable_booking(
        booking_id=booking_id,
        conversation_id=conversation_id(config),
    )

    if booking is None:
        return {
            "pending_action": None,
            **reply_update(NOT_FOUND),
        }

    return {
        "pending_action": {
            "action": ApprovalAction.CANCEL,
            "booking_id": booking_id,
        }
    }
