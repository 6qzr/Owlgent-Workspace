"""Ask the patient for the details classify could not find, instead of guessing (FR-2).

Owner: @6qzr (#11).
"""

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.routing import missing_details
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.domain import Intent

REPHRASE = (
    "Sorry, I'm not sure what you need. I can answer clinic questions, show free "
    "appointment times, and book or cancel appointments. Could you say it another way?"
)

ACTION_WORDS = {Intent.FIND_SLOTS: "show free times", Intent.BOOK: "book"}


async def clarify(state: ConversationState) -> Update:
    """Name exactly what is missing; fall back to a rephrase request when nothing specific is."""
    intent = state.get("intent")
    missing = missing_details(state)
    if intent in ACTION_WORDS and missing:
        return reply_update(
            f"To {ACTION_WORDS[intent]}, please tell me the {' and the '.join(missing)}."
        )
    return reply_update(REPHRASE)
