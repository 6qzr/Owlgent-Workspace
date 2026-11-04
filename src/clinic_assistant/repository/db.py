from psycopg import AsyncConnection
from psycopg.conninfo import make_conninfo
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from clinic_assistant.config import Settings

# Rows come back as dicts, so the type says so too (AsyncPostgresSaver requires it).
type DictPool = AsyncConnectionPool[AsyncConnection[DictRow]]


def conninfo(settings: Settings) -> str:
    """The PostgreSQL connection string for these settings."""
    return make_conninfo(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
    )


def create_pool(settings: Settings) -> DictPool:
    """Create the PostgreSQL asynchronous connection pool."""
    return AsyncConnectionPool(
        conninfo=conninfo(settings),
        connection_class=AsyncConnection[DictRow],
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
        },
        open=False,
    )
