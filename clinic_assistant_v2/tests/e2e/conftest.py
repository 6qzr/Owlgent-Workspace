"""End-to-end setup: the four real MCP servers over HTTP on local ports, with fresh seed data
for every test. Only OpenAI is faked; Qdrant is a real in-memory instance filled from the PDFs."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from copy import deepcopy

import pytest
from fastmcp.utilities.tests import run_server_async
from qdrant_client import QdrantClient

from ingestion.ingest import PDF_DIR, ingest_pdfs
from servers.appointments import server as appointments
from servers.knowledge import server as knowledge
from servers.pharmacy import server as pharmacy
from servers.records import server as records
from tests.e2e.helpers import FakeOpenAI, keyword_embedder

COLLECTION = "clinic_docs"

# The seed data as the servers start with it, restored before every test.
SEED_APPOINTMENTS = deepcopy(appointments.appointments)
SEED_INVENTORY = deepcopy(pharmacy.inventory)
SEED_RECORDS = deepcopy(records.medical_records)

SERVERS = {
    "APPOINTMENTS_MCP_URL": appointments.mcp,
    "PHARMACY_MCP_URL": pharmacy.mcp,
    "RECORDS_MCP_URL": records.mcp,
    "KNOWLEDGE_MCP_URL": knowledge.mcp,
}


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """One asyncio loop for the whole session: the real servers are started once and stay
    bound to it (a FastMCP server object can't move to another loop)."""
    return "asyncio"


@pytest.fixture(scope="session")
def clinic_docs() -> QdrantClient:
    """A real in-memory Qdrant holding the three clinic PDFs, loaded by the real ingest code."""
    client = QdrantClient(":memory:")
    ingest_pdfs(client, PDF_DIR, COLLECTION, keyword_embedder)
    return client


@pytest.fixture(autouse=True)
def fresh_seed_data() -> None:
    """Put every server's in-memory data back to its seed state."""
    appointments.appointments.clear()
    appointments.appointments.update(deepcopy(SEED_APPOINTMENTS))
    pharmacy.inventory.clear()
    pharmacy.inventory.update(deepcopy(SEED_INVENTORY))
    records.medical_records.clear()
    records.medical_records.update(deepcopy(SEED_RECORDS))


@pytest.fixture(autouse=True)
def api_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake settings for the API; none of them reach a real service."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
    monkeypatch.setenv("CHAT_MODEL", "fake-model")
    monkeypatch.setenv("QDRANT_COLLECTION", COLLECTION)


@pytest.fixture(scope="session")
async def running_servers(clinic_docs: QdrantClient) -> AsyncIterator[dict[str, str]]:
    """Serve the four real MCP servers once for the session; yield {env var: URL}."""
    with pytest.MonkeyPatch.context() as patch:
        # Only OpenAI is faked: the knowledge server embeds with keywords and reads the
        # in-memory Qdrant that the real ingest code filled.
        patch.setattr(knowledge, "get_openai_client", FakeOpenAI)
        patch.setattr(knowledge, "get_qdrant_client", lambda: clinic_docs)
        urls: dict[str, str] = {}
        async with AsyncExitStack() as stack:
            for env_var, mcp in SERVERS.items():
                urls[env_var] = await stack.enter_async_context(run_server_async(mcp))
            yield urls


@pytest.fixture
def servers(running_servers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Point the API at the running servers; return their URLs by short name."""
    for env_var, url in running_servers.items():
        monkeypatch.setenv(env_var, url)
    return {
        env_var.removesuffix("_MCP_URL").lower(): url for env_var, url in running_servers.items()
    }
