"""Tests for the Pharmacy Inventory MCP Server."""

import time

import jwt
import pytest

from servers.pharmacy import server
from servers.pharmacy.tokens import create_token

TEST_SECRET = "unit-test-secret-not-for-production"


@pytest.fixture(autouse=True)
def setup_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset inventory and configure a fake JWT secret."""
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setattr(
        server,
        "inventory",
        {"Paracetamol": 120, "Ibuprofen": 40},
    )


def authenticate(
    monkeypatch: pytest.MonkeyPatch,
    scopes: list[str],
) -> None:
    """Mock a Bearer header containing a signed test JWT."""
    token = create_token(
        sub="user-a",
        email="user-a@example.com",
        scopes=scopes,
    )
    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {"authorization": f"Bearer {token}"},
    )


def test_view_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    """A user with read permission can see the inventory."""
    authenticate(monkeypatch, ["pharmacy:read"])

    result = server.view_inventory()

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["medicine"] == "Paracetamol"
    assert result[0]["stock"] == 120


def test_add_existing_medicine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding existing medicine increases its stock."""
    authenticate(monkeypatch, ["pharmacy:write"])

    result = server.add_inventory("Paracetamol", 20)

    assert result == {"medicine": "Paracetamol", "stock": 140}


def test_add_new_medicine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding a new medicine creates an inventory item."""
    authenticate(monkeypatch, ["pharmacy:write"])

    result = server.add_inventory("Amoxicillin", 30)

    assert result == {"medicine": "Amoxicillin", "stock": 30}
    assert server.inventory["Amoxicillin"] == 30


@pytest.mark.parametrize("quantity", [0, -5])
def test_invalid_quantity(
    monkeypatch: pytest.MonkeyPatch,
    quantity: int,
) -> None:
    """Zero or negative quantities are rejected."""
    authenticate(monkeypatch, ["pharmacy:write"])

    result = server.add_inventory("Ibuprofen", quantity)

    assert result == {"error": "Quantity must be greater than zero"}
    assert server.inventory["Ibuprofen"] == 40


def test_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request without a token is unauthorized."""
    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {},
    )

    result = server.view_inventory()

    assert result == {"error": "unauthorized"}


def test_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed JWT is rejected."""
    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {"authorization": "Bearer invalid-token"},
    )

    result = server.add_inventory("Ibuprofen", 10)

    assert result == {"error": "unauthorized"}


def test_missing_read_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Viewing stock requires the pharmacy read scope."""
    authenticate(monkeypatch, ["pharmacy:write"])

    result = server.view_inventory()

    assert result == {"error": "unauthorized"}


def test_missing_write_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Updating stock requires the pharmacy write scope."""
    authenticate(monkeypatch, ["pharmacy:read"])

    result = server.add_inventory("Ibuprofen", 10)

    assert result == {"error": "unauthorized"}


def test_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """An expired JWT cannot access pharmacy inventory."""
    token = jwt.encode(
        {
            "sub": "user-a",
            "email": "user-a@example.com",
            "scopes": ["pharmacy:read"],
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

    result = server.view_inventory()

    assert result == {"error": "unauthorized"}
