"""Every tool on every real server refuses a bad token with exactly {"error": "unauthorized"}."""

import time
from typing import Any

import jwt
import pytest

from servers.appointments import server as appointments
from servers.pharmacy import server as pharmacy
from tests.conftest import ALL_SCOPES, TEST_SECRET, TokenFactory
from tests.e2e.helpers import call_tool

pytestmark = pytest.mark.anyio

UNAUTHORIZED = {"error": "unauthorized"}

# (server, tool, arguments, the scope the contract says it needs) for all eight tools.
TOOLS: list[tuple[str, str, dict[str, Any], str]] = [
    (
        "appointments",
        "book_appointment",
        {"doctor": "Dr. Huda", "date": "2026-12-20", "time": "09:00"},
        "appointments:write",
    ),
    ("appointments", "list_my_appointments", {}, "appointments:read"),
    ("appointments", "cancel_appointment", {"appointment_id": 1}, "appointments:write"),
    ("pharmacy", "view_inventory", {}, "pharmacy:read"),
    ("pharmacy", "add_inventory", {"medicine": "Paracetamol", "quantity": 5}, "pharmacy:write"),
    ("records", "get_my_medical_records", {}, "records:read"),
    ("records", "get_my_last_medical_record", {}, "records:read"),
    ("knowledge", "search_clinic_docs", {"query": "skin doctor"}, "docs:read"),
]
TOOL_IDS = [name for _, name, _, _ in TOOLS]


def signed(claims: dict[str, Any], secret: str) -> str:
    """Sign arbitrary claims, to build the bad tokens create_token never makes."""
    return jwt.encode(claims, secret, algorithm="HS256")


def valid_claims() -> dict[str, Any]:
    """Claims that are fine apart from whatever a test changes."""
    return {
        "sub": "user-a",
        "email": "user-a@example.com",
        "scopes": ALL_SCOPES,
        "exp": int(time.time()) + 3600,
    }


def bad_tokens(scope: str, make_token: TokenFactory) -> dict[str, str | None]:
    """The four kinds of bad token from #125, for a tool that needs this scope."""
    return {
        "missing": None,
        "bad signature": signed(valid_claims(), "a-different-secret-that-is-long-enough-too"),
        "expired": signed({**valid_claims(), "exp": int(time.time()) - 60}, TEST_SECRET),
        "missing scope": make_token("user-a", [s for s in ALL_SCOPES if s != scope]),
    }


@pytest.mark.parametrize("kind", ["missing", "bad signature", "expired", "missing scope"])
@pytest.mark.parametrize(("server", "tool", "arguments", "scope"), TOOLS, ids=TOOL_IDS)
async def test_bad_token_is_unauthorized_with_no_data(
    servers: dict[str, str],
    make_token: TokenFactory,
    kind: str,
    server: str,
    tool: str,
    arguments: dict[str, Any],
    scope: str,
) -> None:
    """A bad token gets exactly {"error": "unauthorized"}: no data, and nothing changes."""
    token = bad_tokens(scope, make_token)[kind]

    result = await call_tool(servers[server], tool, arguments, token)

    assert result == UNAUTHORIZED
    assert appointments.appointments[1]["status"] == "booked"
    assert len(appointments.appointments) == 2
    assert pharmacy.inventory["Paracetamol"] == 120
