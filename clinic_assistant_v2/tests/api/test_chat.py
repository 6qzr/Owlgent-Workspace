"""Tests for POST /chat and the agent. The LLM is a scripted FakeLLM; the MCP servers are the
contract stubs from tests/stub_servers.py, served over real HTTP on local ports."""

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import httpx2
import jwt
import pytest
from fastmcp.utilities.http import find_available_port
from fastmcp.utilities.tests import run_server_async

from api.config import MAX_AGENT_STEPS, STEP_LIMIT_REPLY, SYSTEM_PROMPT, USER_SCOPES
from api.llm import FakeLLM, LLMReply, LLMUnavailable, ToolCall
from api.main import create_app
from api.mcp_tools import UNAVAILABLE_RESULT, McpToolbox
from api.tokens import create_token
from tests.stub_servers import StubLog, build_stub_servers

pytestmark = pytest.mark.anyio

TEST_SECRET = "test-secret-that-is-long-enough-for-hs256-signing"  # the value conftest.py sets
CONTRACT_TOOLS = {
    "book_appointment",
    "list_my_appointments",
    "cancel_appointment",
    "view_inventory",
    "add_inventory",
    "get_my_medical_records",
    "get_my_last_medical_record",
    "search_clinic_docs",
}
URL_ENV_VARS = {
    "appointments": "APPOINTMENTS_MCP_URL",
    "pharmacy": "PHARMACY_MCP_URL",
    "records": "RECORDS_MCP_URL",
    "knowledge": "KNOWLEDGE_MCP_URL",
}


@pytest.fixture
async def stubs(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[StubLog]:
    """Serve the four stub servers on free local ports and point the API at them."""
    log = StubLog()
    async with AsyncExitStack() as stack:
        for name, server in build_stub_servers(log).items():
            url = await stack.enter_async_context(run_server_async(server))
            monkeypatch.setenv(URL_ENV_VARS[name], url)
        yield log


@asynccontextmanager
async def api_client(llm: FakeLLM) -> AsyncIterator[httpx2.AsyncClient]:
    """Run the real app in-process, with the fake LLM, and yield an HTTP client for it."""
    app = create_app(llm=llm)
    transport = httpx2.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        yield client


def bearer(sub: str) -> dict[str, str]:
    """Return the Authorization header for a signed-in test user."""
    return {"Authorization": f"Bearer {create_token(sub, f'{sub}@example.com', USER_SCOPES)}"}


def tool_call(name: str, call_id: str = "call-1", **arguments: object) -> LLMReply:
    """A scripted model reply that asks for one tool."""
    return LLMReply(content="", tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)])


