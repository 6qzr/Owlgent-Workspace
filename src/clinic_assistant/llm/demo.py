"""Rule-based stand-in used when LLM_PROVIDER=fake, so anyone can run the stack without a key.

Unlike FakeLLM (scripted replies for unit tests), DemoLLM answers any message with simple
keyword rules. It is good enough to demo routing end to end; it is not a language model.
"""

import re
from collections.abc import Sequence

from langchain_core.messages import AnyMessage, HumanMessage
from pydantic import BaseModel, ValidationError

from clinic_assistant.domain import Intent
from clinic_assistant.llm.base import LLMError

DEMO_REPLY = "Demo mode: replies come from simple rules, not a language model."

SPECIALTY_WORDS = {
    "dentistry": "Dentistry",
    "dentist": "Dentistry",
    "dental": "Dentistry",
    "general practice": "General Practice",
    "general practitioner": "General Practice",
    "gp": "General Practice",
}
DAY_WORDS = (
    "today",
    "tomorrow",
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
)
# "book number 2" / "book slot 2": picks from the slots find_slots offered; checked before the
# word rules, because "slot" alone means find_slots.
SLOT_CHOICE = re.compile(r"\b(?:book|take|choose)\s+(?:slot|number|option)?\s*#?(\d+)\b")
NAME = re.compile(r"\b(?:my name is|name is|name:)\s*([a-z]+(?:\s+[a-z]+)?)")
PHONE = re.compile(r"\+?\d[\d\s-]{6,}\d")
# Checked in order; the first rule whose words appear in the message wins.
INTENT_RULES: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (Intent.CANCEL, ("cancel",)),
    (Intent.FIND_SLOTS, ("free", "available", "slot", "when is", "what times")),
    (Intent.BOOK, ("book", "appointment", "reserve")),
    (Intent.QUESTION, ("hours", "open", "fast", "insurance", "prepare", "policy", "?")),
)


def _latest_text(messages: Sequence[AnyMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.text).lower()
    return ""


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) is not None


def classify_text(text: str) -> dict[str, object]:
    """Keyword classification of one message into intent, confidence and details."""
    choice = SLOT_CHOICE.search(text)
    intent = (
        Intent.BOOK
        if choice
        else next((i for i, words in INTENT_RULES if any(w in text for w in words)), Intent.OTHER)
    )
    result: dict[str, object] = {"intent": intent, "confidence": 0.9}
    if choice:
        result["slot_choice"] = int(choice.group(1))
    if name := NAME.search(text):
        result["patient_name"] = name.group(1).title()
    if phone := PHONE.search(text):
        result["patient_phone"] = re.sub(r"[\s-]", "", phone.group())
    specialty = next((s for w, s in SPECIALTY_WORDS.items() if _has_word(text, w)), None)
    if specialty:
        result["specialty"] = specialty
    if doctor := re.search(r"\bdr\.?\s+([a-z]+)", text):
        result["doctor_name"] = f"Dr. {doctor.group(1).capitalize()}"
    if day := next((d for d in DAY_WORDS if _has_word(text, d)), None):
        result["booking_day"] = day.capitalize()
    if intent is Intent.CANCEL and (number := re.search(r"\d+", text)):
        result["booking_id"] = int(number.group())
    return result


class DemoLLM:
    """Satisfies the LLM protocol with keyword rules; deterministic and offline."""

    async def complete(self, messages: Sequence[AnyMessage]) -> str:
        return DEMO_REPLY

    async def parse[SchemaT: BaseModel](
        self, messages: Sequence[AnyMessage], schema: type[SchemaT]
    ) -> SchemaT:
        try:
            return schema.model_validate(classify_text(_latest_text(messages)))
        except ValidationError as exc:
            raise LLMError(f"Demo mode cannot produce {schema.__name__}") from exc
