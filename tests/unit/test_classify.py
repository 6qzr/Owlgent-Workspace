"""classify turns the model's structured output into state; the FakeLLM stands in for OpenAI."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from clinic_assistant.agent.nodes.classify import Classification, classify, to_entities
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.domain import Intent
from clinic_assistant.llm import FakeLLM, LLMError


def conversation(*texts: str) -> ConversationState:
    """A state with alternating patient and assistant messages."""
    messages = [HumanMessage(t) if i % 2 == 0 else AIMessage(t) for i, t in enumerate(texts)]
    return {"messages": list(messages)}


@pytest.mark.parametrize("intent", list(Intent))
async def test_every_intent_is_written_to_state(intent: Intent) -> None:
    llm = FakeLLM([Classification(intent=intent, confidence=0.8)])

    update = await classify(conversation("hello"), llm)

    assert update["intent"] is intent
    assert update["confidence"] == 0.8


async def test_entities_keep_only_what_the_patient_gave() -> None:
    reply = Classification(
        intent=Intent.BOOK, confidence=0.9, doctor_name="Dr. Sara", booking_day="Thursday"
    )
    llm = FakeLLM([reply])

    update = await classify(conversation("Book me with Dr. Sara on Thursday"), llm)

    assert update["entities"] == {"doctor_name": "Dr. Sara", "booking_day": "Thursday"}


def test_no_details_gives_empty_entities() -> None:
    assert to_entities(Classification(intent=Intent.OTHER, confidence=0.5)) == {}


def test_booking_id_is_kept() -> None:
    result = Classification(intent=Intent.CANCEL, confidence=0.9, booking_id=12)

    assert to_entities(result) == {"booking_id": 12}


async def test_only_the_recent_window_is_sent_with_the_system_prompt() -> None:
    llm = FakeLLM([Classification(intent=Intent.QUESTION, confidence=0.7)])
    state = conversation("1", "2", "3", "4", "5")

    await classify(state, llm, window=2)

    sent = llm.calls[0]
    assert isinstance(sent[0], SystemMessage)
    assert [m.content for m in sent[1:]] == ["4", "5"]


async def test_model_failure_surfaces_as_llm_error() -> None:
    llm = FakeLLM([LLMError("timeout")])

    with pytest.raises(LLMError):
        await classify(conversation("hello"), llm)


def test_confidence_outside_0_to_1_is_rejected() -> None:
    with pytest.raises(ValueError):
        Classification(intent=Intent.OTHER, confidence=1.5)
