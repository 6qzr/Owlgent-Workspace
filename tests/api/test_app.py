"""The app factory builds a working FastAPI app and manages the injected runtime."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from psycopg import AsyncConnection
from psycopg.rows import DictRow
from psycopg_pool import AsyncConnectionPool

from clinic_assistant.agent.graph import build_graph
from clinic_assistant.llm import FakeLLM
from clinic_assistant.main import APP_TITLE, Runtime, create_app


class FakeRuntime:
    """Builds an in-memory runtime and records whether it was closed."""

    def __init__(self) -> None:
        # Never opened, so no database is needed; these tests don't query it.
        pool = AsyncConnectionPool("", connection_class=AsyncConnection[DictRow], open=False)
        self.runtime = Runtime(graph=build_graph(FakeLLM(), InMemorySaver()), pool=pool)
        self.closed = False

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[Runtime]:
        try:
            yield self.runtime
        finally:
            self.closed = True


def test_openapi_schema_is_served() -> None:
    # Deliberately no `with`: the lifespan does not run, so no database is needed.
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == APP_TITLE


def test_lifespan_exposes_runtime_graph() -> None:
    fake = FakeRuntime()

    with TestClient(create_app(fake)) as client:
        assert client.app.state.runtime is fake.runtime  # type: ignore[attr-defined]  # TestClient.app is typed as a plain ASGI app


def test_lifespan_closes_runtime_on_shutdown() -> None:
    fake = FakeRuntime()

    with TestClient(create_app(fake)):
        assert not fake.closed

    assert fake.closed


def test_health_still_served_with_runtime() -> None:
    with TestClient(create_app(FakeRuntime())) as client:
        response = client.get("/health")

    assert response.status_code == 200
