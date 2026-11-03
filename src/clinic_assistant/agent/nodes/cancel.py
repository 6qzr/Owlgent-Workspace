"""Prepare a cancellation of the patient's own booking for staff approval.

Owner: @baraah34 (#17). Stub from the graph skeleton: replace the body, keep the name.
"""

from clinic_assistant.agent.nodes import Update
from clinic_assistant.agent.state import ConversationState


async def prepare_cancel(state: ConversationState) -> Update:
    """Find the patient's booking and set pending_action."""
    return {}
