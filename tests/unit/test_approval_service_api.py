"""Test approval service and API without PostgreSQL."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clinic_assistant.api.approvals import (
    get_approval_service,
    router,
)
from clinic_assistant.repository.approvals import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
)
from clinic_assistant.services.approval import ApprovalService


def make_service() -> tuple[ApprovalService, MagicMock, MagicMock]:
    """Build a service with fake dependencies."""

    # Create a fake repository.
    repository = MagicMock()
    repository.get_by_id = AsyncMock()
    repository.list_pending = AsyncMock()

    # Create a fake graph.
    graph = MagicMock()
    graph.ainvoke = AsyncMock()

    return ApprovalService(repository, graph), repository, graph


async def test_list_pending() -> None:
    """Service returns the pending queue."""

    service, repository, _ = make_service()

    repository.list_pending.return_value = [{"id": 1, "status": "pending"}]

    result = await service.list_pending()

    assert len(result) == 1
    assert result[0]["id"] == 1


@pytest.mark.parametrize("approved", [True, False])
async def test_resume_decision(approved: bool) -> None:
    """Test resuming with approval or rejection."""

    service, repository, graph = make_service()

    conversation_id = uuid4()

    status = "approved" if approved else "rejected"

    # First read is pending.
    # Second read is approved or rejected.
    repository.get_by_id.side_effect = [
        {
            "id": 1,
            "conversation_id": conversation_id,
            "status": "pending",
        },
        {
            "id": 1,
            "conversation_id": conversation_id,
            "status": status,
        },
    ]

    # Fake graph response after resuming.
    graph.ainvoke.return_value = {
        "decision": {
            "approved": approved,
            "reason": "Staff decision",
            "staff": "Receptionist",
        },
        "reply": "The decision was processed.",
    }

    # Staff approves or rejects.
    result = await service.decide(
        approval_id=1,
        approved=approved,
        reason="Staff decision",
        staff="Receptionist",
    )

    # Check the returned message.
    assert result["outcome"] == "The decision was processed."

    # Check that the graph resumed once.
    graph.ainvoke.assert_awaited_once()

    # Check that the correct conversation was resumed.
    _, kwargs = graph.ainvoke.await_args

    assert kwargs["config"]["configurable"]["thread_id"] == str(conversation_id)


async def test_unknown_approval() -> None:
    """Unknown approval should raise an error."""

    service, repository, graph = make_service()

    repository.get_by_id.return_value = None

    with pytest.raises(ApprovalNotFoundError):
        await service.decide(
            999,
            True,
            "Approved",
            "Staff",
        )

    graph.ainvoke.assert_not_awaited()


async def test_already_decided() -> None:
    """Decided approval must not resume again."""

    service, repository, graph = make_service()

    repository.get_by_id.return_value = {
        "id": 1,
        "status": "approved",
    }

    with pytest.raises(ApprovalAlreadyDecidedError):
        await service.decide(
            1,
            False,
            "Rejected",
            "Staff",
        )

    graph.ainvoke.assert_not_awaited()


def make_client(service: MagicMock) -> TestClient:
    """Build a small FastAPI app with a fake service."""

    app = FastAPI()

    # Add approval API routes.
    app.include_router(router)

    # Replace real service with fake service.
    app.dependency_overrides[get_approval_service] = lambda: service

    return TestClient(app)


def test_api_list_pending() -> None:
    """GET returns the staff approval queue."""

    service = MagicMock()

    service.list_pending = AsyncMock(return_value=[{"id": 1, "status": "pending"}])

    client = make_client(service)

    response = client.get("/api/v1/approvals?status=pending")

    assert response.status_code == 200
    assert response.json()[0]["id"] == 1


def test_api_unknown_approval() -> None:
    """POST returns 404 for an unknown approval."""

    service = MagicMock()

    service.decide = AsyncMock(side_effect=ApprovalNotFoundError())

    client = make_client(service)

    response = client.post(
        "/api/v1/approvals/999/decision",
        json={
            "approved": True,
            "reason": "Approved",
            "staff": "Receptionist",
        },
    )

    assert response.status_code == 404


def test_api_already_decided() -> None:
    """POST returns 409 for an already decided approval."""

    service = MagicMock()

    service.decide = AsyncMock(side_effect=ApprovalAlreadyDecidedError())

    client = make_client(service)

    response = client.post(
        "/api/v1/approvals/1/decision",
        json={
            "approved": False,
            "reason": "Rejected",
            "staff": "Receptionist",
        },
    )

    assert response.status_code == 409
