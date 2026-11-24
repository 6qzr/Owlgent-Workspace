"""Routes for /auth/login and /auth/callback: sign in with Google, get a JWT back."""

import logging
import secrets
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from api.config import STATE_COOKIE_MAX_AGE_SECONDS, STATE_COOKIE_NAME, USER_SCOPES, Settings
from api.google_oauth import (
    GoogleAuthError,
    build_login_url,
    fetch_google_user,
    new_state,
)
from api.tokens import create_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def get_settings(request: Request) -> Settings:
    """Return the settings loaded when the app was created."""
    settings: Settings = request.app.state.settings
    return settings


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared HTTP client used to call Google."""
    client: httpx.AsyncClient = request.app.state.http_client
    return client


SettingsDep = Annotated[Settings, Depends(get_settings)]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


@router.get("/login")
def login(settings: SettingsDep) -> RedirectResponse:
    """Send the browser to Google's sign-in page, remembering the state in a cookie."""
    state = new_state()
    response = RedirectResponse(build_login_url(settings, state))
    response.set_cookie(
        STATE_COOKIE_NAME,
        state,
        max_age=STATE_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=settings.oauth_redirect_uri.startswith("https://"),
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
    response: Response,
    settings: SettingsDep,
    client: HttpClientDep,
    code: str | None = None,
    state: str | None = None,
) -> dict[str, str]:
    """Check the state, ask Google who signed in, and return a signed JWT."""
    expected_state = request.cookies.get(STATE_COOKIE_NAME)
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        raise HTTPException(
            status_code=400, detail="Invalid OAuth state. Start again at /auth/login."
        )
    if not code:
        raise HTTPException(
            status_code=400, detail="Google sent no code. Start again at /auth/login."
        )

    try:
        user = await fetch_google_user(code, settings, client)
    except GoogleAuthError as error:
        logger.warning("Google sign-in failed: %s", error)
        raise HTTPException(status_code=502, detail="Google sign-in failed. Try again.") from error

    # The state is single-use: clear it so the same callback URL can't be replayed.
    response.delete_cookie(STATE_COOKIE_NAME)
    token = create_token(user.sub, user.email, USER_SCOPES)
    return {"access_token": token, "token_type": "bearer"}
