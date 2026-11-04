"""Checkpointed state keeps our enums as enums (not plain str) after a load."""

from langchain_core.messages import AIMessage, HumanMessage

from clinic_assistant.agent.checkpointer import checkpoint_serializer
from clinic_assistant.agent.state import ConversationState, PendingAction
from clinic_assistant.domain import ApprovalAction, Intent


def sample_state() -> ConversationState:
    """A state with every kind of value a real turn stores."""
    return {
        "messages": [HumanMessage("Cancel booking 7"), AIMessage("Waiting for staff")],
        "intent": Intent.CANCEL,
        "confidence": 0.9,
        "entities": {"booking_id": 7, "patient_name": "Sara Ali"},
        "pending_action": PendingAction(action=ApprovalAction.CANCEL, booking_id=7),
        "approval_id": 12,
        "decision": {"approved": True, "reason": "ok", "staff": "Mona"},
    }


def test_enums_survive_a_round_trip_as_enums() -> None:
    serde = checkpoint_serializer()

    loaded = serde.loads_typed(serde.dumps_typed(sample_state()))

    assert loaded["intent"] is Intent.CANCEL
    assert loaded["pending_action"]["action"] is ApprovalAction.CANCEL
    assert loaded["messages"][0].content == "Cancel booking 7"
