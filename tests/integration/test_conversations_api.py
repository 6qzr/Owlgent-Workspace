"""Conversation routes end to end: httpx client, real PostgreSQL, FakeLLM."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from clinic_assistant.agent.graph import ConversationGraph, build_graph
from clinic_assistant.agent.nodes.classify import Classification
from clinic_assistant.domain import Intent
from clinic_assistant.llm import FakeLLM
from clinic_assistant.main import Runtime, create_app
from clinic_assistant.repository.db import DictPool

pytestmark = pytest.mark.integration

OTHER = Classification(intent=Intent.OTHER, confidence=0.9)

type ClientFactory = Callable[[ConversationGraph], AbstractAsyncContextManager[AsyncClient]]


@pytest.fixture
def client_for(pool: DictPool) -> ClientFactory:
    """Open a client on the real app, with its lifespan running around the given graph."""

    @asynccontextmanager
    async def open_client(graph: ConversationGraph) -> AsyncIterator[AsyncClient]:
        @asynccontextmanager
        async def runtime() -> AsyncIterator[Runtime]:
            yield Runtime(graph=graph, pool=pool)

        app = create_app(runtime)
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app), base_url="http://test") as client,
        ):
            yield client

    return open_client


async def test_conversation_round_trip(
    client_for: ClientFactory, saver: AsyncPostgresSaver
) -> None:
    async with client_for(build_graph(FakeLLM([OTHER, OTHER]), saver)) as client:
        created = await client.post("/api/v1/conversations")
        url = f"/api/v1/conversations/{created.json()['conversation_id']}"

        first = await client.post(f"{url}/messages", json={"message": "Hello"})
        second = await client.post(f"{url}/messages", json={"message": "Still there?"})
        history = await client.get(url)

    assert created.status_code == 201
    assert first.status_code == second.status_code == 200
    assert second.json()["status"] == "answered"
    assert [m["role"] for m in history.json()["messages"]] == ["patient", "assistant"] * 2


async def test_unknown_conversation_is_404(
    client_for: ClientFactory, saver: AsyncPostgresSaver
) -> None:
    url = f"/api/v1/conversations/{uuid4()}"
    async with client_for(build_graph(FakeLLM(), saver)) as client:
        assert (await client.get(url)).status_code == 404
        assert (await client.post(f"{url}/messages", json={"message": "Hi"})).status_code == 404


async def test_paused_conversation_is_409(
    client_for: ClientFactory, paused_graph: ConversationGraph
) -> None:
    async with client_for(paused_graph) as client:
        created = await client.post("/api/v1/conversations")
        url = f"/api/v1/conversations/{created.json()['conversation_id']}/messages"

        first = await client.post(url, json={"message": "Cancel booking 7"})
        second = await client.post(url, json={"message": "Any news?"})

    assert first.json()["status"] == "awaiting_approval"
    assert second.status_code == 409
