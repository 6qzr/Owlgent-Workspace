"""Shared setup for the API tests: fake settings and a known JWT secret."""

import pytest

TEST_SECRET = "test-secret-that-is-long-enough-for-hs256-signing"
REDIRECT_URI = "http://localhost:8000/auth/callback"


@pytest.fixture(autouse=True)
def api_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every API test fake settings; no real Google, OpenAI or MCP server is used."""
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", REDIRECT_URI)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
    monkeypatch.setenv("CHAT_MODEL", "fake-model")
    for name, port in [("APPOINTMENTS", 8001), ("PHARMACY", 8002), ("RECORDS", 8003)]:
        monkeypatch.setenv(f"{name}_MCP_URL", f"http://127.0.0.1:{port}/mcp")
    monkeypatch.setenv("KNOWLEDGE_MCP_URL", "http://127.0.0.1:8004/mcp")
    monkeypatch.delenv("TOKEN_TTL_SECONDS", raising=False)


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio, the loop FastAPI and fastmcp use."""
    return "asyncio"
