"""Routing decisions as plain functions over state; the LLM never chooses the path (ADR 0005)."""

from typing import Literal

from clinic_assistant.agent.prompts import ROUTING_CONFIDENCE_THRESHOLD
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

# What the patient must give before a workflow can run; checked in code, never by the LLM.
DOCTOR_OR_SPECIALTY = "doctor or specialty"
DAY = "day"


def route_after_safety(state: ConversationState) -> AfterSafety:
    """Send emergencies straight to emergency_reply; everything else to classify."""
    return "emergency_reply" if state.get("emergency") else "classify"


def missing_details(state: ConversationState) -> list[str]:
    """List the details the classified intent still needs from the patient."""
    intent = state.get("intent")
    entities = state.get("entities", {})
    missing: list[str] = []
    if intent in (Intent.FIND_SLOTS, Intent.BOOK) and not (
        "doctor_name" in entities or "specialty" in entities
    ):
        missing.append(DOCTOR_OR_SPECIALTY)
    if intent is Intent.BOOK and "booking_day" not in entities:
        missing.append(DAY)
    return missing


def route_intent(state: ConversationState) -> AfterIntent:
    """Map the classified intent to its node, or ask a clarifying question instead of guessing.

    Order matters: an emergency is never held back by low confidence or missing details.
    """
    intent = state.get("intent")
    if intent is None:
        return "clarify"
    if intent is Intent.EMERGENCY:
        return "emergency_reply"
    if state.get("confidence", 0.0) < ROUTING_CONFIDENCE_THRESHOLD:
        return "clarify"
    if missing_details(state):
        return "clarify"
    return INTENT_TO_NODE[intent]


def route_after_booking(state: ConversationState) -> AfterBooking:
    """Same-day bookings (pending_action set by prepare_booking) wait for staff."""
    return "record_approval" if "pending_action" in state else "confirm_booking"
