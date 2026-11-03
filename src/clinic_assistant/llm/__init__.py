"""LLM adapter interface with a real and a deterministic fake implementation."""

from clinic_assistant.llm.base import LLM, LLMError
from clinic_assistant.llm.demo import DemoLLM
from clinic_assistant.llm.fake import FakeLLM
from clinic_assistant.llm.openai_llm import OpenAILLM

__all__ = ["LLM", "DemoLLM", "FakeLLM", "LLMError", "OpenAILLM"]
