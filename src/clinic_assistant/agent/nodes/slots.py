"""Find free slots by doctor or specialty and date.

Owner: @baraah34 (#14). Stubs from the graph skeleton: replace the bodies, keep the names.
"""

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState


async def find_slots(state: ConversationState) -> Update:
    """Offer free slots matching the patient's entities."""
    return reply_update("No free slots found.")
