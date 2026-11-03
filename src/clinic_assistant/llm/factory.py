"""Choose the LLM adapter from settings; the only place that knows about providers."""

from clinic_assistant.config import Settings
from clinic_assistant.llm.base import LLM
from clinic_assistant.llm.demo import DemoLLM
from clinic_assistant.llm.openai_llm import OpenAILLM


def create_llm(settings: Settings) -> LLM:
    """OpenAI in production; DemoLLM when LLM_PROVIDER=fake (no key needed)."""
    if settings.llm_provider == "fake":
        return DemoLLM()
    if settings.openai_api_key is None:  # unreachable: Settings validates this at start-up
        raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
    return OpenAILLM.create(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
