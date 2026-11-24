"""FastAPI dependencies: the objects create_app puts on app.state, and the signed-in user."""

from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, Request

from api.config import CHAT_REQUIRED_SCOPE, Settings
from api.llm import LLM
from api.tokens import Unauthorized, token_from_header, verify_token


def get_settings(request: Request) -> Settings:
    """Return the settings loaded when the app was created."""
    settings: Settings = request.app.state.settings
    return settings


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared HTTP client used to call Google."""
    client: httpx.AsyncClient = request.app.state.http_client
    return client


def get_llm(request: Request) -> LLM:
    """Return the chat model the app was created with."""
    llm: LLM = request.app.state.llm
    return llm


def get_user_token(authorization: Annotated[str | None, Header()] = None) -> str:
    """Return the caller's JWT if it is valid; otherwise answer 401."""
    token = token_from_header(authorization)
    try:
        if token is None:
            raise Unauthorized("missing token")
        verify_token(token, CHAT_REQUIRED_SCOPE)
    except Unauthorized as error:
        raise HTTPException(
            status_code=401,
            detail="Sign in at /auth/login, then send Authorization: Bearer <token>.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    return token


SettingsDep = Annotated[Settings, Depends(get_settings)]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
LLMDep = Annotated[LLM, Depends(get_llm)]
UserTokenDep = Annotated[str, Depends(get_user_token)]
