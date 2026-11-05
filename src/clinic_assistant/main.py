"""Application factory: creates the FastAPI app and wires dependencies at start-up."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

from clinic_assistant import __version__
from clinic_assistant.agent.checkpointer import open_checkpointer
from clinic_assistant.agent.graph import ConversationGraph, Repositories, build_graph
from clinic_assistant.api import approvals, conversations, emergencies, health, slots
from clinic_assistant.config import Settings, get_settings
from clinic_assistant.kb.loader import load_documents
from clinic_assistant.kb.retriever import Retriever
from clinic_assistant.llm import LLM
from clinic_assistant.llm.factory import create_llm
from clinic_assistant.repository.approvals import ApprovalsRepository
from clinic_assistant.repository.bookings import BookingsRepository
from clinic_assistant.repository.db import DictPool, create_pool
from clinic_assistant.repository.emergencies import EmergencyFlagsRepository
from clinic_assistant.repository.slots import SlotsRepository

APP_TITLE = "Clinic Front-Desk Assistant"
POOL_OPEN_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class Runtime:
    """Long-lived objects built once at start-up and shared by every request."""

    graph: ConversationGraph
    pool: DictPool


type RuntimeFactory = Callable[[], AbstractAsyncContextManager[Runtime]]


@asynccontextmanager
async def postgres_runtime(settings: Settings, llm: LLM) -> AsyncIterator[Runtime]:
    """Open the pool and checkpointer, build the graph, and close the pool on exit."""
    pool = create_pool(settings)
    await pool.open(wait=True, timeout=POOL_OPEN_TIMEOUT_SECONDS)
    try:
        # Load clinic documents into PostgreSQL.
        await load_documents(pool)
        checkpointer = await open_checkpointer(pool)
        repositories = Repositories(
            approvals=ApprovalsRepository(pool),
            slots=SlotsRepository(pool),
            emergencies=EmergencyFlagsRepository(pool),
            bookings=BookingsRepository(pool),
            retriever=Retriever(
                pool,
                threshold=settings.retrieval_threshold,
                top_k=settings.retrieval_top_k,
            ),
        )
        yield Runtime(graph=build_graph(llm, checkpointer, repositories), pool=pool)
    finally:
        await pool.close()


def default_runtime() -> AbstractAsyncContextManager[Runtime]:
    """Production runtime: settings from env, the LLM_PROVIDER adapter, PostgreSQL state."""
    settings = get_settings()
    return postgres_runtime(settings, create_llm(settings))


def create_app(runtime: RuntimeFactory = default_runtime) -> FastAPI:
    """Create the FastAPI app; each slice registers its router here.

    The runtime is opened in the lifespan and stored on ``app.state.runtime``.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with runtime() as opened:
            app.state.runtime = opened
            yield

    app = FastAPI(title=APP_TITLE, version=__version__, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(conversations.router)
    app.include_router(approvals.router)
    app.include_router(slots.router)
    app.include_router(emergencies.router)
    return app


app = create_app()
