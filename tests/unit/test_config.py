"""Settings fail fast on a missing key only when the real model is selected."""

import pytest
from pydantic import SecretStr, ValidationError

from clinic_assistant.config import Settings

DB = {
    "postgres_user": "clinic",
    "postgres_password": SecretStr("clinic"),
    "postgres_db": "clinic",
}


@pytest.fixture(autouse=True)
def clear_llm_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent shell environment variables from affecting settings tests."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)


def settings(**overrides: object) -> Settings:
    """Create settings from explicit values only."""
    return Settings.model_validate({"openai_api_key": None, **DB, **overrides})


def test_openai_is_the_default_provider() -> None:
    assert settings(openai_api_key=SecretStr("sk-test")).llm_provider == "openai"


def test_openai_without_a_key_fails_fast() -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY is required"):
        settings()


def test_blank_key_counts_as_missing() -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY is required"):
        settings(openai_api_key=SecretStr("   "))


def test_fake_provider_needs_no_key() -> None:
    assert settings(llm_provider="fake").llm_provider == "fake"


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        settings(llm_provider="gemini")
