"""Classify the patient's message into an intent with entities (the only LLM routing input).

Owner: @6qzr (#11). The LLM only classifies; route_intent (plain code) decides the path.
"""

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from clinic_assistant.agent.nodes import Update
from clinic_assistant.agent.prompts import CLASSIFY_HISTORY_WINDOW, CLASSIFY_SYSTEM_PROMPT
from clinic_assistant.agent.state import ConversationState, Entities
from clinic_assistant.domain import Intent
from clinic_assistant.llm import LLM


class Classification(BaseModel):
    """Structured output the model must return; validated before it reaches the graph."""

    intent: Intent
    confidence: float = Field(ge=0, le=1)
    doctor_name: str | None = None
    specialty: str | None = None
    booking_day: str | None = None
    booking_id: int | None = None


def to_entities(result: Classification) -> Entities:
    """Keep only the details the patient actually gave."""
    entities = Entities()
    if result.doctor_name is not None:
        entities["doctor_name"] = result.doctor_name
    if result.specialty is not None:
        entities["specialty"] = result.specialty
    if result.booking_day is not None:
        entities["booking_day"] = result.booking_day
    if result.booking_id is not None:
        entities["booking_id"] = result.booking_id
    return entities


async def classify(
    state: ConversationState, llm: LLM, window: int = CLASSIFY_HISTORY_WINDOW
) -> Update:
    """Ask the LLM for intent, confidence and entities, sending only the recent window."""
    prompt = [SystemMessage(CLASSIFY_SYSTEM_PROMPT), *state["messages"][-window:]]
    result = await llm.parse(prompt, Classification)
    return {
        "intent": result.intent,
        "confidence": result.confidence,
        "entities": to_entities(result),
    }