async def post_chat(llm: FakeLLM, message: str, headers: dict[str, str]) -> httpx2.Response:
    """Send one chat message to a fresh app."""
    async with api_client(llm) as client:
        response: httpx2.Response = await client.post(
            "/chat", json={"message": message}, headers=headers
        )
    return response


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": "Basic abc"},
        {
            "Authorization": "Bearer "
            + jwt.encode(
                {"sub": "user-a", "email": "a@x.com", "scopes": USER_SCOPES, "exp": 1},
                TEST_SECRET,
                algorithm="HS256",
            )
        },
    ],
    ids=["missing", "malformed", "not-bearer", "expired"],
)
async def test_chat_without_a_valid_token_is_401(headers: dict[str, str]) -> None:
    """No valid JWT, no chat: the model is never called."""
    llm = FakeLLM([])
    response = await post_chat(llm, "hello", headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert llm.calls == []


@pytest.mark.parametrize("message", ["", "x" * 2001])
async def test_empty_or_huge_message_is_422(message: str) -> None:
    """The message must be 1 to 2000 characters."""
    response = await post_chat(FakeLLM([]), message, bearer("user-a"))

    assert response.status_code == 422


async def test_plain_reply_with_tools_discovered_from_all_four_servers(stubs: StubLog) -> None:
    """The model gets the system prompt, the message and every contract tool, and its text
    comes back as the reply."""
    llm = FakeLLM([LLMReply(content="Hello! How can I help?")])

    response = await post_chat(llm, "hi", bearer("user-a"))

    assert response.status_code == 200
    assert response.json() == {"reply": "Hello! How can I help?"}
    messages, tools = llm.calls[0]
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert messages[1] == {"role": "user", "content": "hi"}
    assert {tool.name for tool in tools} == CONTRACT_TOOLS


@pytest.mark.parametrize(("sub", "diagnosis"), [("user-a", "Flu"), ("user-b", "Sprained ankle")])
async def test_tool_call_carries_the_callers_jwt(stubs: StubLog, sub: str, diagnosis: str) -> None:
    """The MCP server gets the caller's own JWT, so it returns the caller's own record."""
    headers = bearer(sub)
    llm = FakeLLM(
        [tool_call("get_my_last_medical_record"), LLMReply(content=f"Your last visit: {diagnosis}")]
    )

    response = await post_chat(llm, "Show me the last medical record", headers)

    assert response.json() == {"reply": f"Your last visit: {diagnosis}"}
    second_prompt, _ = llm.calls[1]
    tool_message = second_prompt[-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert diagnosis in tool_message["content"]
    assert stubs.authorization_headers[-1] == headers["Authorization"]


async def test_the_jwt_never_reaches_the_model(stubs: StubLog) -> None:
    """The token lives only in the MCP calls, never in anything the model sees."""
    headers = bearer("user-a")
    token = headers["Authorization"].removeprefix("Bearer ")
    llm = FakeLLM([tool_call("get_my_last_medical_record"), LLMReply(content="Done")])

    await post_chat(llm, "last record please", headers)

    for messages, _ in llm.calls:
        assert token not in str(messages)


async def test_unknown_tool_gets_an_error_result_not_a_crash(stubs: StubLog) -> None:
    """If the model invents a tool, it gets an error back and can still answer."""
    llm = FakeLLM([tool_call("delete_all_records"), LLMReply(content="I can't do that.")])

    response = await post_chat(llm, "delete everything", bearer("user-a"))

    assert response.json() == {"reply": "I can't do that."}
    second_prompt, _ = llm.calls[1]
    assert "unknown tool delete_all_records" in second_prompt[-1]["content"]


async def test_step_limit_stops_a_model_that_keeps_calling_tools(stubs: StubLog) -> None:
    """A model stuck calling tools is stopped after MAX_AGENT_STEPS with a polite reply."""
    llm = FakeLLM([tool_call("view_inventory", call_id=f"c{n}") for n in range(MAX_AGENT_STEPS)])

    response = await post_chat(llm, "loop forever", bearer("user-a"))

    assert response.json() == {"reply": STEP_LIMIT_REPLY}
    assert len(llm.calls) == MAX_AGENT_STEPS


async def test_a_down_server_is_skipped_and_logged(
    stubs: StubLog, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """If one MCP server is down, chat still works with the other servers' tools."""
    monkeypatch.setenv("RECORDS_MCP_URL", f"http://127.0.0.1:{find_available_port()}/mcp")
    llm = FakeLLM([LLMReply(content="Records are unavailable right now, sorry.")])

    with caplog.at_level(logging.WARNING, logger="api.mcp_tools"):
        response = await post_chat(llm, "my records?", bearer("user-a"))

    assert response.status_code == 200
    _, tools = llm.calls[0]
    names = {tool.name for tool in tools}
    assert "get_my_last_medical_record" not in names
    assert "view_inventory" in names
    assert "MCP server records" in caplog.text


async def test_a_server_that_goes_down_after_discovery_gives_an_error_result(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A tool call to a server that has gone away returns an error for the model, and logs."""
    server = build_stub_servers(StubLog())["records"]
    token = bearer("user-a")["Authorization"].removeprefix("Bearer ")
    async with run_server_async(server) as url:
        toolbox = McpToolbox({"records": url}, token, timeout=2)
        await toolbox.discover()
    # Point the toolbox's clients at a port where nothing listens, as if the server crashed.
    dead_url = f"http://127.0.0.1:{find_available_port()}/mcp"
    make_client = toolbox._client
    monkeypatch.setattr(toolbox, "_client", lambda _url: make_client(dead_url))

    with caplog.at_level(logging.WARNING, logger="api.mcp_tools"):
        result = await toolbox.call("get_my_last_medical_record", {})

    assert result == UNAVAILABLE_RESULT
    assert "get_my_last_medical_record" in caplog.text


async def test_model_failure_is_503_and_logged(
    stubs: StubLog, caplog: pytest.LogCaptureFixture
) -> None:
    """If the model can't be reached, the patient gets a clear 503, never a stack trace."""
    llm = FakeLLM([LLMUnavailable("OpenAI request failed: APITimeoutError")])

    with caplog.at_level(logging.WARNING, logger="api.chat_routes"):
        response = await post_chat(llm, "hi", bearer("user-a"))

    assert response.status_code == 503
    assert response.json() == {"detail": "The assistant is unavailable right now. Try again soon."}
    assert "APITimeoutError" in caplog.text


def test_system_prompt_sets_the_safety_rules() -> None:
    """The prompt says the user is known, never to ask for an ID, and never to diagnose."""
    prompt = SYSTEM_PROMPT.lower()

    assert "already signed in" in prompt
    assert "never ask for" in prompt and "id" in prompt
    assert "never diagnose" in prompt


def test_missing_chat_settings_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """The app refuses to start without the model and MCP server settings."""
    monkeypatch.delenv("CHAT_MODEL")
    monkeypatch.delenv("RECORDS_MCP_URL")

    with pytest.raises(RuntimeError, match="CHAT_MODEL, RECORDS_MCP_URL"):
        create_app()
