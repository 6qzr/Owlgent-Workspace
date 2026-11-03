"""Fixtures for tests that need a real PostgreSQL (settings come from env / .env)."""

import asyncio
from collections.abc import AsyncIterator, Mapping

import pytest
from pytest_asyncio.plugin import LoopFactory

from clinic_assistant.config import Settings, get_settings
from clinic_assistant.repository.db import DictPool, create_pool

POOL_OPEN_TIMEOUT_SECONDS = 10.0


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, LoopFactory]:
    """Run on a selector loop: psycopg async can't use Windows' default Proactor loop."""
    return {"selector": asyncio.SelectorEventLoop}


@pytest.fixture
def settings() -> Settings:
    """Application settings read from the environment."""
    return get_settings()


@pytest.fixture
async def pool(settings: Settings) -> AsyncIterator[DictPool]:
    """An open connection pool to the test database, closed after the test."""
    db_pool = create_pool(settings)
    await db_pool.open(wait=True, timeout=POOL_OPEN_TIMEOUT_SECONDS)
    try:
        yield db_pool
    finally:
        await db_pool.close()
