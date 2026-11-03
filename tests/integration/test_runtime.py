"""postgres_runtime opens the pool and checkpointer at start-up and closes them at shutdown."""

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from clinic_assistant.config import Settings
from clinic_assistant.llm import FakeLLM
from clinic_assistant.main import postgres_runtime

pytestmark = pytest.mark.integration


async def test_postgres_runtime_builds_checkpointed_graph(settings: Settings) -> None:
    async with postgres_runtime(settings, FakeLLM()) as runtime:
        checkpointer = runtime.graph.checkpointer

        assert isinstance(checkpointer, AsyncPostgresSaver)
        assert not checkpointer.conn.closed
        assert runtime.pool is checkpointer.conn  # services share the checkpointer's pool


async def test_postgres_runtime_closes_pool(settings: Settings) -> None:
    async with postgres_runtime(settings, FakeLLM()) as runtime:
        checkpointer = runtime.graph.checkpointer
        assert isinstance(checkpointer, AsyncPostgresSaver)

    assert checkpointer.conn.closed
