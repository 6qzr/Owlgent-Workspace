"""open_checkpointer prepares AsyncPostgresSaver on the shared pool (ADR 0001)."""

from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.checkpointer import open_checkpointer
from clinic_assistant.agent.graph import build_graph
from clinic_assistant.agent.nodes.classify import Classification
from clinic_assistant.domain import Intent
from clinic_assistant.llm import FakeLLM
from clinic_assistant.repository.db import DictPool

pytestmark = pytest.mark.integration

CHECKPOINT_TABLES = {
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
}


async def test_open_checkpointer_creates_tables(pool: DictPool) -> None:
    await open_checkpointer(pool)

    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
            ("public",),
        )
        tables = {row["table_name"] for row in await cursor.fetchall()}

    assert tables >= CHECKPOINT_TABLES


async def test_open_checkpointer_is_idempotent(pool: DictPool) -> None:
    await open_checkpointer(pool)
    await open_checkpointer(pool)


async def test_checkpoint_round_trip(pool: DictPool) -> None:
    saver = await open_checkpointer(pool)
    llm = FakeLLM([Classification(intent=Intent.OTHER, confidence=0.9)])
    graph = build_graph(llm, saver)
    config: RunnableConfig = {"configurable": {"thread_id": str(uuid4())}}

    await graph.ainvoke({"messages": [HumanMessage("Hello")]}, config)

    saved = await graph.aget_state(config)
    assert saved.values["messages"][0].content == "Hello"
    assert len(saved.values["messages"]) == 2  # patient message + reply
