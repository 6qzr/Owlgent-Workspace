"""Enum values must match the strings stored in PostgreSQL and returned by the API."""

from clinic_assistant.domain import (
    ApprovalAction,
    ApprovalStatus,
    BookingStatus,
    Intent,
)
from clinic_assistant.services.conversation import TurnStatus


def test_intents_cover_every_route() -> None:
    assert {i.value for i in Intent} == {
        "question",
        "find_slots",
        "book",
        "cancel",
        "emergency",
        "other",
    }


def test_booking_statuses_match_the_schema() -> None:
    assert {s.value for s in BookingStatus} == {
        "pending_approval",
        "confirmed",
        "cancelled",
        "rejected",
    }


def test_approval_values_match_the_schema() -> None:
    assert {a.value for a in ApprovalAction} == {"book", "cancel"}
    assert {s.value for s in ApprovalStatus} == {"pending", "approved", "rejected"}


def test_reply_statuses_match_the_api_contract() -> None:
    assert {s.value for s in TurnStatus} == {
        "answered",
        "clarifying",
        "awaiting_approval",
        "emergency",
    }


def test_enums_format_as_plain_strings() -> None:
    assert str(Intent.BOOK) == "book"
    assert f"{BookingStatus.CONFIRMED}" == "confirmed"
