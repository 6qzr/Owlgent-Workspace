"""create_llm picks the adapter from LLM_PROVIDER; no network call is made."""

import pytest
from pydantic import SecretStr

from clinic_assistant.config import Settings
from clinic_assistant.llm import DemoLLM, OpenAILLM
from clinic_assistant.llm.factory import create_llm

DB = {
    "postgres_user": "clinic",
    "postgres_password": SecretStr("clinic"),
    "postgres_db": "clinic",
}


@pytest.fixture(autouse=True)
def clear_llm_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent shell environment variables from affecting factory tests."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)


def test_fake_provider_gives_the_demo_llm() -> None:
    settings = Settings.model_validate(
        {
            **DB,
            "llm_provider": "fake",
        }
    )

    assert isinstance(create_llm(settings), DemoLLM)


def test_openai_provider_gives_the_openai_adapter() -> None:
    settings = Settings.model_validate(
        {
            **DB,
            "llm_provider": "openai",
            "openai_api_key": SecretStr("sk-test"),
        }
    )

    assert isinstance(create_llm(settings), OpenAILLM)
