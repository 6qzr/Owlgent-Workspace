"""Both adapters honour the LLM interface; OpenAI failures surface as LLMError (502)."""

import json

import httpx2 as httpx  # the HTTP library openai>=3 is built on
import openai
import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from clinic_assistant.llm import LLM, FakeLLM, LLMError, OpenAILLM

PROMPT = [HumanMessage("Do I need to fast before a blood test?")]


class Answer(BaseModel):
    intent: str
    confidence: float


def _completion(content: str | None, refusal: str | None = None) -> dict[str, object]:
    message = {"role": "assistant", "content": content, "refusal": refusal}
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "test-model",
        "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
    }


def _llm(handler: httpx.MockTransport) -> OpenAILLM:
    client = openai.AsyncOpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=handler),
    )
    return OpenAILLM(client, "test-model")


def _replying(status: int, body: dict[str, object]) -> httpx.MockTransport:
    return httpx.MockTransport(lambda _request: httpx.Response(status, json=body))


# ------------------------------------------------------------------ FakeLLM


async def test_fake_returns_scripted_replies_in_order_and_records_prompts() -> None:
    fake = FakeLLM(["first", Answer(intent="question", confidence=0.9)])
    llm: LLM = fake

    assert await llm.complete(PROMPT) == "first"
    assert await llm.parse(PROMPT, Answer) == Answer(intent="question", confidence=0.9)
    assert fake.calls == [PROMPT, PROMPT]


async def test_fake_raises_a_scripted_error() -> None:
    fake = FakeLLM([LLMError("model down")])

    with pytest.raises(LLMError, match="model down"):
        await fake.complete(PROMPT)


async def test_fake_fails_loudly_when_the_script_is_wrong() -> None:
    with pytest.raises(AssertionError, match="no scripted reply"):
        await FakeLLM().complete(PROMPT)
    with pytest.raises(AssertionError, match="expected a str"):
        await FakeLLM([Answer(intent="book", confidence=1.0)]).complete(PROMPT)
    with pytest.raises(AssertionError, match="expected Answer"):
        await FakeLLM(["text"]).parse(PROMPT, Answer)


# ------------------------------------------------------------------ OpenAILLM.complete


async def test_complete_returns_the_reply_text() -> None:
    llm = _llm(_replying(200, _completion("Yes, fast for 8 hours.")))

    assert await llm.complete(PROMPT) == "Yes, fast for 8 hours."


async def test_complete_rejects_an_empty_reply() -> None:
    llm = _llm(_replying(200, _completion(None)))

    with pytest.raises(LLMError, match="empty"):
        await llm.complete(PROMPT)


async def test_complete_maps_a_server_error_to_llm_error() -> None:
    llm = _llm(_replying(500, {"error": {"message": "boom"}}))

    with pytest.raises(LLMError):
        await llm.complete(PROMPT)


async def test_complete_maps_a_timeout_to_llm_error() -> None:
    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow model", request=request)

    llm = _llm(httpx.MockTransport(time_out))

    with pytest.raises(LLMError):
        await llm.complete(PROMPT)


def test_create_applies_the_configured_timeout() -> None:
    llm = OpenAILLM.create(api_key="test-key", model="test-model", timeout_seconds=7)

    assert llm._client.timeout == 7


# ------------------------------------------------------------------ OpenAILLM.parse


async def test_parse_returns_a_validated_object() -> None:
    body = json.dumps({"intent": "question", "confidence": 0.8})
    llm = _llm(_replying(200, _completion(body)))

    assert await llm.parse(PROMPT, Answer) == Answer(intent="question", confidence=0.8)


async def test_parse_maps_a_refusal_to_llm_error() -> None:
    llm = _llm(_replying(200, _completion(None, refusal="I can't help with that.")))

    with pytest.raises(LLMError):
        await llm.parse(PROMPT, Answer)


async def test_parse_maps_a_server_error_to_llm_error() -> None:
    llm = _llm(_replying(500, {"error": {"message": "boom"}}))

    with pytest.raises(LLMError):
        await llm.parse(PROMPT, Answer)


async def test_parse_maps_invalid_json_to_llm_error() -> None:
    llm = _llm(_replying(200, _completion('{"intent": "question"}')))

    with pytest.raises(LLMError):
        await llm.parse(PROMPT, Answer)
