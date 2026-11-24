"""Tests for Google sign-in and JWT issuing. Google is faked with httpx.MockTransport."""

import logging
import time
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

import httpx
import httpx2
import jwt
import pytest
from fastapi.testclient import TestClient

from api.config import (
    GOOGLE_AUTH_URL,
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
    STATE_COOKIE_NAME,
    USER_SCOPES,
)
from api.main import create_app

TEST_SECRET = "test-secret-that-is-long-enough-for-hs256-signing"
REDIRECT_URI = "http://localhost:8000/auth/callback"
STATE = "known-test-state"

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def api_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every test fake Google settings and a known JWT secret."""
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", REDIRECT_URI)
    monkeypatch.delenv("TOKEN_TTL_SECONDS", raising=False)


def fake_google(
    token_response: httpx.Response | None = None,
    userinfo_response: httpx.Response | None = None,
) -> tuple[Handler, list[httpx.Request]]:
    """Return a fake Google that answers the token and userinfo calls, and its call log."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Answer like Google would, by URL."""
        calls.append(request)
        if str(request.url) == GOOGLE_TOKEN_URL:
            return token_response or httpx.Response(200, json={"access_token": "google-at"})
        if str(request.url) == GOOGLE_USERINFO_URL:
            return userinfo_response or httpx.Response(
                200, json={"sub": "google-sub-123", "email": "patient@example.com"}
            )
        return httpx.Response(404)

    return handler, calls


def make_client(handler: Handler) -> TestClient:
    """Build the app with the fake Google behind it."""
    return TestClient(create_app(transport=httpx.MockTransport(handler)))


def call_callback(
    client: TestClient, state: str = STATE, code: str = "the-code"
) -> httpx2.Response:
    """Call /auth/callback as the browser would, with the state cookie set at login."""
    client.cookies.set(STATE_COOKIE_NAME, STATE)
    response: httpx2.Response = client.get("/auth/callback", params={"code": code, "state": state})
    return response


