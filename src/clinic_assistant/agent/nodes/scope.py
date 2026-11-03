"""Polite reply for messages outside the assistant's job; never diagnoses.

Owner: @6qzr (#12). Stubs from the graph skeleton: replace the bodies, keep the names.
"""

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState


async def polite_scope_reply(state: ConversationState) -> Update:
    """Explain what the assistant can help with."""
    return reply_update("I can help with clinic questions and appointments.")
