"""Deterministic stand-in for the model; unit tests and CI never call a real LLM."""

from collections import deque
from collections.abc import Iterable, Sequence

from langchain_core.messages import AnyMessage
from pydantic import BaseModel

type ScriptedReply = str | BaseModel | Exception


class FakeLLM:
    """Returns scripted replies in order and records every prompt it received.

    A scripted Exception is raised instead of returned, to test the 502 path.
    """

    def __init__(self, replies: Iterable[ScriptedReply] = ()) -> None:
        self._replies: deque[ScriptedReply] = deque(replies)
        self.calls: list[list[AnyMessage]] = []

    async def complete(self, messages: Sequence[AnyMessage]) -> str:
        reply = self._next(messages)
        if not isinstance(reply, str):
            raise AssertionError(f"FakeLLM.complete expected a str, got {type(reply).__name__}")
        return reply

    async def parse[SchemaT: BaseModel](
        self, messages: Sequence[AnyMessage], schema: type[SchemaT]
    ) -> SchemaT:
        reply = self._next(messages)
        if not isinstance(reply, schema):
            raise AssertionError(
                f"FakeLLM.parse expected {schema.__name__}, got {type(reply).__name__}"
            )
        return reply

    def _next(self, messages: Sequence[AnyMessage]) -> str | BaseModel:
        self.calls.append(list(messages))
        if not self._replies:
            raise AssertionError("FakeLLM has no scripted reply left")
        reply = self._replies.popleft()
        if isinstance(reply, Exception):
            raise reply
        return reply
