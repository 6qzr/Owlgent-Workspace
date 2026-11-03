"""Conversation routes: status codes, validation and error mapping, with a stub service."""

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from clinic_assistant.api.conversations import MAX_MESSAGE_CHARS, get_conversation_service
from clinic_assistant.llm import LLMError
from clinic_assistant.main import create_app
from clinic_assistant.services.conversation import (
    AwaitingApproval,
    ConversationNotFound,
    ConversationView,
    DatabaseUnavailable,
    HistoryMessage,
    TurnResult,
    TurnStatus,
)

CONVERSATION_ID = uuid4()
URL = f"/api/v1/conversations/{CONVERSATION_ID}"
LEAKED_TEXT = "internal detail"


class StubService:
    """Returns fixed results, or raises `error` from every method."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sent: list[str] = []

    async def create_conversation(self) -> UUID:
        self._fail()
        return CONVERSATION_ID

    async def send_message(self, conversation_id: UUID, text: str) -> TurnResult:
        self._fail()
        self.sent.append(text)
        return TurnResult(TurnStatus.ANSWERED, reply="8 to 4.", sources=["hours.md"])

    async def get_conversation(self, conversation_id: UUID) -> ConversationView:
        self._fail()
        return ConversationView([HistoryMessage("patient", "Hours?")], TurnStatus.ANSWERED)

    def _fail(self) -> None:
        if self.error is not None:
            raise self.error


@pytest.fixture
def stub() -> StubService:
    return StubService()


@pytest.fixture
async def client(stub: StubService) -> AsyncIterator[AsyncClient]:
    """Client on an app whose service is the stub; no lifespan, so no database."""
    app = create_app()
    app.dependency_overrides[get_conversation_service] = lambda: stub
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as http:
        yield http


async def test_create_returns_201_with_id(client: AsyncClient) -> None:
    response = await client.post("/api/v1/conversations")

    assert response.status_code == 201
    assert response.json() == {"conversation_id": str(CONVERSATION_ID)}


async def test_send_returns_the_turn(client: AsyncClient, stub: StubService) -> None:
    response = await client.post(f"{URL}/messages", json={"message": "  Hours?  "})

    assert response.status_code == 200
    assert response.json() == {
        "reply": "8 to 4.",
        "status": "answered",
        "sources": ["hours.md"],
        "approval_id": None,
    }
    assert stub.sent == ["Hours?"]


async def test_get_returns_history(client: AsyncClient) -> None:
    response = await client.get(URL)

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": str(CONVERSATION_ID),
        "status": "answered",
        "messages": [{"role": "patient", "content": "Hours?"}],
    }


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ConversationNotFound(LEAKED_TEXT), 404),
        (AwaitingApproval(LEAKED_TEXT), 409),
        (LLMError(LEAKED_TEXT), 502),
        (DatabaseUnavailable(LEAKED_TEXT), 503),
    ],
)
async def test_send_maps_service_errors(
    client: AsyncClient, stub: StubService, error: Exception, status: int
) -> None:
    stub.error = error

    response = await client.post(f"{URL}/messages", json={"message": "Hi"})

    assert response.status_code == status
    assert LEAKED_TEXT not in response.json()["detail"]  # fixed text, never the exception message


@pytest.mark.parametrize(
    ("error", "status"),
    [(ConversationNotFound(LEAKED_TEXT), 404), (DatabaseUnavailable(LEAKED_TEXT), 503)],
)
async def test_get_and_create_map_service_errors(
    client: AsyncClient, stub: StubService, error: Exception, status: int
) -> None:
    stub.error = error

    assert (await client.get(URL)).status_code == status
    if isinstance(error, DatabaseUnavailable):
        assert (await client.post("/api/v1/conversations")).status_code == 503


@pytest.mark.parametrize(
    "body",
    [None, {}, {"message": ""}, {"message": "   "}, {"message": "a" * (MAX_MESSAGE_CHARS + 1)}],
)
async def test_invalid_message_is_422(client: AsyncClient, body: object) -> None:
    response = await client.post(f"{URL}/messages", json=body)

    assert response.status_code == 422


async def test_malformed_id_is_422(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/conversations/not-a-uuid")).status_code == 422
    response = await client.post(
        "/api/v1/conversations/not-a-uuid/messages", json={"message": "Hi"}
    )
    assert response.status_code == 422


async def test_service_unavailable_before_start_up() -> None:
    # No override and no lifespan: app.state.runtime was never set.
    async with AsyncClient(transport=ASGITransport(create_app()), base_url="http://test") as http:
        assert (await http.post("/api/v1/conversations")).status_code == 503
