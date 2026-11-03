"""Answer clinic questions from the clinic documents and name the source.

Owner: @NoorAlbusaidi (#13). Stubs from the graph skeleton: replace the bodies, keep the names.
"""

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState


async def answer_from_docs(state: ConversationState) -> Update:
    """Answer only from retrieved passages, or say I don't know."""
    return reply_update("I don't know yet.")
