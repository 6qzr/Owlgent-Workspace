"""Emergencies are caught by rules before any LLM call, and the graph short-circuits (FR-6)."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from clinic_assistant.agent.graph import build_graph
from clinic_assistant.agent.nodes.safety import emergency_reply, safety_gate
from clinic_assistant.agent.safety_rules import EMERGENCY_INSTRUCTION, is_emergency
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.llm import FakeLLM


@pytest.mark.parametrize(
    "text",
    [
        "I have chest pain",
        "CHEST   PAIN since this morning!",
        "I can't breathe",
        "I cant breathe properly",
        "my father can’t breathe",
        "she is having a seizure",
        "There is heavy bleeding from the cut",
        "I think I'm having a stroke",
        "he passed out at home",
        "I want to kill myself",
    ],
)
def test_emergency_phrases_are_detected(text: str) -> None:
    assert is_emergency(text)


@pytest.mark.parametrize(
    "text",
    [
        "Do I need to fast before a blood test?",
        "Book me with a dermatologist on Thursday",
        "What are your opening hours?",
        "Cancel my appointment tomorrow",
        "",
    ],
)
def test_routine_messages_are_not_emergencies(text: str) -> None:
    assert not is_emergency(text)


def test_phrases_match_whole_words_only() -> None:
    assert not is_emergency("I need a strokes-gained golf lesson")


async def test_safety_gate_checks_only_the_latest_patient_message() -> None:
    state: ConversationState = {
        "messages": [
            HumanMessage("I had chest pain last year"),
            AIMessage("I'm sorry to hear that."),
            HumanMessage("What are your opening hours?"),
        ]
    }

    assert await safety_gate(state) == {"emergency": False}


async def test_safety_gate_flags_an_emergency() -> None:
    state: ConversationState = {"messages": [HumanMessage("I can't breathe")]}

    assert await safety_gate(state) == {"emergency": True}


async def test_emergency_reply_gives_the_fixed_instruction() -> None:
    update = await emergency_reply({"messages": []}, {"configurable": {}})

    assert update["reply"] == EMERGENCY_INSTRUCTION
    assert "diagnos" not in EMERGENCY_INSTRUCTION.lower()


async def test_emergency_never_reaches_the_llm() -> None:
    llm = FakeLLM()  # no scripted replies: any LLM call would fail the test
    graph = build_graph(llm, checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "emergency-1"}}

    result = await graph.ainvoke({"messages": [HumanMessage("I have chest pain")]}, config)

    assert result["reply"] == EMERGENCY_INSTRUCTION
    assert result["emergency"] is True
    assert llm.calls == []
