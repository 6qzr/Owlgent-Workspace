from typing import Any

from fastapi.testclient import TestClient

from clinic_assistant.main import create_app


class FakeConnection:
    """Simulate a database connection."""

    async def execute(self, query: str) -> None:
        assert query == "SELECT 1"


class FakeConnectionContext:
    """Simulate the pool connection context manager."""

    async def __aenter__(self) -> FakeConnection:
        return FakeConnection()

    async def __aexit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        return None


class FakePool:
    """Simulate a working or failing database pool."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def open(self, wait: bool = False) -> None:
        pass

    async def close(self) -> None:
        pass

    def connection(self) -> FakeConnectionContext:
        if self.should_fail:
            raise RuntimeError("Database unavailable")

        return FakeConnectionContext()


def test_health_returns_200_with_working_pool() -> None:
    with TestClient(create_app(pool=FakePool())) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}


def test_health_returns_503_with_failing_pool() -> None:
    with TestClient(create_app(pool=FakePool(should_fail=True))) as client:
        response = client.get("/health")

        assert response.status_code == 503
        assert response.json() == {
            "detail": {
                "status": "degraded",
                "database": "unreachable",
            }
        }
