"""The skeleton graph compiles, routes, and runs end to end with the FakeLLM."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from clinic_assistant.agent.graph import Repositories, build_graph
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
from clinic_assistant.repository.approvals import ApprovalsRepository

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
    """Check that the graph contains all required nodes."""

    graph = build_graph(FakeLLM())

    assert set(graph.get_graph().nodes) - {"__start__", "__end__"} == EXPECTED_NODES


async def test_message_runs_end_to_end_and_is_checkpointed() -> None:
    """Check that a normal conversation runs and saves its history."""

    llm = FakeLLM([Classification(intent=Intent.OTHER, confidence=0.9)])
    graph = build_graph(llm, checkpointer=InMemorySaver())

    config: RunnableConfig = {"configurable": {"thread_id": "conversation-1"}}

    result = await graph.ainvoke(
        {"messages": [HumanMessage("Hello")]},
        config,
    )

    assert result["reply"]

    saved = await graph.aget_state(config)
    assert len(saved.values["messages"]) == 2  # patient message + reply


def test_emergency_skips_classify() -> None:
    """An emergency must bypass normal intent classification."""

    state: ConversationState = {
        "messages": [],
        "emergency": True,
    }

    assert route_after_safety(state) == "emergency_reply"


def test_non_emergency_goes_to_classify() -> None:
    """Non-emergency messages should be classified."""

    state: ConversationState = {
        "messages": [],
        "emergency": False,
    }

    assert route_after_safety(state) == "classify"


def test_every_intent_has_a_route() -> None:
    """Branch-by-branch routing is covered in test_route_intent.py."""

    assert set(INTENT_TO_NODE) == set(Intent)


def test_same_day_booking_waits_for_staff() -> None:
    """A booking requiring approval must go to record_approval."""

    pending = PendingAction(
        action=ApprovalAction.BOOK,
        booking_id=1,
    )

    assert (
        route_after_booking(
            {
                "messages": [],
                "pending_action": pending,
            }
        )
        == "record_approval"
    )

    assert route_after_booking({"messages": []}) == "confirm_booking"


def test_an_old_pending_action_does_not_reroute_a_new_turn() -> None:
    """An earlier pending action should not affect the new turn."""

    assert (
        route_after_booking(
            {
                "messages": [],
                "pending_action": None,
            }
        )
        == "confirm_booking"
    )


def test_found_cancellation_waits_for_staff() -> None:
    """A valid cancellation must be sent for staff approval."""

    pending = PendingAction(
        action=ApprovalAction.CANCEL,
        booking_id=7,
    )

    assert (
        route_after_cancel(
            {
                "messages": [],
                "pending_action": pending,
            }
        )
        == "record_approval"
    )

    assert (
        route_after_cancel(
            {
                "messages": [],
                "pending_action": None,
            }
        )
        == "__end__"
    )


async def test_cancel_without_a_found_booking_ends_with_a_reply() -> None:
    """An unknown booking must not create a cancellation approval."""

    # FakeLLM recognizes the patient's cancellation request.
    llm = FakeLLM(
        [
            Classification(
                intent=Intent.CANCEL,
                confidence=0.9,
                booking_id=99,
            )
        ]
    )

    # Mock the approvals repository.
    # Booking 99 does not exist in this conversation.
    approvals = MagicMock(spec=ApprovalsRepository)
    approvals.find_cancellable_booking = AsyncMock(return_value=None)

    # Build the graph with the mocked repository.
    graph = build_graph(
        llm,
        checkpointer=InMemorySaver(),
        repositories=Repositories(approvals=approvals),
    )

    # Use a valid UUID as the conversation ID.
    conversation_id = uuid4()

    config: RunnableConfig = {
        "configurable": {
            "thread_id": str(conversation_id),
        }
    }

    # Send the cancellation request.
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="Cancel booking 99")]},
        config,
    )

    # The patient receives the not-found message.
    assert result["reply"] == NOT_FOUND

    # No cancellation approval should be created.
    assert result["pending_action"] is None

    # Verify the booking was searched using the correct conversation.
    approvals.find_cancellable_booking.assert_awaited_once_with(
        booking_id=99,
        conversation_id=conversation_id,
    )

    # The graph finishes instead of pausing for approval.
    assert (await graph.aget_state(config)).next == ()
