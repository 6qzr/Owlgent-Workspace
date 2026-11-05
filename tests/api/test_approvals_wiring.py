"""The approvals routes are registered and build their service from the runtime."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from clinic_assistant.agent.graph import build_graph
from clinic_assistant.api.approvals import get_approval_service
from clinic_assistant.llm import FakeLLM
from clinic_assistant.main import create_app
from clinic_assistant.repository.approvals import ApprovalsRepository
from clinic_assistant.runtime import Runtime
from clinic_assistant.services.approval import ApprovalService

PENDING = [{"id": 1, "conversation_id": "c-1", "booking_id": 7, "action": "cancel"}]


class FakeApprovals(ApprovalsRepository):
    """Returns a fixed pending list instead of querying PostgreSQL."""

    def __init__(self) -> None:
        super().__init__(cast(Any, None))  # never queried: list_pending() is overridden

    async def list_pending(self) -> list[dict[str, Any]]:
        return PENDING


@asynccontextmanager
async def fake_runtime() -> AsyncIterator[Runtime]:
    yield Runtime(graph=build_graph(FakeLLM(), InMemorySaver()), pool=cast(Any, None))


def test_service_is_built_from_the_runtime() -> None:
    runtime = Runtime(graph=build_graph(FakeLLM(), InMemorySaver()), pool=cast(Any, None))
    service = get_approval_service(runtime)

    assert isinstance(service, ApprovalService)


def test_approvals_route_is_registered() -> None:
    app = create_app(fake_runtime)
    graph = build_graph(FakeLLM(), InMemorySaver())
    app.dependency_overrides[get_approval_service] = lambda: ApprovalService(FakeApprovals(), graph)

    with TestClient(app) as client:
        response = client.get("/api/v1/approvals")

    assert response.status_code == 200
    assert response.json() == PENDING


def test_approvals_are_unavailable_before_the_runtime_is_open() -> None:
    # No `with`: the lifespan never runs, so there is no runtime yet.
    response = TestClient(create_app(fake_runtime)).get("/api/v1/approvals")

    assert response.status_code == 503
