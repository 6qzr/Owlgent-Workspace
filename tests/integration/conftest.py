"""Fixtures for tests that need real PostgreSQL."""

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
    config: pytest.Config,
    item: pytest.Item,
) -> Mapping[str, LoopFactory]:
    """Use the selector event loop for psycopg on Windows."""
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
    """Open and close a PostgreSQL connection pool."""
    db_pool = create_pool(settings)
    await db_pool.open(
        wait=True,
        timeout=POOL_OPEN_TIMEOUT_SECONDS,
    )

    try:
        yield db_pool
    finally:
        await db_pool.close()


@pytest.fixture
async def saver(pool: DictPool) -> AsyncPostgresSaver:
    """Return the real PostgreSQL checkpointer."""
    return await open_checkpointer(pool)


@pytest.fixture
def paused_graph(saver: AsyncPostgresSaver) -> ConversationGraph:
    """A small graph that pauses while awaiting staff approval."""

    async def await_staff(state: ConversationState) -> Update:
        interrupt({"approval_id": 1})
        return {}

    builder = StateGraph(ConversationState)
    builder.add_node("await_staff", await_staff)
    builder.add_edge(START, "await_staff")
    builder.add_edge("await_staff", END)

    return builder.compile(checkpointer=saver)


class FreeSlot(NamedTuple):
    """A doctor and an available appointment slot."""

    slot_id: int
    doctor_id: int


class SeededBooking(NamedTuple):
    """IDs of a confirmed booking created for one test."""

    booking_id: int
    conversation_id: UUID
    slot_id: int
    doctor_id: int


@pytest.fixture
async def free_slot(pool: DictPool) -> AsyncIterator[FreeSlot]:
    """Create a doctor and an unbooked future slot.

    The test data is removed after dependent fixtures and tests finish.
    """
    starts_at = datetime.now(UTC) + timedelta(days=30)

    async with pool.connection() as conn, conn.transaction():
        cursor = await conn.execute(
            """
            INSERT INTO doctors (name, specialty)
            VALUES (%s, %s)
            RETURNING id
            """,
            (f"Test Doctor {uuid4()}", "Test"),
        )
        doctor = await cursor.fetchone()
        assert doctor is not None

        doctor_id = int(doctor["id"])

        cursor = await conn.execute(
            """
            INSERT INTO slots (doctor_id, starts_at, ends_at)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (
                doctor_id,
                starts_at,
                starts_at + timedelta(minutes=30),
            ),
        )
        slot = await cursor.fetchone()
        assert slot is not None

        slot_id = int(slot["id"])

    try:
        yield FreeSlot(
            slot_id=slot_id,
            doctor_id=doctor_id,
        )
    finally:
        async with pool.connection() as conn, conn.transaction():
            await conn.execute(
                "DELETE FROM slots WHERE id = %s",
                (slot_id,),
            )
            await conn.execute(
                "DELETE FROM doctors WHERE id = %s",
                (doctor_id,),
            )


@pytest.fixture
async def confirmed_booking(
    pool: DictPool,
    free_slot: FreeSlot,
) -> AsyncIterator[SeededBooking]:
    """Create a confirmed booking using the shared free slot."""
    patient_conversation_id = uuid4()

    async with pool.connection() as conn, conn.transaction():
        await conn.execute(
            "INSERT INTO conversations (id) VALUES (%s)",
            (patient_conversation_id,),
        )

        cursor = await conn.execute(
            """
            INSERT INTO bookings (
                slot_id,
                conversation_id,
                patient_name,
                patient_phone,
                status
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                free_slot.slot_id,
                patient_conversation_id,
                "Test Patient",
                "90000000",
                "confirmed",
            ),
        )

        booking = await cursor.fetchone()
        assert booking is not None

        booking_id = int(booking["id"])

    seeded = SeededBooking(
        booking_id=booking_id,
        conversation_id=patient_conversation_id,
        slot_id=free_slot.slot_id,
        doctor_id=free_slot.doctor_id,
    )

    try:
        yield seeded
    finally:
        checkpointer = await open_checkpointer(pool)
        await checkpointer.adelete_thread(str(patient_conversation_id))

        async with pool.connection() as conn, conn.transaction():
            await conn.execute(
                "DELETE FROM approvals WHERE conversation_id = %s",
                (patient_conversation_id,),
            )
            await conn.execute(
                "DELETE FROM bookings WHERE id = %s",
                (booking_id,),
            )
            await conn.execute(
                "DELETE FROM conversations WHERE id = %s",
                (patient_conversation_id,),
            )
