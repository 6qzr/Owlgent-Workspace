"""The skeleton graph compiles, routes, and runs end to end with the FakeLLM."""

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from clinic_assistant.agent.graph import build_graph
from clinic_assistant.agent.nodes.cancel import NOT_FOUND
from clinic_assistant.agent.nodes.classify import Classification
from clinic_assistant.agent.routing import (
    INTENT_TO_NODE,
    route_after_booking,
    route_after_cancel,
    route_after_safety,
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
    llm = FakeLLM([Classification(intent=Intent.OTHER, confidence=0.9)])
    graph = build_graph(llm, checkpointer=InMemorySaver())
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
    """Branch-by-branch routing is covered in test_route_intent.py."""
    assert set(INTENT_TO_NODE) == set(Intent)


def test_same_day_booking_waits_for_staff() -> None:
    pending = PendingAction(action=ApprovalAction.BOOK, booking_id=1)

    assert route_after_booking({"messages": [], "pending_action": pending}) == "record_approval"
    assert route_after_booking({"messages": []}) == "confirm_booking"


def test_an_old_pending_action_does_not_reroute_a_new_turn() -> None:
    """prepare_* write None when nothing waits, so the route ignores an earlier turn's value."""
    assert route_after_booking({"messages": [], "pending_action": None}) == "confirm_booking"


def test_found_cancellation_waits_for_staff() -> None:
    pending = PendingAction(action=ApprovalAction.CANCEL, booking_id=7)

    assert route_after_cancel({"messages": [], "pending_action": pending}) == "record_approval"
    assert route_after_cancel({"messages": [], "pending_action": None}) == "__end__"


async def test_cancel_without_a_found_booking_ends_with_a_reply() -> None:
    llm = FakeLLM([Classification(intent=Intent.CANCEL, confidence=0.9, booking_id=99)])
    graph = build_graph(llm, checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "cancel-1"}}

    result = await graph.ainvoke({"messages": [HumanMessage("Cancel booking 99")]}, config)

    assert result["reply"] == NOT_FOUND
    assert (await graph.aget_state(config)).next == ()  # not paused: nothing to approve
