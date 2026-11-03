"""Application factory: creates the FastAPI app and wires dependencies at start-up."""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Protocol

from fastapi import FastAPI

from clinic_assistant import __version__
from clinic_assistant.api import health
from clinic_assistant.config import get_settings
from clinic_assistant.repository.db import create_pool


class DatabaseConnection(Protocol):
    """Operations required from a database connection."""

    async def execute(self, query: str) -> Any: ...


class DatabasePool(Protocol):
    """Operations required from the application database pool."""

    async def open(self, wait: bool = False) -> None: ...

    async def close(self) -> None: ...

    def connection(self) -> AbstractAsyncContextManager[DatabaseConnection]: ...


APP_TITLE = "Clinic Front-Desk Assistant"


def create_app(pool: DatabasePool | None = None) -> FastAPI:
    """Create the FastAPI app and manage the database pool lifecycle."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app_pool = create_pool(get_settings()) if pool is None else pool

        try:
            await app_pool.open(wait=True)
            app.state.pool = app_pool
            yield
        finally:
            await app_pool.close()

    app = FastAPI(
        title=APP_TITLE,
        version=__version__,
        lifespan=lifespan,
    )

    app.include_router(health.router)

    return app


app = create_app()
