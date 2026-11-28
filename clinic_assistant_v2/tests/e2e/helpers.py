"""Helpers for the end-to-end tests: call a real MCP tool, chat through the real API, and a
keyword embedder that stands in for OpenAI embeddings."""

import json
import math
import zlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import httpx2
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import TextContent

from api.llm import FakeLLM, LLMReply, Message, ToolCall, ToolSpec
from api.main import create_app

VECTOR_SIZE = 1536

# Each group of words is one dimension of the fake embedding, so texts about the same
# topic point the same way. Enough topics to tell the three clinic PDFs apart.
KEYWORD_GROUPS = [
    ["doctor", "dr."],
    ["skin", "dermatolog"],
    ["dentist", "dental"],
    ["child", "pediatric"],
    ["parking"],
    ["pharmacy"],
    ["cancel"],
    ["book"],
    ["laboratory", "blood"],
]


def keyword_vector(text: str) -> list[float]:
    """Embed text as keyword-group counts, normalised, so cosine similarity means topic overlap."""
    lowered = text.lower()
    vector = [0.0] * VECTOR_SIZE
    for index, words in enumerate(KEYWORD_GROUPS):
        vector[index] = float(sum(lowered.count(word) for word in words))
    # A small text-specific direction: never a zero vector (cosine can't handle one), and two
    # texts with no topic words in common don't look identical.
    vector[len(KEYWORD_GROUPS) + zlib.crc32(lowered.encode()) % 1000] = 0.1
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector]


def keyword_embedder(chunks: list[str]) -> list[list[float]]:
    """Embed every chunk with keyword_vector, as ingestion's embedder would."""
    return [keyword_vector(chunk) for chunk in chunks]


class FakeOpenAI:
    """Just enough of the OpenAI client for the knowledge server: embeddings.create()."""

    def __init__(self) -> None:
        """Expose embeddings.create like the real client."""
        self.embeddings = SimpleNamespace(create=self.create_embedding)

    def create_embedding(self, model: str, input: str, **_: Any) -> SimpleNamespace:
        """Return one keyword embedding for the query, shaped like OpenAI's response."""
        return SimpleNamespace(data=[SimpleNamespace(embedding=keyword_vector(input))])


async def call_tool(
    url: str, name: str, arguments: dict[str, Any] | None = None, token: str | None = None
) -> Any:
    """Call one tool on a real MCP server, as the API would, and return its JSON result."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with Client(StreamableHttpTransport(url, headers=headers), timeout=10) as client:
        result = await client.call_tool(name, arguments or {}, raise_on_error=False)
    text = "".join(block.text for block in result.content if isinstance(block, TextContent))
    # An empty list has no text content, only structured data.
    return json.loads(text) if text else result.data


async def list_tools(url: str) -> list[Any]:
    """List the tools a real MCP server offers."""
    async with Client(StreamableHttpTransport(url), timeout=10) as client:
        tools: list[Any] = await client.list_tools()
    return tools


@asynccontextmanager
async def api_client(llm: Any) -> AsyncIterator[httpx2.AsyncClient]:
    """Run the real API in-process with the given fake LLM, and yield an HTTP client for it."""
    app = create_app(llm=llm)
    transport = httpx2.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        yield client


async def chat(llm: Any, message: str, token: str) -> str:
    """Send one chat message through the real API and return the reply text."""
    async with api_client(llm) as client:
        response = await client.post(
            "/chat", json={"message": message}, headers={"Authorization": f"Bearer {token}"}
        )
    response.raise_for_status()
    return str(response.json()["reply"])


def tool_call(name: str, call_id: str = "call-1", **arguments: Any) -> LLMReply:
    """A scripted model reply that asks for one tool."""
    return LLMReply(content="", tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)])


def tool_results(llm: FakeLLM) -> list[str]:
    """Every tool result the model was shown during the chat."""
    return [
        str(message["content"])
        for messages, _ in llm.calls
        for message in messages
        if message["role"] == "tool"
    ]


class RelayLLM:
    """A fake model that calls one tool, then answers by quoting what the tool returned.

    Unlike a scripted reply, the final answer really comes from the MCP server, so a test can
    check the patient sees their own data."""

    def __init__(self, tool_name: str) -> None:
        """Remember which tool to call first."""
        self._tool_name = tool_name
        self.calls: list[list[Message]] = []

    async def complete(self, messages: list[Message], tools: list[ToolSpec]) -> LLMReply:
        """First ask for the tool; once its result is in, answer with it."""
        self.calls.append(list(messages))
        if messages[-1]["role"] != "tool":
            return tool_call(self._tool_name)
        result = json.loads(messages[-1]["content"])
        if "error" in result:
            return LLMReply(content=f"Sorry, I couldn't get that: {result['error']}.")
        return LLMReply(
            content=f"Your last medical record is from {result['date']}: "
            f"{result['diagnosis']} ({result['notes']})."
        )
