"""create_llm picks the adapter from LLM_PROVIDER; no network call is made."""

from collections.abc import Callable

from pydantic import SecretStr

from clinic_assistant.config import Settings
from clinic_assistant.llm import DemoLLM, OpenAILLM
from clinic_assistant.llm.factory import create_llm

type MakeSettings = Callable[..., Settings]


def test_fake_provider_gives_the_demo_llm(explicit_settings: MakeSettings) -> None:
    settings = explicit_settings(llm_provider="fake")

    assert isinstance(create_llm(settings), DemoLLM)


def test_openai_provider_gives_the_openai_adapter(explicit_settings: MakeSettings) -> None:
    settings = explicit_settings(openai_api_key=SecretStr("sk-test"))

    assert isinstance(create_llm(settings), OpenAILLM)
