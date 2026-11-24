"""Tests for the Medical Records MCP server."""

import time

import jwt
import pytest

from servers.records import server
from servers.records.tokens import create_token

TEST_SECRET = "fake-medical-records-test-secret"


@pytest.fixture(autouse=True)
def setup_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a fake JWT secret for each test."""
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)


def authenticate(
    monkeypatch: pytest.MonkeyPatch,
    user_id: str,
    scopes: list[str],
) -> None:
    """Mock an HTTP Bearer header with a signed test token."""
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


def test_user_a_all_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """User A can view only their own records."""
    authenticate(monkeypatch, "user-a", ["records:read"])

    result = server.get_my_medical_records()

    assert isinstance(result, list)
    assert len(result) >= 2
    assert result[-1]["diagnosis"] == "Flu"


def test_user_b_all_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """User B can view only their own records."""
    authenticate(monkeypatch, "user-b", ["records:read"])

    result = server.get_my_medical_records()

    assert isinstance(result, list)
    assert len(result) >= 2
    assert result[-1]["diagnosis"] == "Sprained ankle"
    assert all(record["diagnosis"] != "Flu" for record in result)


def test_user_a_last_record(monkeypatch: pytest.MonkeyPatch) -> None:
    """User A's latest record is the Flu record."""
    authenticate(monkeypatch, "user-a", ["records:read"])

    result = server.get_my_last_medical_record()

    assert result == {
        "date": "2026-10-02",
        "diagnosis": "Flu",
        "notes": "Rest",
    }


def test_user_b_last_record(monkeypatch: pytest.MonkeyPatch) -> None:
    """User B's latest record is the Sprained ankle record."""
    authenticate(monkeypatch, "user-b", ["records:read"])

    result = server.get_my_last_medical_record()

    assert result == {
        "date": "2026-10-20",
        "diagnosis": "Sprained ankle",
        "notes": "Ice and rest",
    }


def test_unknown_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown signed-in patient has no records."""
    authenticate(monkeypatch, "user-unknown", ["records:read"])

    assert server.get_my_medical_records() == {"error": "no records"}
    assert server.get_my_last_medical_record() == {"error": "no records"}


def test_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requests without a Bearer token are unauthorized."""
    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {},
    )

    assert server.get_my_medical_records() == {"error": "unauthorized"}
    assert server.get_my_last_medical_record() == {"error": "unauthorized"}


def test_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed JWTs cannot access medical records."""
    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {"authorization": "Bearer invalid-token"},
    )

    assert server.get_my_last_medical_record() == {"error": "unauthorized"}


def test_missing_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Medical records require the records:read scope."""
    authenticate(monkeypatch, "user-a", ["pharmacy:read"])

    assert server.get_my_medical_records() == {"error": "unauthorized"}
    assert server.get_my_last_medical_record() == {"error": "unauthorized"}


def test_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expired JWTs are rejected."""
    token = jwt.encode(
        {
            "sub": "user-a",
            "email": "user-a@example.com",
            "scopes": ["records:read"],
            "exp": int(time.time()) - 60,
        },
        TEST_SECRET,
        algorithm="HS256",
    )

    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {"authorization": f"Bearer {token}"},
    )

    assert server.get_my_last_medical_record() == {"error": "unauthorized"}
