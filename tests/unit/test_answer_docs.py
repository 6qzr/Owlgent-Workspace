"""Tests for answering clinic questions using retrieved documents."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes.answer_docs import answer_from_docs
from clinic_assistant.agent.prompts import DONT_KNOW
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.kb.retriever import Retriever
from clinic_assistant.llm import LLM


def make_retriever() -> MagicMock:
    """Create a fake retriever without PostgreSQL."""

    retriever = MagicMock(spec=Retriever)
    retriever.search = AsyncMock(return_value=[])

    return retriever


def make_llm() -> MagicMock:
    """Create a fake LLM without calling a real API."""

    llm = MagicMock(spec=LLM)
    llm.complete = AsyncMock(return_value="The clinic opens at 8 AM.")

    return llm


def make_config(retriever: MagicMock) -> RunnableConfig:
    """Inject the fake retriever into the graph configuration."""

    return {
        "configurable": {
            "retriever": retriever,
        }
    }


async def test_answer_from_docs_success() -> None:
    """Generate an answer and include the document source."""

    retriever = make_retriever()
    llm = make_llm()

    retriever.search.return_value = [
        {
            "content": "The clinic opens at 8 AM.",
            "source": "opening_hours.md",
            "chunk_index": 0,
            "score": 0.15,
        }
    ]

    state: ConversationState = {
        "messages": [HumanMessage("What time does the clinic open?")],
    }

    result = await answer_from_docs(state, make_config(retriever), llm)

    assert "The clinic opens at 8 AM." in result["reply"]
    assert "opening_hours.md" in result["reply"]
    assert result["sources"] == ["opening_hours.md"]

    retriever.search.assert_awaited_once_with("What time does the clinic open?")
    llm.complete.assert_awaited_once()


async def test_answer_from_docs_no_results() -> None:
    """Return I don't know without calling the LLM when no documents match."""

    retriever = make_retriever()
    llm = make_llm()

    state: ConversationState = {
        "messages": [HumanMessage("Can I get a free car?")],
    }

    result = await answer_from_docs(state, make_config(retriever), llm)

    assert result["reply"] == DONT_KNOW
    assert result["sources"] == []

    retriever.search.assert_awaited_once_with("Can I get a free car?")
    llm.complete.assert_not_awaited()


async def test_answer_from_docs_unique_sources() -> None:
    """Include each source document only once."""

    retriever = make_retriever()
    llm = make_llm()

    retriever.search.return_value = [
        {
            "content": "The clinic opens at 8 AM.",
            "source": "opening_hours.md",
            "chunk_index": 0,
            "score": 0.15,
        },
        {
            "content": "The clinic closes at 5 PM.",
            "source": "opening_hours.md",
            "chunk_index": 1,
            "score": 0.12,
        },
        {
            "content": "The clinic is closed on Friday.",
            "source": "clinic_policy.md",
            "chunk_index": 0,
            "score": 0.10,
        },
    ]

    state: ConversationState = {
        "messages": [HumanMessage("What are the clinic hours?")],
    }

    result = await answer_from_docs(state, make_config(retriever), llm)

    assert result["sources"] == [
        "opening_hours.md",
        "clinic_policy.md",
    ]


async def test_answer_from_docs_llm_does_not_know() -> None:
    """Do not attach sources when the LLM cannot answer from the passages."""

    retriever = make_retriever()
    llm = make_llm()

    retriever.search.return_value = [
        {
            "content": "The clinic opens at 8 AM.",
            "source": "opening_hours.md",
            "chunk_index": 0,
            "score": 0.15,
        }
    ]
    llm.complete.return_value = DONT_KNOW

    state: ConversationState = {
        "messages": [HumanMessage("Which dentist works at the clinic?")],
    }

    result = await answer_from_docs(state, make_config(retriever), llm)

    assert result["reply"] == DONT_KNOW
    assert result["sources"] == []

    retriever.search.assert_awaited_once()
    llm.complete.assert_awaited_once()


async def test_answer_from_docs_empty_question() -> None:
    """Return I don't know without searching when there is no question."""

    retriever = make_retriever()
    llm = make_llm()

    state: ConversationState = {
        "messages": [HumanMessage("")],
    }

    result = await answer_from_docs(state, make_config(retriever), llm)

    assert result["reply"] == DONT_KNOW
    assert result["sources"] == []

    retriever.search.assert_not_awaited()
    llm.complete.assert_not_awaited()


async def test_answer_from_docs_uses_latest_patient_message() -> None:
    """Search using the latest patient message, not an earlier message."""

    retriever = make_retriever()
    llm = make_llm()

    state: ConversationState = {
        "messages": [
            HumanMessage("What are the insurance policies?"),
            AIMessage("I can help with that."),
            HumanMessage("What time does the clinic open?"),
        ],
    }

    await answer_from_docs(state, make_config(retriever), llm)

    retriever.search.assert_awaited_once_with("What time does the clinic open?")


async def test_answer_from_docs_missing_retriever() -> None:
    """Raise an error when no retriever is configured."""

    llm = make_llm()

    state: ConversationState = {
        "messages": [HumanMessage("What are your opening hours?")],
    }

    with pytest.raises(
        RuntimeError,
        match="retriever is not configured",
    ):
        await answer_from_docs(
            state,
            {"configurable": {}},
            llm,
        )

    llm.complete.assert_not_awaited()
