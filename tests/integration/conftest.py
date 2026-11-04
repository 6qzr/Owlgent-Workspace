"""Fixtures for tests that need a real PostgreSQL (settings come from env / .env)."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import NamedTuple
from uuid import UUID, uuid4

import psycopg
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pytest_asyncio.plugin import LoopFactory

from clinic_assistant.agent.checkpointer import open_checkpointer
from clinic_assistant.agent.graph import ConversationGraph
from clinic_assistant.agent.nodes import Update
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.config import Settings
from clinic_assistant.repository.db import DictPool, conninfo, create_pool

POOL_OPEN_TIMEOUT_SECONDS = 10.0
DB_CHECK_TIMEOUT_SECONDS = 3
START_DEV_DB = "docker compose -f compose.yaml -f compose.dev.yaml up -d db"


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, LoopFactory]:
    """Run on a selector loop: psycopg async can't use Windows' default Proactor loop."""
    return {"selector": asyncio.SelectorEventLoop}


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Database settings from env / `.env`, with the fake LLM: tests never call a real one.

    Forcing the provider means a developer's `.env` (openai without a key, or fake) can't
    change or break the run. The database is checked once, so a missing one stops the run
    straight away with the fix, instead of a 10 s pool timeout in every test.
    """
    settings = Settings(llm_provider="fake")  # type: ignore[call-arg]  # rest from env / .env
    try:
        with psycopg.connect(conninfo(settings), connect_timeout=DB_CHECK_TIMEOUT_SECONDS):
            pass
    except psycopg.OperationalError as error:
        pytest.exit(
            f"PostgreSQL is not reachable at {settings.postgres_host}:{settings.postgres_port}"
            f" ({error}). Start it with: {START_DEV_DB}",
            returncode=1,
        )
    return settings


@pytest.fixture
async def pool(settings: Settings) -> AsyncIterator[DictPool]:
    """An open connection pool to the test database, closed after the test."""
    db_pool = create_pool(settings)
    await db_pool.open(wait=True, timeout=POOL_OPEN_TIMEOUT_SECONDS)
    try:
        yield db_pool
    finally:
        await db_pool.close()


@pytest.fixture
async def saver(pool: DictPool) -> AsyncPostgresSaver:
    """The real checkpointer on the test pool."""
    return await open_checkpointer(pool)


@pytest.fixture
def paused_graph(saver: AsyncPostgresSaver) -> ConversationGraph:
    """A tiny graph that always stops at await_staff, like the approval branch."""

    async def await_staff(state: ConversationState) -> Update:
        interrupt({"approval_id": 1})
        return {}

    builder = StateGraph(ConversationState)
    builder.add_node("await_staff", await_staff)
    builder.add_edge(START, "await_staff")
    builder.add_edge("await_staff", END)
    return builder.compile(checkpointer=saver)


class SeededBooking(NamedTuple):
    """Ids of a confirmed booking created for one test."""

    booking_id: int
    conversation_id: UUID
    slot_id: int
    doctor_id: int


@pytest.fixture
async def confirmed_booking(pool: DictPool) -> AsyncIterator[SeededBooking]:
    """A confirmed booking with its own conversation, doctor and future slot, removed after.

    It never touches seed data, so tests can cancel it or free its slot safely. Seeding is one
    transaction, so a failure part-way leaves nothing behind.
    """
    conversation_id = uuid4()
    starts_at = datetime.now(UTC) + timedelta(days=30)
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("INSERT INTO conversations (id) VALUES (%s)", (conversation_id,))
        cur = await conn.execute(
            "INSERT INTO doctors (name, specialty) VALUES (%s, 'Test') RETURNING id",
            (f"Test Doctor {conversation_id}",),
        )
        doctor = await cur.fetchone()
        assert doctor is not None
        cur = await conn.execute(
            "INSERT INTO slots (doctor_id, starts_at, ends_at) VALUES (%s, %s, %s) RETURNING id",
            (doctor["id"], starts_at, starts_at + timedelta(minutes=30)),
        )
        slot = await cur.fetchone()
        assert slot is not None
        cur = await conn.execute(
            "INSERT INTO bookings (slot_id, conversation_id, patient_name, patient_phone, status)"
            " VALUES (%s, %s, 'Test Patient', '90000000', 'confirmed') RETURNING id",
            (slot["id"], conversation_id),
        )
        booking = await cur.fetchone()
        assert booking is not None
    seeded = SeededBooking(booking["id"], conversation_id, slot["id"], doctor["id"])
    try:
        yield seeded
    finally:
        # The conversation's checkpoints first, then its rows in foreign-key order. Approvals go
        # by conversation, so one for another booking can't block the conversation delete.
        await (await open_checkpointer(pool)).adelete_thread(str(conversation_id))
        async with pool.connection() as conn, conn.transaction():
            await conn.execute(
                "DELETE FROM approvals WHERE conversation_id = %s", (conversation_id,)
            )
            await conn.execute("DELETE FROM bookings WHERE id = %s", (seeded.booking_id,))
            await conn.execute("DELETE FROM slots WHERE id = %s", (seeded.slot_id,))
            await conn.execute("DELETE FROM doctors WHERE id = %s", (seeded.doctor_id,))
            await conn.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
