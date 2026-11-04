"""Prepare a cancellation of the patient's own booking for staff approval.

Owner: @baraah34 (#17). Stub from the graph skeleton: replace the body, keep the name.
"""

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState

NOT_FOUND = "I couldn't find a booking with that number in this conversation."


async def prepare_cancel(state: ConversationState, config: RunnableConfig) -> Update:
    """Find the patient's booking and set pending_action.

    config["configurable"]["approval_repository"] is the ApprovalsRepository (wired in graph.py).
    Found: return pending_action. Not found: pending_action None plus a reply; the turn ends.
    """
    return {"pending_action": None, **reply_update(NOT_FOUND)}
