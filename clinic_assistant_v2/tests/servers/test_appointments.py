"""Tests for the Appointments MCP Server."""

import time
from copy import deepcopy

import jwt
import pytest

from servers.appointments import server
from servers.appointments.tokens import create_token

TEST_SECRET = "unit-test-secret-not-for-production"

ORIGINAL_APPOINTMENTS = deepcopy(server.appointments)


@pytest.fixture(autouse=True)
def setup_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set a fake JWT secret and reset appointments before each test."""
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setattr(
        server,
        "appointments",
        deepcopy(ORIGINAL_APPOINTMENTS),
    )


def authenticate(
    monkeypatch: pytest.MonkeyPatch,
    user_id: str,
    scopes: list[str],
) -> None:
    """Mock an HTTP Bearer header containing a valid JWT."""
    token = create_token(
        sub=user_id,
        email=f"{user_id}@example.com",
        scopes=scopes,
    )

    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {"authorization": f"Bearer {token}"},
    )


def test_book_appointment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A signed-in user can book a free appointment."""
    authenticate(monkeypatch, "user-a", ["appointments:write"])

    result = server.book_appointment(
        doctor="Dr. Sara",
        date="2026-12-05",
        time="11:00",
    )

    assert result["user_id"] == "user-a"
    assert result["doctor"] == "Dr. Sara"
    assert result["status"] == "booked"


def test_duplicate_booking(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same doctor and time cannot be booked twice."""
    authenticate(monkeypatch, "user-a", ["appointments:write"])

    result = server.book_appointment(
        doctor="Dr. Huda",
        date="2026-12-01",
        time="09:00",
    )

    assert result == {"error": "slot already booked"}


def test_list_my_appointments(monkeypatch: pytest.MonkeyPatch) -> None:
    """A user can see only their own appointments."""
    authenticate(monkeypatch, "user-a", ["appointments:read"])

    result = server.list_my_appointments()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["user_id"] == "user-a"


def test_user_b_cannot_see_user_a(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User B cannot view User A's appointments."""
    authenticate(monkeypatch, "user-b", ["appointments:read"])

    result = server.list_my_appointments()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["user_id"] == "user-b"


def test_cancel_own_appointment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user can cancel their own appointment."""
    authenticate(monkeypatch, "user-a", ["appointments:write"])

    result = server.cancel_appointment(appointment_id=1)

    assert result["status"] == "cancelled"
    assert result["user_id"] == "user-a"


def test_cannot_cancel_other_user_appointment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user cannot cancel another user's appointment."""
    authenticate(monkeypatch, "user-a", ["appointments:write"])

    result = server.cancel_appointment(appointment_id=2)

    assert result == {"error": "not found"}
    assert server.appointments[2]["status"] == "booked"


def test_cancel_unknown_appointment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown appointment returns not found."""
    authenticate(monkeypatch, "user-a", ["appointments:write"])

    result = server.cancel_appointment(appointment_id=999)

    assert result == {"error": "not found"}


def test_cancel_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cancelled appointment cannot be cancelled again."""
    authenticate(monkeypatch, "user-a", ["appointments:write"])

    server.cancel_appointment(appointment_id=1)
    result = server.cancel_appointment(appointment_id=1)

    assert result == {"error": "already cancelled"}


def test_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing Bearer authentication returns unauthorized."""
    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {},
    )

    result = server.list_my_appointments()

    assert result == {"error": "unauthorized"}


def test_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """An invalid JWT returns unauthorized."""
    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {"authorization": "Bearer invalid-token"},
    )

    result = server.cancel_appointment(appointment_id=1)

    assert result == {"error": "unauthorized"}


def test_missing_read_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Listing appointments requires the read scope."""
    authenticate(monkeypatch, "user-a", ["appointments:write"])

    result = server.list_my_appointments()

    assert result == {"error": "unauthorized"}


def test_missing_write_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Booking an appointment requires the write scope."""
    authenticate(monkeypatch, "user-a", ["appointments:read"])

    result = server.book_appointment(
        doctor="Dr. Sara",
        date="2026-12-05",
        time="11:00",
    )

    assert result == {"error": "unauthorized"}


def test_cancel_requires_write_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelling an appointment requires the write scope."""
    authenticate(monkeypatch, "user-a", ["appointments:read"])

    result = server.cancel_appointment(appointment_id=1)

    assert result == {"error": "unauthorized"}


def test_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """An expired JWT cannot access appointment data."""
    expired_token = jwt.encode(
        {
            "sub": "user-a",
            "email": "user-a@example.com",
            "scopes": ["appointments:read"],
            "exp": int(time.time()) - 60,
        },
        TEST_SECRET,
        algorithm="HS256",
    )

    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {"authorization": f"Bearer {expired_token}"},
    )

    result = server.list_my_appointments()

    assert result == {"error": "unauthorized"}
