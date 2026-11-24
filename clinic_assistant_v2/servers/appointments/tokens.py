"""Create and verify the clinic JWT. Every MCP server and the API copy this file unchanged."""

import os
import time
from typing import Any

import jwt

ALGORITHM = "HS256"
DEFAULT_TOKEN_TTL_SECONDS = 3600
REQUIRED_CLAIMS = ["sub", "email", "scopes", "exp"]
BEARER_PREFIX = "Bearer "


class Unauthorized(Exception):
    """A token is missing, malformed, badly signed, expired or lacks the scope a tool needs."""


def get_jwt_secret() -> str:
    """Return JWT_SECRET from the environment; fail fast with a clear message when it is unset."""
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set. Copy .env.example to .env and set it.")
    return secret


def get_token_ttl_seconds() -> int:
    """Return how long a new token lives, from TOKEN_TTL_SECONDS (default one hour)."""
    return int(os.environ.get("TOKEN_TTL_SECONDS", DEFAULT_TOKEN_TTL_SECONDS))


def create_token(sub: str, email: str, scopes: list[str]) -> str:
    """Sign a token with exactly the claims sub, email, scopes and exp."""
    claims = {
        "sub": sub,
        "email": email,
        "scopes": scopes,
        "exp": int(time.time()) + get_token_ttl_seconds(),
    }
    return jwt.encode(claims, get_jwt_secret(), algorithm=ALGORITHM)


def token_from_header(authorization: str | None) -> str | None:
    """Return the token from an 'Authorization: Bearer <jwt>' header value, or None."""
    if authorization is None or not authorization.startswith(BEARER_PREFIX):
        return None
    return authorization[len(BEARER_PREFIX) :].strip()


def verify_token(token: str | None, required_scope: str) -> dict[str, Any]:
    """Return the token's claims, or raise Unauthorized if the token or its scope is not valid."""
    if not token:
        raise Unauthorized("missing token")
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[ALGORITHM],
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError as error:
        raise Unauthorized("token expired") from error
    except jwt.InvalidTokenError as error:
        raise Unauthorized("invalid token") from error

    scopes = claims["scopes"]
    if not isinstance(scopes, list) or required_scope not in scopes:
        raise Unauthorized(f"missing scope {required_scope}")
    return claims
