"""The real adapter: AsyncOpenAI with a timeout; every failure becomes LLMError."""

from collections.abc import Sequence
from typing import cast

import openai
from langchain_core.messages import AnyMessage, convert_to_openai_messages
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError

from clinic_assistant.llm.base import LLMError


def _to_openai(messages: Sequence[AnyMessage]) -> list[ChatCompletionMessageParam]:
    return cast(list[ChatCompletionMessageParam], convert_to_openai_messages(list(messages)))


class OpenAILLM:
    """Calls the OpenAI chat API; the client is injected so tests can fake the HTTP layer."""

    def __init__(self, client: openai.AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def create(cls, api_key: str, model: str, timeout_seconds: float) -> OpenAILLM:
        """Build the adapter from settings; one retry keeps the patient's wait bounded."""
        client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        return cls(client, model)

    async def complete(self, messages: Sequence[AnyMessage]) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model, messages=_to_openai(messages)
            )
        except openai.OpenAIError as exc:
            raise LLMError(f"OpenAI call failed: {type(exc).__name__}") from exc
        content = response.choices[0].message.content
        if not content:
            raise LLMError("OpenAI returned an empty reply")
        return content

    async def parse[SchemaT: BaseModel](
        self, messages: Sequence[AnyMessage], schema: type[SchemaT]
    ) -> SchemaT:
        try:
            response = await self._client.chat.completions.parse(
                model=self._model, messages=_to_openai(messages), response_format=schema
            )
        except (openai.OpenAIError, ValidationError) as exc:
            raise LLMError(f"OpenAI structured call failed: {type(exc).__name__}") from exc
        parsed = response.choices[0].message.parsed
        if parsed is None:
            # A refusal or empty reply; the refusal text stays out of the error (and logs).
            raise LLMError("OpenAI refused or returned no structured reply")
        return parsed
