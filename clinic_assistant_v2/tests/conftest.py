"""Shared test setup: one known JWT secret, and a factory for signed test tokens."""

from collections.abc import Callable

import pytest

from auth_reference.tokens import create_token

# Long enough for the 32-byte rule; a fake value made only for tests.
TEST_SECRET = "test-secret-that-is-long-enough-for-hs256-signing"

ALL_SCOPES = [
    "appointments:read",
    "appointments:write",
    "pharmacy:read",
    "pharmacy:write",
    "records:read",
    "docs:read",
]

TokenFactory = Callable[..., str]


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sign and verify every test token with the same known secret."""
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)


@pytest.fixture
def make_token() -> TokenFactory:
    """Return a function that signs a test token for a user, with all scopes by default."""

    def make(sub: str, scopes: list[str] | None = None) -> str:
        """Sign a token for this test user."""
        return create_token(sub, f"{sub}@example.com", ALL_SCOPES if scopes is None else scopes)

    return make
