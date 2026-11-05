"""Shared pytest fixtures.

Layout mirrors the package: tests/unit (nodes, routing, retriever with the fake LLM),
tests/api (HTTP via TestClient), tests/integration (real PostgreSQL, marked `integration`).
Tests never call a real LLM.
"""

from collections.abc import Callable

import pytest
from pydantic import SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from clinic_assistant.config import Settings

# The database values every Settings needs; tests add only what they check.
TEST_DB = {
    "postgres_user": "clinic",
    "postgres_password": SecretStr("clinic"),
    "postgres_db": "clinic",
}


class ExplicitSettings(Settings):
    """Settings from the values a test passes only, never the shell environment or `.env`.

    Plain Settings (and Settings.model_validate) still read both, so a developer's
    LLM_PROVIDER=fake would silently change what a config test checks.
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Keep only the constructor arguments."""
        return (init_settings,)


@pytest.fixture
def explicit_settings() -> Callable[..., Settings]:
    """Build Settings from TEST_DB plus the given values, isolated from env and `.env`."""

    def build(**values: object) -> Settings:
        return ExplicitSettings.model_validate({**TEST_DB, **values})

    return build
