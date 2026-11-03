"""Routing decisions as plain functions over state; the LLM never chooses the path (ADR 0005)."""

from typing import Literal

from clinic_assistant.agent.state import ConversationState
from clinic_assistant.domain import Intent

type AfterSafety = Literal["emergency_reply", "classify"]
type AfterIntent = Literal[
    "emergency_reply",
    "clarify",
    "answer_from_docs",
    "find_slots",
    "polite_scope_reply",
    "prepare_booking",
    "prepare_cancel",
]
type AfterBooking = Literal["record_approval", "confirm_booking"]

INTENT_TO_NODE: dict[Intent, AfterIntent] = {
    Intent.EMERGENCY: "emergency_reply",
    Intent.QUESTION: "answer_from_docs",
    Intent.FIND_SLOTS: "find_slots",
    Intent.BOOK: "prepare_booking",
    Intent.CANCEL: "prepare_cancel",
    Intent.OTHER: "polite_scope_reply",
}


def route_after_safety(state: ConversationState) -> AfterSafety:
    """Send emergencies straight to emergency_reply; everything else to classify."""
    return "emergency_reply" if state.get("emergency") else "classify"


def route_intent(state: ConversationState) -> AfterIntent:
    """Map the classified intent to its node; unknown intent → clarify.

    The confidence threshold and missing-details checks come in the route_intent step of #11.
    """
    intent = state.get("intent")
    return INTENT_TO_NODE.get(intent, "clarify") if intent else "clarify"


def route_after_booking(state: ConversationState) -> AfterBooking:
    """Same-day bookings (pending_action set by prepare_booking) wait for staff."""
    return "record_approval" if "pending_action" in state else "confirm_booking"