def test_health() -> None:
    """GET /health answers ok for the compose healthcheck."""
    handler, _ = fake_google()
    with make_client(handler) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_redirects_to_google_with_state_cookie() -> None:
    """/auth/login sends the browser to Google and remembers the state in an httpOnly cookie."""
    handler, _ = fake_google()
    with make_client(handler) as client:
        response = client.get("/auth/login", follow_redirects=False)

    assert response.status_code == 307
    url = urlsplit(response.headers["location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == GOOGLE_AUTH_URL
    params = {key: values[0] for key, values in parse_qs(url.query).items()}
    assert params["client_id"] == "fake-client-id"
    assert params["redirect_uri"] == REDIRECT_URI
    assert params["response_type"] == "code"
    assert params["scope"] == "openid email"
    assert len(params["state"]) >= 32
    assert response.cookies[STATE_COOKIE_NAME] == params["state"]
    assert "httponly" in response.headers["set-cookie"].lower()


def test_login_state_is_different_every_time() -> None:
    """Each login gets a fresh random state."""
    handler, _ = fake_google()
    with make_client(handler) as client:
        first = client.get("/auth/login", follow_redirects=False).cookies[STATE_COOKIE_NAME]
        second = client.get("/auth/login", follow_redirects=False).cookies[STATE_COOKIE_NAME]

    assert first != second


def test_callback_returns_a_jwt_with_the_contract_claims() -> None:
    """A good callback returns a bearer JWT for Google's sub, with all six scopes and 1 h expiry."""
    handler, _ = fake_google()
    before = int(time.time())
    with make_client(handler) as client:
        response = call_callback(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    claims = jwt.decode(body["access_token"], TEST_SECRET, algorithms=["HS256"])
    assert set(claims) == {"sub", "email", "scopes", "exp"}
    assert claims["sub"] == "google-sub-123"
    assert claims["email"] == "patient@example.com"
    assert claims["scopes"] == USER_SCOPES
    assert before + 3600 <= claims["exp"] <= int(time.time()) + 3600
    # The single-use state cookie is cleared (expired) in the same response.
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f'{STATE_COOKIE_NAME}=""')
    assert "Max-Age=0" in set_cookie


def test_callback_sends_google_the_code_and_client_credentials() -> None:
    """The code exchange posts the code and client, then userinfo uses Google's access token."""
    handler, calls = fake_google()
    with make_client(handler) as client:
        call_callback(client, code="the-code")

    token_call, userinfo_call = calls
    form = parse_qs(token_call.content.decode())
    assert token_call.method == "POST"
    assert form["code"] == ["the-code"]
    assert form["client_id"] == ["fake-client-id"]
    assert form["client_secret"] == ["fake-client-secret"]
    assert form["redirect_uri"] == [REDIRECT_URI]
    assert form["grant_type"] == ["authorization_code"]
    assert userinfo_call.headers["authorization"] == "Bearer google-at"


def test_callback_rejects_a_state_that_does_not_match_the_cookie() -> None:
    """A forged or stale state is refused with 400, and Google is never called."""
    handler, calls = fake_google()
    with make_client(handler) as client:
        response = call_callback(client, state="some-other-state")

    assert response.status_code == 400
    assert "state" in response.json()["detail"]
    assert calls == []


def test_callback_rejects_a_missing_state_cookie() -> None:
    """Without the cookie from /auth/login, the callback is refused."""
    handler, calls = fake_google()
    with make_client(handler) as client:
        response = client.get("/auth/callback", params={"code": "c", "state": STATE})

    assert response.status_code == 400
    assert calls == []


def test_callback_without_a_code_is_refused() -> None:
    """If the user cancels at Google there is no code, so the answer is 400."""
    handler, calls = fake_google()
    with make_client(handler) as client:
        client.cookies.set(STATE_COOKIE_NAME, STATE)
        response = client.get("/auth/callback", params={"state": STATE, "error": "access_denied"})

    assert response.status_code == 400
    assert calls == []


def raise_timeout(request: httpx.Request) -> httpx.Response:
    """Act like Google never answers."""
    raise httpx.ReadTimeout("timed out", request=request)


def raise_connect_error(request: httpx.Request) -> httpx.Response:
    """Act like Google can't be reached."""
    raise httpx.ConnectError("no route", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        fake_google(token_response=httpx.Response(400, json={"error": "invalid_grant"}))[0],
        fake_google(token_response=httpx.Response(200, json={"no": "token"}))[0],
        fake_google(token_response=httpx.Response(200, text="not json"))[0],
        fake_google(userinfo_response=httpx.Response(500))[0],
        fake_google(userinfo_response=httpx.Response(200, json={"email": "x@example.com"}))[0],
        raise_timeout,
        raise_connect_error,
    ],
    ids=[
        "token-400",
        "token-missing",
        "token-not-json",
        "userinfo-500",
        "userinfo-no-sub",
        "timeout",
        "unreachable",
    ],
)
def test_google_failures_give_502_and_a_log_line(
    handler: Handler, caplog: pytest.LogCaptureFixture
) -> None:
    """Any Google failure is a clean 502 with a log line, never a stack trace or a token."""
    with caplog.at_level(logging.WARNING, logger="api.auth_routes"), make_client(handler) as client:
        response = call_callback(client)

    assert response.status_code == 502
    assert response.json() == {"detail": "Google sign-in failed. Try again."}
    assert "Google sign-in failed" in caplog.text


def test_missing_google_settings_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """The app refuses to start without its Google settings, naming the missing ones."""
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET")
    monkeypatch.delenv("OAUTH_REDIRECT_URI")

    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_SECRET, OAUTH_REDIRECT_URI"):
        create_app()


def test_placeholder_jwt_secret_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """The app refuses to start with the .env.example JWT secret."""
    monkeypatch.setenv("JWT_SECRET", "change-me")

    with pytest.raises(RuntimeError, match="placeholder"):
        create_app()
