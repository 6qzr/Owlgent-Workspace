"""Graph state shared by every node; each field has exactly one writer (docs/architecture.md)."""

from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from clinic_assistant.domain import ApprovalAction, Intent


class Entities(TypedDict, total=False):
    """Details classify extracts from the patient's message; every key is optional."""

    doctor_name: str
    specialty: str
    booking_day: str
    booking_id: int


class PendingAction(TypedDict):
    """A booking or cancellation waiting for staff; written by prepare_booking / prepare_cancel."""

    action: ApprovalAction
    booking_id: int


class Decision(TypedDict):
    """The staff decision passed in with Command(resume=...)."""

    approved: bool
    reason: str
    staff: str


class ConversationState(TypedDict):
    """State of one conversation thread (thread_id = conversation_id)."""

    # Writer: the service (patient input) and each reply node; appended, never replaced.
    messages: Annotated[list[AnyMessage], add_messages]
    # Writer: classify.
    intent: NotRequired[Intent]
    confidence: NotRequired[float]
    entities: NotRequired[Entities]
    # Writer: safety_gate / emergency_reply.
    emergency: NotRequired[bool]
    # Writer: answer_from_docs (source document names).
    sources: NotRequired[list[str]]
    # Writer: find_slots (slot ids offered to the patient).
    slots_offered: NotRequired[list[int]]
    # Writer: prepare_booking / prepare_cancel.
    pending_action: NotRequired[PendingAction]
    # Writer: record_approval.
    approval_id: NotRequired[int]
    # Writer: the resume input, read by apply_decision.
    decision: NotRequired[Decision]
    # Writer: the last node of each branch.
    reply: NotRequired[str]
