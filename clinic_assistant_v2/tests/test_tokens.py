"""Tests for the shared JWT helpers: every rejection case in the contract, and the happy path."""

import time

import jwt
import pytest

from auth_reference.tokens import (
    ALGORITHM,
    Unauthorized,
    create_token,
    token_from_header,
    verify_token,
)

TEST_SECRET = "test-secret-that-is-long-enough-for-hs256-signing"
OTHER_SECRET = "another-secret-that-is-also-long-enough-for-hs256"


@pytest.fixture(autouse=True)
def jwt_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every test the same known secret and the default token lifetime."""
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.delenv("TOKEN_TTL_SECONDS", raising=False)


def make_raw_token(claims: dict[str, object], secret: str = TEST_SECRET) -> str:
    """Sign arbitrary claims, to build the bad tokens create_token would never make."""
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def test_create_token_has_exactly_the_contract_claims() -> None:
    """The token carries sub, email, scopes and exp, and nothing else."""
    token = create_token("user-a", "a@example.com", ["records:read"])

    claims = jwt.decode(token, TEST_SECRET, algorithms=[ALGORITHM])

    assert set(claims) == {"sub", "email", "scopes", "exp"}
    assert claims["sub"] == "user-a"
    assert claims["email"] == "a@example.com"
    assert claims["scopes"] == ["records:read"]


def test_create_token_expires_after_one_hour_by_default() -> None:
    """exp is now + 3600 seconds when TOKEN_TTL_SECONDS is not set."""
    before = int(time.time())

    claims = jwt.decode(create_token("user-a", "a@example.com", []), TEST_SECRET, [ALGORITHM])

    assert before + 3600 <= claims["exp"] <= int(time.time()) + 3600


def test_create_token_uses_token_ttl_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """TOKEN_TTL_SECONDS changes the lifetime."""
    monkeypatch.setenv("TOKEN_TTL_SECONDS", "60")
    before = int(time.time())

    claims = jwt.decode(create_token("user-a", "a@example.com", []), TEST_SECRET, [ALGORITHM])

    assert before + 60 <= claims["exp"] <= int(time.time()) + 60


def test_verify_token_returns_claims_for_a_valid_token() -> None:
    """A valid token with the needed scope gives back its claims."""
    token = create_token("user-a", "a@example.com", ["records:read"])

    claims = verify_token(token, "records:read")

    assert claims["sub"] == "user-a"


@pytest.mark.parametrize("token", [None, ""])
def test_verify_token_rejects_a_missing_token(token: str | None) -> None:
    """No token at all is unauthorized."""
    with pytest.raises(Unauthorized, match="missing token"):
        verify_token(token, "records:read")


def test_verify_token_rejects_a_malformed_token() -> None:
    """Something that is not a JWT is unauthorized."""
    with pytest.raises(Unauthorized, match="invalid token"):
        verify_token("not-a-jwt", "records:read")


def test_verify_token_rejects_a_wrong_signature() -> None:
    """A token signed with another secret is unauthorized."""
    claims = {"sub": "user-a", "email": "a@x.com", "scopes": ["records:read"], "exp": 9999999999}
    token = make_raw_token(claims, secret=OTHER_SECRET)

    with pytest.raises(Unauthorized, match="invalid token"):
        verify_token(token, "records:read")


def test_verify_token_rejects_an_expired_token() -> None:
    """A token whose exp is in the past is unauthorized."""
    claims = {"sub": "user-a", "email": "a@x.com", "scopes": ["records:read"], "exp": 1}
    token = make_raw_token(claims)

    with pytest.raises(Unauthorized, match="expired"):
        verify_token(token, "records:read")


def test_verify_token_rejects_a_missing_scope() -> None:
    """A valid token without the scope the tool needs is unauthorized."""
    token = create_token("user-a", "a@example.com", ["records:read"])

    with pytest.raises(Unauthorized, match="missing scope appointments:write"):
        verify_token(token, "appointments:write")


def test_verify_token_rejects_a_token_without_required_claims() -> None:
    """A signed token that lacks sub, email or scopes is unauthorized."""
    token = make_raw_token({"sub": "user-a", "exp": 9999999999})

    with pytest.raises(Unauthorized, match="invalid token"):
        verify_token(token, "records:read")


def test_missing_jwt_secret_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without JWT_SECRET, the code stops with a clear message instead of signing with nothing."""
    monkeypatch.delenv("JWT_SECRET")

    with pytest.raises(RuntimeError, match="JWT_SECRET is not set"):
        create_token("user-a", "a@example.com", [])


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Bearer abc.def.ghi", "abc.def.ghi"),
        ("bearer abc.def.ghi", None),
        ("Basic abc", None),
        ("", None),
        (None, None),
    ],
)
def test_token_from_header(header: str | None, expected: str | None) -> None:
    """Only 'Bearer <token>' (capital B, one space) yields a token."""
    assert token_from_header(header) == expected
