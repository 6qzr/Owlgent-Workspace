"""Staff approval workflow for Issue #16."""

from typing import cast

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from clinic_assistant.agent.nodes import Update, configured, conversation_id, reply_update
from clinic_assistant.agent.state import ConversationState, Decision
from clinic_assistant.repository.approvals import ApprovalsRepository


async def record_approval(
    state: ConversationState,
    config: RunnableConfig,
) -> Update:
    """Save the approval before the graph pauses."""

    # Get the pending booking or cancellation.
    pending_action = state.get("pending_action")
    if pending_action is None:
        raise RuntimeError("record_approval needs pending_action from prepare_booking/cancel")

    repository = configured(config, "approval_repository", ApprovalsRepository)
    approval_id = await repository.create(
        conversation_id=conversation_id(config),
        booking_id=pending_action["booking_id"],
        action=pending_action["action"],
    )

    # Store the approval ID in the graph state.
    return {"approval_id": approval_id}


async def await_staff(state: ConversationState) -> Update:
    """Pause the workflow until staff makes a decision."""

    # Only interrupt here. Never write to the database.
    result = interrupt(
        {
            "approval_id": state["approval_id"],
            "message": "Waiting for staff approval",
        }
    )

    # Validate the resumed decision.
    if not isinstance(result, dict):
        raise ValueError("Invalid staff decision")

    if (
        not isinstance(result.get("approved"), bool)
        or not isinstance(result.get("reason"), str)
        or not isinstance(result.get("staff"), str)
        or not result["reason"].strip()
        or not result["staff"].strip()
    ):
        raise ValueError("Invalid staff decision")

    return {"decision": cast(Decision, result)}


async def apply_decision(
    state: ConversationState,
    config: RunnableConfig,
) -> Update:
    """Apply the staff decision to the database."""

    # Get the approval and staff decision.
    approval_id = state["approval_id"]
    decision = state["decision"]

    repository = configured(config, "approval_repository", ApprovalsRepository)

    # Update the approval and booking together.
    await repository.decide(
        approval_id=approval_id,
        approved=decision["approved"],
        reason=decision["reason"],
        staff=decision["staff"],
    )

    return {}


async def notify_outcome(state: ConversationState) -> Update:
    """Tell the patient what staff decided."""

    decision = state["decision"]

    if decision["approved"]:
        reply = "Your request was approved."
    else:
        reply = f"Your request was rejected: {decision['reason']}"

    return reply_update(reply)
