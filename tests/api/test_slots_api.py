"""Test Issue #14 slots API."""

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg_pool import AsyncConnectionPool

from clinic_assistant.api.slots import router
from clinic_assistant.repository.slots import SlotsRepository


def make_client() -> TestClient:
    """Create a test app with the slots API."""

    app = FastAPI()
    app.include_router(router)

    # Provide a repository without a real database.
    pool = cast(AsyncConnectionPool, MagicMock())
    app.state.slots_repository = SlotsRepository(pool)

    return TestClient(app)


def test_get_slots_by_specialty() -> None:
    """Return available Dentistry appointments."""

    with patch.object(
        SlotsRepository,
        "find_free_slots",
        new_callable=AsyncMock,
    ) as find_free_slots:
        find_free_slots.return_value = [
            {
                "id": 1,
                "doctor_id": 3,
                "doctor_name": "Dr. Sara",
                "specialty": "Dentistry",
                "starts_at": datetime(2026, 11, 10, 9, 0, tzinfo=UTC),
                "ends_at": datetime(2026, 11, 10, 9, 30, tzinfo=UTC),
            }
        ]

        client = make_client()

        response = client.get("/api/v1/slots?specialty=Dentistry")

        assert response.status_code == 200

        slots = response.json()

        assert len(slots) == 1
        assert slots[0]["doctor_name"] == "Dr. Sara"
        assert slots[0]["specialty"] == "Dentistry"

        find_free_slots.assert_awaited_once_with(
            doctor_id=None,
            doctor_name=None,
            specialty="Dentistry",
            booking_date=None,
        )


def test_get_slots_with_all_filters() -> None:
    """Accept doctor, specialty and date filters."""

    with patch.object(
        SlotsRepository,
        "find_free_slots",
        new_callable=AsyncMock,
    ) as find_free_slots:
        find_free_slots.return_value = []

        client = make_client()

        response = client.get(
            "/api/v1/slots",
            params={
                "doctor_id": "3",
                "doctor_name": "Dr. Sara",
                "specialty": "Dentistry",
                "date": "2026-11-10",
            },
        )

        assert response.status_code == 200
        assert response.json() == []

        find_free_slots.assert_awaited_once()


@pytest.mark.parametrize(
    "query",
    [
        "doctor_id=-1",
        "doctor_id=abc",
        "date=wrong-date",
        "specialty=",
        "doctor_name=",
    ],
)
def test_invalid_filters_return_422(query: str) -> None:
    """Invalid query parameters should return HTTP 422."""

    client = make_client()

    response = client.get(f"/api/v1/slots?{query}")

    assert response.status_code == 422


def test_no_slots_returns_empty_list() -> None:
    """Return an empty list when nothing is available."""

    with patch.object(
        SlotsRepository,
        "find_free_slots",
        new_callable=AsyncMock,
    ) as find_free_slots:
        find_free_slots.return_value = []

        client = make_client()

        response = client.get("/api/v1/slots?specialty=Dentistry")

        assert response.status_code == 200
        assert response.json() == []


def test_missing_repository_returns_503() -> None:
    """Report an unavailable service when startup wiring is missing."""

    app = FastAPI()
    app.include_router(router)

    client = TestClient(app)

    response = client.get("/api/v1/slots")

    assert response.status_code == 503
