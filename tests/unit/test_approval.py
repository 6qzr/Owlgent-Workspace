"""Test approval nodes without a database."""
from langchain_core.runnables import RunnableConfig
from clinic_assistant.agent.state import ConversationState
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from clinic_assistant.agent.nodes.approval import (
    await_staff,
    notify_outcome,
)
from clinic_assistant.agent.state import ConversationState


@pytest.mark.parametrize(
    ("approved", "reason", "expected_reply"),
    [
        (
            True,
            "Approved by reception",
            "Your request was approved.",
        ),
        (
            False,
            "Doctor is unavailable",
            "Your request was rejected: Doctor is unavailable",
        ),
    ],
)
async def test_staff_decision(
    approved: bool,
    reason: str,
    expected_reply: str,
) -> None:
    """Test staff approval and rejection."""

    # Create a small test graph.
    builder = StateGraph(ConversationState)

    # Add only the nodes that work without a database.
    builder.add_node("await_staff", await_staff)
    builder.add_node("notify_outcome", notify_outcome)

    # Connect the nodes.
    builder.add_edge(START, "await_staff")
    builder.add_edge("await_staff", "notify_outcome")
    builder.add_edge("notify_outcome", END)

    # Store graph state in temporary memory.
    graph = builder.compile(checkpointer=InMemorySaver())

    # Give each test its own conversation.
    config = {"configurable": {"thread_id": f"approval-test-{approved}"}}

    # Start the workflow.
    first = await graph.ainvoke(
        {"messages": [], "approval_id": 1},
        config=config,
    )

    # The graph should pause.
    assert "__interrupt__" in first

    # Resume with the staff decision.
    result = await graph.ainvoke(
        Command(
            resume={
                "approved": approved,
                "reason": reason,
                "staff": "Receptionist",
            }
        ),
        config=config,
    )

    # Check the staff decision.
    assert result["decision"]["approved"] is approved
    assert result["decision"]["reason"] == reason

    # Check the patient's message.
    # The leader's reply_update helper may store replies
    # differently, so this assumes state["reply"] is a string.
    assert result["reply"] == expected_reply


async def test_invalid_staff_decision() -> None:
    """Test that invalid staff decisions are rejected."""

    # Create a graph with the pause node.
    builder = StateGraph(ConversationState)

    builder.add_node("await_staff", await_staff)

    builder.add_edge(START, "await_staff")
    builder.add_edge("await_staff", END)

    # Save the state in memory.
    graph = builder.compile(checkpointer=InMemorySaver())

    config = {"configurable": {"thread_id": "invalid-decision"}}

    # Start and pause.
    first = await graph.ainvoke(
        {"messages": [], "approval_id": 2},
        config=config,
    )

    assert "__interrupt__" in first

    # Resume with invalid data.
    with pytest.raises(
        ValueError,
        match="Invalid staff decision",
    ):
        await graph.ainvoke(
            Command(
                resume={
                    "approved": "yes",
                    "reason": "Approved",
                    "staff": "Receptionist",
                }
            ),
            config=config,
        )
