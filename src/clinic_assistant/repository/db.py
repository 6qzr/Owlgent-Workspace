from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from clinic_assistant.config import Settings


def create_pool(settings: Settings) -> AsyncConnectionPool:
    """Create the PostgreSQL asynchronous connection pool."""
    return AsyncConnectionPool(
        conninfo=make_conninfo(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password.get_secret_value(),
        ),
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
        },
        open=False,
    )
