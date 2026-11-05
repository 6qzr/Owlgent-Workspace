"""Shared domain types used by every layer (API, graph and storage)."""

from enum import StrEnum


class Intent(StrEnum):
    """What the patient wants; produced by classify, consumed by route_intent."""

    QUESTION = "question"
    FIND_SLOTS = "find_slots"
    BOOK = "book"
    CANCEL = "cancel"
    EMERGENCY = "emergency"
    OTHER = "other"


class BookingStatus(StrEnum):
    """Values of bookings.status; pending and confirmed hold the slot (ADR 0006)."""

    PENDING_APPROVAL = "pending_approval"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class ApprovalAction(StrEnum):
    """Values of approvals.action: what staff are asked to approve."""

    BOOK = "book"
    CANCEL = "cancel"


class ApprovalStatus(StrEnum):
    """Values of approvals.status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
