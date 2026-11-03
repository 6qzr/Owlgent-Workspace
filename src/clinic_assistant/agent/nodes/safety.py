"""Emergency short-circuit: rules run before any LLM call (ADR 0005).

Owner: @6qzr (#12). Stubs from the graph skeleton: replace the bodies, keep the names.
"""

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState


async def safety_gate(state: ConversationState) -> Update:
    """Flag the message as an emergency when it matches the emergency phrase list."""
    return {"emergency": False}


async def emergency_reply(state: ConversationState) -> Update:
    """Answer with the fixed emergency instruction and flag the message for staff."""
    return reply_update("If this is an emergency, call 9999 or go to the nearest emergency room.")
