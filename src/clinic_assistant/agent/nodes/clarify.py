"""Ask the patient for the details classify could not find.

Owner: @6qzr (#11). Stubs from the graph skeleton: replace the bodies, keep the names.
"""

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState


async def clarify(state: ConversationState) -> Update:
    """Ask for the missing details instead of guessing."""
    return reply_update("Could you tell me a bit more?")
