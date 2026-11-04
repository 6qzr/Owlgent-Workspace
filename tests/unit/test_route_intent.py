"""route_intent and clarify: low confidence or missing details ask a question, never guess."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from clinic_assistant.agent.graph import build_graph
from clinic_assistant.agent.nodes import CLARIFYING, reply_kind
from clinic_assistant.agent.nodes.clarify import REPHRASE, clarify
from clinic_assistant.agent.nodes.classify import Classification
from clinic_assistant.agent.prompts import ROUTING_CONFIDENCE_THRESHOLD
from clinic_assistant.agent.routing import missing_details, route_intent
from clinic_assistant.agent.state import ConversationState, Entities
from clinic_assistant.domain import Intent
from clinic_assistant.llm import FakeLLM

COMPLETE: dict[Intent, Entities] = {
    Intent.QUESTION: {},
    Intent.FIND_SLOTS: {"specialty": "Dentistry"},
    Intent.BOOK: {"slot_choice": 2, "patient_name": "Sara Ali", "patient_phone": "91234567"},
    Intent.CANCEL: {},
    Intent.OTHER: {},
}


# Three slots find_slots offered earlier in the conversation.
OFFERED = [11, 12, 13]


def state(
    intent: Intent, confidence: float = 0.9, entities: Entities | None = None
) -> ConversationState:
    """A classified state with the given intent, confidence and entities."""
    return {
        "messages": [],
        "intent": intent,
        "confidence": confidence,
        "entities": entities if entities is not None else COMPLETE.get(intent, {}),
        "slots_offered": OFFERED,
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


def test_booking_without_a_phone_asks_for_it() -> None:
    s = state(Intent.BOOK, entities={"slot_choice": 1, "patient_name": "Sara Ali"})

    assert missing_details(s) == ["phone number"]
    assert route_intent(s) == "clarify"


def test_booking_with_nothing_asks_for_everything() -> None:
    assert missing_details(state(Intent.BOOK, entities={})) == [
        "number of a slot from the list of free times",
        "name",
        "phone number",
    ]


@pytest.mark.parametrize("choice", [0, 4])
def test_a_slot_number_outside_the_offer_is_asked_again(choice: int) -> None:
    entities: Entities = {**COMPLETE[Intent.BOOK], "slot_choice": choice}

    assert missing_details(state(Intent.BOOK, entities=entities)) == [
        "number of a slot from the list of free times"
    ]


def test_booking_before_any_slots_were_offered_asks_for_a_slot() -> None:
    s: ConversationState = {**state(Intent.BOOK), "slots_offered": []}

    assert missing_details(s) == ["number of a slot from the list of free times"]


def test_find_slots_needs_a_doctor_or_specialty_but_not_a_day() -> None:
    assert missing_details(state(Intent.FIND_SLOTS, entities={})) == ["doctor or specialty"]
    assert missing_details(state(Intent.FIND_SLOTS, entities={"doctor_name": "Dr. Sara"})) == []


async def test_clarify_names_exactly_what_is_missing() -> None:
    update = await clarify(state(Intent.BOOK, entities={"slot_choice": 2}))

    assert update["reply"] == "To book, please tell me the name and the phone number."


async def test_clarify_asks_for_every_missing_detail() -> None:
    update = await clarify(state(Intent.BOOK, entities={}))

    assert update["reply"] == (
        "To book, please tell me the number of a slot from the list of free times"
        " and the name and the phone number."
    )


async def test_clarify_asks_to_rephrase_when_nothing_specific_is_missing() -> None:
    update = await clarify(state(Intent.QUESTION, confidence=0.2))

    assert update["reply"] == REPHRASE
    assert update["messages"][0].content == REPHRASE


@pytest.mark.parametrize(
    "s",
    [
        state(Intent.BOOK, entities={}),  # specific question
        state(Intent.QUESTION, confidence=0.2),  # rephrase request
    ],
)
async def test_every_clarify_reply_is_marked_clarifying(s: ConversationState) -> None:
    update = await clarify(s)

    assert reply_kind(update["messages"][0]) == CLARIFYING


async def test_two_clarifying_turns_in_a_row_are_both_marked() -> None:
    llm = FakeLLM(
        [
            Classification(intent=Intent.BOOK, confidence=0.9),
            Classification(intent=Intent.BOOK, confidence=0.9, patient_name="Sara Ali"),
        ]
    )
    graph = build_graph(llm, checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "clarify-twice"}}

    await graph.ainvoke({"messages": [HumanMessage("I want to book")]}, config)
    result = await graph.ainvoke({"messages": [HumanMessage("I'm Sara Ali")]}, config)

    replies = [m for m in result["messages"] if isinstance(m, AIMessage)]
    assert [reply_kind(m) for m in replies] == [CLARIFYING, CLARIFYING]
    assert replies[-1].text == (
        "To book, please tell me the number of a slot from the list of free times"
        " and the phone number."
    )
