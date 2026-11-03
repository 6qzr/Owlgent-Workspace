"""The skeleton graph compiles, routes, and runs end to end with the FakeLLM."""

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from clinic_assistant.agent.graph import build_graph
from clinic_assistant.agent.routing import (
    INTENT_TO_NODE,
    route_after_booking,
    route_after_safety,
    route_intent,
)
from clinic_assistant.agent.state import ConversationState, PendingAction
from clinic_assistant.domain import ApprovalAction, Intent
from clinic_assistant.llm import FakeLLM

EXPECTED_NODES = {
    "safety_gate",
    "emergency_reply",
    "classify",
    "clarify",
    "answer_from_docs",
    "find_slots",
    "polite_scope_reply",
    "prepare_booking",
    "confirm_booking",
    "prepare_cancel",
    "record_approval",
    "await_staff",
    "apply_decision",
    "notify_outcome",
}


def test_graph_has_every_node_from_the_architecture() -> None:
    graph = build_graph(FakeLLM())

    assert set(graph.get_graph().nodes) - {"__start__", "__end__"} == EXPECTED_NODES


async def test_message_runs_end_to_end_and_is_checkpointed() -> None:
    graph = build_graph(FakeLLM(), checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "conversation-1"}}

    result = await graph.ainvoke({"messages": [HumanMessage("Hello")]}, config)

    assert result["reply"]
    saved = await graph.aget_state(config)
    assert len(saved.values["messages"]) == 2  # patient message + reply


def test_emergency_skips_classify() -> None:
    state: ConversationState = {"messages": [], "emergency": True}

    assert route_after_safety(state) == "emergency_reply"


def test_non_emergency_goes_to_classify() -> None:
    state: ConversationState = {"messages": [], "emergency": False}

    assert route_after_safety(state) == "classify"


def test_every_intent_has_a_route() -> None:
    assert set(INTENT_TO_NODE) == set(Intent)
    for intent, node in INTENT_TO_NODE.items():
        assert route_intent({"messages": [], "intent": intent}) == node


def test_missing_intent_asks_for_clarification() -> None:
    assert route_intent({"messages": []}) == "clarify"


def test_same_day_booking_waits_for_staff() -> None:
    pending = PendingAction(action=ApprovalAction.BOOK, booking_id=1)

    assert route_after_booking({"messages": [], "pending_action": pending}) == "record_approval"
    assert route_after_booking({"messages": []}) == "confirm_booking"
