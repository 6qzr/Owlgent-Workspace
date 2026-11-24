"""Offline tests for the Knowledge MCP server."""

from unittest.mock import MagicMock

import pytest

from servers.knowledge import server
from servers.knowledge.tokens import create_token

TEST_SECRET = "unit-test-secret-not-for-production"


@pytest.fixture(autouse=True)
def setup_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a safe test environment."""
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-tests")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("QDRANT_COLLECTION", "clinic_docs")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")


def authenticate(
    monkeypatch: pytest.MonkeyPatch,
    scopes: list[str],
) -> None:
    """Mock an Authorization header with a signed JWT."""
    token = create_token(
        sub="user-a",
        email="user-a@example.com",
        scopes=scopes,
    )

    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {"authorization": f"Bearer {token}"},
    )


def setup_fake_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, MagicMock]:
    """Replace OpenAI and Qdrant with fake clients."""
    fake_openai = MagicMock()
    fake_qdrant = MagicMock()

    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1] * 1536)]

    monkeypatch.setattr(
        server,
        "get_openai_client",
        lambda: fake_openai,
    )

    monkeypatch.setattr(
        server,
        "get_qdrant_client",
        lambda: fake_qdrant,
    )

    return fake_openai, fake_qdrant


def test_search_returns_matching_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return relevant chunks with their source and score."""
    authenticate(monkeypatch, ["docs:read"])
    fake_openai, fake_qdrant = setup_fake_clients(monkeypatch)

    hit = MagicMock()
    hit.payload = {
        "text": "Dr. Sara is a dermatologist.",
        "source": "doctors.pdf",
    }
    hit.score = 0.91

    fake_qdrant.query_points.return_value.points = [hit]

    result = server.search_clinic_docs("Which doctor sees skin problems?")

    assert result == [
        {
            "text": "Dr. Sara is a dermatologist.",
            "source": "doctors.pdf",
            "score": 0.91,
        }
    ]

    fake_openai.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input="Which doctor sees skin problems?",
        timeout=server.REQUEST_TIMEOUT_SECONDS,
    )

    fake_qdrant.query_points.assert_called_once_with(
        collection_name="clinic_docs",
        query=[0.1] * 1536,
        limit=3,
        score_threshold=0.3,
        with_payload=True,
        timeout=server.REQUEST_TIMEOUT_SECONDS,
    )


def test_no_matches_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A search with no matching chunks returns an empty list."""
    authenticate(monkeypatch, ["docs:read"])
    _, fake_qdrant = setup_fake_clients(monkeypatch)

    fake_qdrant.query_points.return_value.points = []

    result = server.search_clinic_docs("Do you sell car insurance?")

    assert result == []


def test_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requests without a JWT cannot search clinic documents."""
    monkeypatch.setattr(
        server,
        "get_http_headers",
        lambda include: {},
    )

    result = server.search_clinic_docs("Clinic opening hours")

    assert result == {"error": "unauthorized"}


def test_wrong_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """The docs:read scope is required to search documents."""
    authenticate(monkeypatch, ["pharmacy:read"])

    result = server.search_clinic_docs("Clinic opening hours")

    assert result == {"error": "unauthorized"}


def test_invalid_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    """The number of requested results must be positive."""
    authenticate(monkeypatch, ["docs:read"])

    result = server.search_clinic_docs("Clinic hours", top_k=0)

    assert result == {"error": "top_k must be greater than zero"}


def test_blank_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty question returns no results."""
    authenticate(monkeypatch, ["docs:read"])

    result = server.search_clinic_docs("   ")

    assert result == []


def test_openai_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenAI failures produce an error response."""
    authenticate(monkeypatch, ["docs:read"])
    fake_openai, _ = setup_fake_clients(monkeypatch)

    fake_openai.embeddings.create.side_effect = RuntimeError("Fake OpenAI failure")

    result = server.search_clinic_docs("Clinic hours")

    assert result == {"error": "retrieval failed: RuntimeError"}


def test_qdrant_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Qdrant failures produce an error response."""
    authenticate(monkeypatch, ["docs:read"])
    _, fake_qdrant = setup_fake_clients(monkeypatch)

    fake_qdrant.query_points.side_effect = RuntimeError("Fake Qdrant failure")

    result = server.search_clinic_docs("Clinic hours")

    assert result == {"error": "retrieval failed: RuntimeError"}


def test_custom_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    """Search uses the requested number of results."""
    authenticate(monkeypatch, ["docs:read"])
    _, fake_qdrant = setup_fake_clients(monkeypatch)

    fake_qdrant.query_points.return_value.points = []

    result = server.search_clinic_docs(
        "Clinic doctors",
        top_k=5,
    )

    assert result == []

    assert fake_qdrant.query_points.call_args.kwargs["limit"] == 5


def test_missing_payload_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Search skips Qdrant hits without document payloads."""
    authenticate(monkeypatch, ["docs:read"])
    _, fake_qdrant = setup_fake_clients(monkeypatch)

    hit = MagicMock()
    hit.payload = None
    hit.score = 0.8

    fake_qdrant.query_points.return_value.points = [hit]

    result = server.search_clinic_docs("Clinic hours")

    assert result == []
