"""Build the FastAPI app. Run with: uvicorn api.main:create_app --factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from api.auth_routes import router as auth_router
from api.chat_routes import router as chat_router
from api.config import GOOGLE_TIMEOUT_SECONDS, LLM_TIMEOUT_SECONDS, load_settings
from api.llm import LLM, OpenAILLM
from api.tokens import get_jwt_secret


def create_app(
    transport: httpx.AsyncBaseTransport | None = None, llm: LLM | None = None
) -> FastAPI:
    """Create the app; fail fast on bad settings. Tests pass a fake Google and a FakeLLM."""
    settings = load_settings()
    get_jwt_secret()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Open one HTTP client, with a timeout, for the app's lifetime."""
        async with httpx.AsyncClient(timeout=GOOGLE_TIMEOUT_SECONDS, transport=transport) as client:
            app.state.http_client = client
            yield

    app = FastAPI(title="Clinic Assistant v2", lifespan=lifespan)
    app.state.settings = settings
    app.state.llm = llm or OpenAILLM(
        settings.openai_api_key, settings.chat_model, LLM_TIMEOUT_SECONDS
    )
    app.include_router(auth_router)
    app.include_router(chat_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Tell docker compose the API is up."""
        return {"status": "ok"}

    return app
