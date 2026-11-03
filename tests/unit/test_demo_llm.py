"""DemoLLM classifies with keyword rules so the stack runs end to end without an API key."""

import pytest
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from pydantic import BaseModel

from clinic_assistant.agent.nodes.classify import Classification
from clinic_assistant.domain import Intent
from clinic_assistant.llm import LLMError
from clinic_assistant.llm.demo import DEMO_REPLY, DemoLLM


async def classify(text: str) -> Classification:
    return await DemoLLM().parse([HumanMessage(text)], Classification)


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Please cancel booking 12", Intent.CANCEL),
        ("Which slots are free on Thursday?", Intent.FIND_SLOTS),
        ("Book me with a dentist tomorrow", Intent.BOOK),
        ("What are your opening hours?", Intent.QUESTION),
        ("Do I need to fast before a blood test?", Intent.QUESTION),
        ("Hello there", Intent.OTHER),
    ],
)
async def test_keywords_pick_the_intent(text: str, intent: Intent) -> None:
    assert (await classify(text)).intent is intent


async def test_booking_details_are_extracted() -> None:
    result = await classify("Book me with Dr. Sara, dentistry, on Thursday")

    assert result.doctor_name == "Dr. Sara"
    assert result.specialty == "Dentistry"
    assert result.booking_day == "Thursday"


async def test_cancel_extracts_the_booking_id() -> None:
    assert (await classify("cancel my booking #7")).booking_id == 7


async def test_only_the_latest_patient_message_counts() -> None:
    messages: list[AnyMessage] = [
        HumanMessage("cancel booking 3"),
        AIMessage("Sure."),
        HumanMessage("hi"),
    ]

    result = await DemoLLM().parse(messages, Classification)

    assert result.intent is Intent.OTHER


async def test_complete_returns_the_demo_reply() -> None:
    assert await DemoLLM().complete([HumanMessage("anything")]) == DEMO_REPLY


async def test_unsupported_schema_raises_llm_error() -> None:
    class Unrelated(BaseModel):
        answer: str

    with pytest.raises(LLMError):
        await DemoLLM().parse([HumanMessage("hi")], Unrelated)
