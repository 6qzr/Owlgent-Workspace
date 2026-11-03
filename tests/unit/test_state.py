"""The graph state appends messages and accepts partial updates from nodes."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.message import Messages, add_messages

from clinic_assistant.agent.state import ConversationState, PendingAction
from clinic_assistant.domain import ApprovalAction, Intent


def test_state_needs_only_messages_to_start() -> None:
    state: ConversationState = {"messages": [HumanMessage("Do I need to fast?")]}

    assert len(state["messages"]) == 1


def test_messages_are_appended_not_replaced() -> None:
    history: Messages = HumanMessage("Book me with a dermatologist")
    reply: Messages = AIMessage("Which day?")

    merged = add_messages(history, reply)

    contents = [m.content for m in merged if isinstance(m, BaseMessage)]
    assert contents == ["Book me with a dermatologist", "Which day?"]


def test_nodes_can_return_a_partial_update() -> None:
    update: ConversationState = {
        "messages": [],
        "intent": Intent.CANCEL,
        "pending_action": PendingAction(action=ApprovalAction.CANCEL, booking_id=7),
    }

    assert update["pending_action"]["action"] == "cancel"
