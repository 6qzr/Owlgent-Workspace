"""Staff approval: record, pause with interrupt(), then apply the decision (ADR 0002).

Owner: @baraah34 (#16). Stubs from the graph skeleton: replace the bodies, keep the names.
Rule: await_staff only calls interrupt(); it re-runs from the top on resume, so no writes there.
"""

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState


async def record_approval(state: ConversationState) -> Update:
    """Insert the approvals row and remember its id."""
    return {}


async def await_staff(state: ConversationState) -> Update:
    """Pause the graph until staff decide."""
    return {}


async def apply_decision(state: ConversationState) -> Update:
    """Confirm or cancel the booking according to the staff decision."""
    return {}


async def notify_outcome(state: ConversationState) -> Update:
    """Tell the patient what staff decided."""
    return reply_update("Your request has been processed.")
