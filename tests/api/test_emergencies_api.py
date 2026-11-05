"""GET /api/v1/emergencies lists flagged messages newest first, built from the runtime."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from clinic_assistant.api.emergencies import get_flags_repository, router
from clinic_assistant.repository.emergencies import EmergencyFlag, EmergencyFlagsRepository

CONVERSATION = uuid4()
FLAG = EmergencyFlag(
    id=3,
    conversation_id=CONVERSATION,
    message="I have chest pain",
    created_at=datetime(2026, 11, 3, 9, 0, tzinfo=UTC),
)


class FakeFlags(EmergencyFlagsRepository):
    def __init__(self) -> None:
        super().__init__(cast(Any, None))  # never queried: list_recent() is overridden
        self.limits: list[int] = []

    async def list_recent(self, limit: int = 50) -> list[EmergencyFlag]:
        self.limits.append(limit)
        return [FLAG]


def client_with(flags: FakeFlags) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_flags_repository] = lambda: flags
    return TestClient(app)


def test_lists_flags_for_staff() -> None:
    flags = FakeFlags()

    response = client_with(flags).get("/api/v1/emergencies?limit=10")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 3,
            "conversation_id": str(CONVERSATION),
            "message": "I have chest pain",
            "created_at": "2026-11-03T09:00:00Z",
        }
    ]
    assert flags.limits == [10]


def test_limit_is_validated() -> None:
    assert client_with(FakeFlags()).get("/api/v1/emergencies?limit=0").status_code == 422


def test_unavailable_before_the_runtime_is_open() -> None:
    app = FastAPI()
    app.include_router(router)

    assert TestClient(app).get("/api/v1/emergencies").status_code == 503


def test_repository_is_built_from_the_runtime_pool() -> None:
    pool = object()
    runtime = SimpleNamespace(pool=pool)

    assert get_flags_repository(cast(Any, runtime)).pool is pool
