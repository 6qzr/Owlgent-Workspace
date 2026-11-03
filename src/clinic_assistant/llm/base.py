"""The async interface every node talks to; the real and fake adapters satisfy it (ADR 0007)."""

from collections.abc import Sequence
from typing import Protocol

from langchain_core.messages import AnyMessage
from pydantic import BaseModel


class LLMError(Exception):
    """The model could not give a usable answer; the API maps this to 502."""


class LLM(Protocol):
    """What the graph needs from a language model: free text or a validated object."""

    async def complete(self, messages: Sequence[AnyMessage]) -> str:
        """Return the model's text reply to the conversation."""
        ...

    async def parse[SchemaT: BaseModel](
        self, messages: Sequence[AnyMessage], schema: type[SchemaT]
    ) -> SchemaT:
        """Return the model's reply validated against `schema` (structured output)."""
        ...
