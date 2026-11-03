"""/health checks the shared pool from the runtime: 200 when the DB answers, 503 otherwise."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from clinic_assistant.agent.graph import build_graph
from clinic_assistant.llm import FakeLLM
from clinic_assistant.main import Runtime, RuntimeFactory, create_app
from clinic_assistant.repository.db import DictPool

UNREACHABLE = {"status": "degraded", "database": "unreachable"}


class FakeConnection:
    """Simulate a database connection."""

    async def execute(self, query: str) -> None:
        assert query == "SELECT 1"


class FakeConnectionContext:
    """Simulate the pool connection context manager."""

    async def __aenter__(self) -> FakeConnection:
        return FakeConnection()

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        return None


class FakePool:
    """Simulate a working or failing database pool."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def connection(self) -> FakeConnectionContext:
        if self.should_fail:
            raise RuntimeError("Database unavailable")
        return FakeConnectionContext()


def runtime_with(pool: FakePool) -> RuntimeFactory:
    """A runtime factory whose pool is the fake; the graph is never used by /health."""

    @asynccontextmanager
    async def factory() -> AsyncIterator[Runtime]:
        graph = build_graph(FakeLLM(), InMemorySaver())
        yield Runtime(graph=graph, pool=cast(DictPool, pool))

    return factory


def test_health_returns_200_with_working_pool() -> None:
    with TestClient(create_app(runtime_with(FakePool()))) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_returns_503_with_failing_pool() -> None:
    with TestClient(create_app(runtime_with(FakePool(should_fail=True)))) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == UNREACHABLE


def test_health_returns_503_before_the_runtime_is_open() -> None:
    # No `with`: the lifespan never runs, so there is no runtime yet.
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 503
    assert response.json() == UNREACHABLE
