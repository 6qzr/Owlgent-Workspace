"""Classify the patient's message into an intent with entities (the only LLM routing input).

Owner: @6qzr (#11). Stub from the graph skeleton: replace the body, keep the signature.
"""

from clinic_assistant.agent.nodes import Update
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.domain import Intent
from clinic_assistant.llm import LLM


async def classify(state: ConversationState, llm: LLM) -> Update:
    """Ask the LLM for intent, confidence and entities."""
    return {"intent": Intent.OTHER, "confidence": 1.0, "entities": {}}
