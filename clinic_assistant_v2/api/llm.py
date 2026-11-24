"""The chat model behind the agent: OpenAI in production, a scripted FakeLLM in tests."""

import json
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

import openai
from openai import AsyncOpenAI, omit

# One chat message in OpenAI's format: {"role": ..., "content": ..., ...}.
Message = dict[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call: its name, what it does and its JSON-schema arguments."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """One tool call the model asked for."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMReply:
    """The model's answer: text, tool calls, or both."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMUnavailable(Exception):
    """The chat model could not be reached or failed."""


class LLM(Protocol):
    """Anything that can answer a conversation, optionally asking for tools."""

    async def complete(self, messages: list[Message], tools: list[ToolSpec]) -> LLMReply:
        """Return the model's next reply to these messages."""
        ...


class OpenAILLM:
    """The production model: OpenAI chat completions with tool calling."""

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        """Create one OpenAI client with a request timeout."""
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=1)
        self._model = model

    async def complete(self, messages: list[Message], tools: list[ToolSpec]) -> LLMReply:
        """Ask OpenAI for the next reply; turn any API failure into LLMUnavailable."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                # Our messages are plain dicts in OpenAI's own format.
                messages=cast(Any, messages),
                tools=[to_openai_tool(tool) for tool in tools] if tools else omit,
            )
        except openai.OpenAIError as error:
            raise LLMUnavailable(f"OpenAI request failed: {type(error).__name__}") from error

        message = response.choices[0].message
        tool_calls = [
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=parse_arguments(call.function.arguments),
            )
            for call in message.tool_calls or []
            if call.type == "function"
        ]
        return LLMReply(content=message.content or "", tool_calls=tool_calls)


def to_openai_tool(tool: ToolSpec) -> Any:
    """Describe one tool in OpenAI's function-tool format."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def parse_arguments(raw: str) -> dict[str, Any]:
    """Parse the model's JSON arguments; anything that is not a JSON object becomes {}."""
    try:
        arguments = json.loads(raw or "{}")
    except ValueError:
        return {}
    return arguments if isinstance(arguments, dict) else {}


class FakeLLM:
    """A scripted model for tests: returns (or raises) the given replies in order."""

    def __init__(self, replies: list[LLMReply | Exception]) -> None:
        """Remember the script, and record every call made to it."""
        self._replies = list(replies)
        self.calls: list[tuple[list[Message], list[ToolSpec]]] = []

    async def complete(self, messages: list[Message], tools: list[ToolSpec]) -> LLMReply:
        """Record the call and return the next scripted reply."""
        self.calls.append((list(messages), list(tools)))
        if not self._replies:
            raise AssertionError("FakeLLM ran out of scripted replies")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
