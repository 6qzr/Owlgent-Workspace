"""Settings fail fast on a missing key only when the real model is selected."""

from collections.abc import Callable

import pytest
from pydantic import SecretStr, ValidationError

from clinic_assistant.config import Settings

type MakeSettings = Callable[..., Settings]


def test_openai_is_the_default_provider(explicit_settings: MakeSettings) -> None:
    settings = explicit_settings(openai_api_key=SecretStr("sk-test"))

    assert settings.llm_provider == "openai"


def test_openai_without_a_key_fails_fast(explicit_settings: MakeSettings) -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY is required"):
        explicit_settings(openai_api_key=None)


def test_blank_key_counts_as_missing(explicit_settings: MakeSettings) -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY is required"):
        explicit_settings(openai_api_key=SecretStr("   "))


def test_fake_provider_needs_no_key(explicit_settings: MakeSettings) -> None:
    assert explicit_settings(llm_provider="fake").llm_provider == "fake"


def test_unknown_provider_is_rejected(explicit_settings: MakeSettings) -> None:
    with pytest.raises(ValidationError):
        explicit_settings(llm_provider="gemini")
