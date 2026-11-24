"""Google sign-in: build the login URL, then trade the code for the user's sub and email."""

import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from api.config import (
    GOOGLE_AUTH_URL,
    GOOGLE_SCOPES,
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
    Settings,
)


class GoogleAuthError(Exception):
    """Google could not be reached or did not confirm who the user is."""


@dataclass(frozen=True)
class GoogleUser:
    """The identity Google vouches for."""

    sub: str
    email: str


def new_state() -> str:
    """Return a random, unguessable OAuth state value."""
    return secrets.token_urlsafe(32)


def build_login_url(settings: Settings, state: str) -> str:
    """Return Google's consent-screen URL for this client and state."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def fetch_google_user(code: str, settings: Settings, client: httpx.AsyncClient) -> GoogleUser:
    """Exchange the authorization code at Google and read the user's sub and email."""
    token_data = await _call_google(
        client,
        "POST",
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.oauth_redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str):
        raise GoogleAuthError("Google's token response has no access_token")

    userinfo = await _call_google(
        client,
        "GET",
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    sub = userinfo.get("sub")
    email = userinfo.get("email")
    if not isinstance(sub, str) or not isinstance(email, str):
        raise GoogleAuthError("Google's userinfo response has no sub or email")
    return GoogleUser(sub=sub, email=email)


async def _call_google(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
) -> dict[str, Any]:
    """Make one request to Google; turn every failure into GoogleAuthError."""
    try:
        response = await client.request(method, url, **kwargs)
    except httpx.TimeoutException as error:
        raise GoogleAuthError(f"Google timed out ({url})") from error
    except httpx.HTTPError as error:
        raise GoogleAuthError(f"Could not reach Google ({url})") from error

    if response.status_code != httpx.codes.OK:
        raise GoogleAuthError(f"Google answered {response.status_code} ({url})")
    try:
        body = response.json()
    except ValueError as error:
        raise GoogleAuthError(f"Google sent a response that is not JSON ({url})") from error
    if not isinstance(body, dict):
        raise GoogleAuthError(f"Google sent an unexpected response ({url})")
    return body
