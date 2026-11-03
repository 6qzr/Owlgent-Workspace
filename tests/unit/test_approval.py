"""Test approval nodes without a database."""

import pytest
from langchain_core.runnables import RunnableConfig
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

    # Create the test graph.
    builder = StateGraph(ConversationState)

    # Add the approval nodes.
    builder.add_node("await_staff", await_staff)
    builder.add_node("notify_outcome", notify_outcome)

    # Connect the nodes.
    builder.add_edge(START, "await_staff")
    builder.add_edge("await_staff", "notify_outcome")
    builder.add_edge("notify_outcome", END)

    # Use temporary memory to save the workflow state.
    graph = builder.compile(checkpointer=InMemorySaver())

    # Create a unique conversation for each test.
    config: RunnableConfig = {
        "configurable": {
            "thread_id": f"approval-test-{approved}",
        }
    }

    # Define the input state.
    initial_state: ConversationState = {
        "messages": [],
        "approval_id": 1,
    }

    # Start the graph.
    first = await graph.ainvoke(
        initial_state,
        config=config,
    )

    # Check that the graph paused for staff.
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

    # Check the decision.
    assert result["decision"]["approved"] is approved
    assert result["decision"]["reason"] == reason

    # Check the patient message.
    assert result["reply"] == expected_reply


async def test_invalid_staff_decision() -> None:
    """Test that invalid staff decisions are rejected."""

    # Create the test graph.
    builder = StateGraph(ConversationState)

    # Add the staff approval node.
    builder.add_node("await_staff", await_staff)

    # Connect the graph.
    builder.add_edge(START, "await_staff")
    builder.add_edge("await_staff", END)

    # Save the graph state in temporary memory.
    graph = builder.compile(checkpointer=InMemorySaver())

    # Create a separate conversation.
    config: RunnableConfig = {
        "configurable": {
            "thread_id": "invalid-decision",
        }
    }

    # Define the input state.
    initial_state: ConversationState = {
        "messages": [],
        "approval_id": 2,
    }

    # Start the graph.
    first = await graph.ainvoke(
        initial_state,
        config=config,
    )

    # Check that the workflow paused.
    assert "__interrupt__" in first

    # Try to resume with an invalid decision.
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
