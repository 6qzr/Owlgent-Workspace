"""route_intent and clarify: low confidence or missing details ask a question, never guess."""

import pytest

from clinic_assistant.agent.nodes.clarify import REPHRASE, clarify
from clinic_assistant.agent.prompts import ROUTING_CONFIDENCE_THRESHOLD
from clinic_assistant.agent.routing import missing_details, route_intent
from clinic_assistant.agent.state import ConversationState, Entities
from clinic_assistant.domain import Intent

COMPLETE: dict[Intent, Entities] = {
    Intent.QUESTION: {},
    Intent.FIND_SLOTS: {"specialty": "Dentistry"},
    Intent.BOOK: {"doctor_name": "Dr. Sara", "booking_day": "Thursday"},
    Intent.CANCEL: {},
    Intent.OTHER: {},
}


def state(
    intent: Intent, confidence: float = 0.9, entities: Entities | None = None
) -> ConversationState:
    """A classified state with the given intent, confidence and entities."""
    return {
        "messages": [],
        "intent": intent,
        "confidence": confidence,
        "entities": entities if entities is not None else COMPLETE.get(intent, {}),
    }


@pytest.mark.parametrize(
    ("intent", "node"),
    [
        (Intent.QUESTION, "answer_from_docs"),
        (Intent.FIND_SLOTS, "find_slots"),
        (Intent.BOOK, "prepare_booking"),
        (Intent.CANCEL, "prepare_cancel"),
        (Intent.OTHER, "polite_scope_reply"),
    ],
)
def test_confident_and_complete_messages_reach_their_node(intent: Intent, node: str) -> None:
    assert route_intent(state(intent)) == node


def test_low_confidence_asks_instead_of_guessing() -> None:
    low = ROUTING_CONFIDENCE_THRESHOLD - 0.01

    assert route_intent(state(Intent.QUESTION, confidence=low)) == "clarify"


def test_threshold_itself_is_confident_enough() -> None:
    assert route_intent(state(Intent.QUESTION, ROUTING_CONFIDENCE_THRESHOLD)) == "answer_from_docs"


def test_emergency_wins_even_with_low_confidence() -> None:
    assert route_intent(state(Intent.EMERGENCY, confidence=0.1)) == "emergency_reply"


def test_missing_intent_asks_for_clarification() -> None:
    assert route_intent({"messages": []}) == "clarify"


def test_booking_without_a_day_asks_for_it() -> None:
    s = state(Intent.BOOK, entities={"specialty": "Dentistry"})

    assert missing_details(s) == ["day"]
    assert route_intent(s) == "clarify"


def test_booking_with_nothing_asks_for_both() -> None:
    assert missing_details(state(Intent.BOOK, entities={})) == ["doctor or specialty", "day"]


def test_find_slots_needs_a_doctor_or_specialty_but_not_a_day() -> None:
    assert missing_details(state(Intent.FIND_SLOTS, entities={})) == ["doctor or specialty"]
    assert missing_details(state(Intent.FIND_SLOTS, entities={"doctor_name": "Dr. Sara"})) == []


async def test_clarify_names_exactly_what_is_missing() -> None:
    update = await clarify(state(Intent.BOOK, entities={"specialty": "Dentistry"}))

    assert update["reply"] == "To book, please tell me the day."


async def test_clarify_asks_for_both_details() -> None:
    update = await clarify(state(Intent.BOOK, entities={}))

    assert update["reply"] == "To book, please tell me the doctor or specialty and the day."


async def test_clarify_asks_to_rephrase_when_nothing_specific_is_missing() -> None:
    update = await clarify(state(Intent.QUESTION, confidence=0.2))

    assert update["reply"] == REPHRASE
    assert update["messages"][0].content == REPHRASE
