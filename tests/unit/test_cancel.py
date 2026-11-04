"""Unit tests for preparing cancellation requests (Issue #17)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import CLARIFYING
from clinic_assistant.agent.nodes.cancel import (
    MISSING_BOOKING_ID,
    NOT_FOUND,
    prepare_cancel,
)
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.domain import ApprovalAction
from clinic_assistant.repository.approvals import ApprovalsRepository


def make_repository() -> MagicMock:
    """Create a mocked repository without PostgreSQL."""

    repository = MagicMock(spec=ApprovalsRepository)
    repository.find_cancellable_booking = AsyncMock(return_value=None)

    return repository


def make_config(
    repository: MagicMock,
    conversation_id: str,
) -> RunnableConfig:
    """Pass the current conversation and repository to LangGraph."""

    return {
        "configurable": {
            "thread_id": conversation_id,
            "approval_repository": repository,
        }
    }


async def test_prepare_cancel_own_booking() -> None:
    """A confirmed booking owned by the patient needs approval."""

    conversation_id = uuid4()
    repository = make_repository()

    repository.find_cancellable_booking.return_value = {
        "id": 10,
        "conversation_id": conversation_id,
        "slot_id": 5,
        "status": "confirmed",
    }

    state: ConversationState = {
        "messages": [],
        "entities": {
            "booking_id": 10,
        },
    }

    result = await prepare_cancel(
        state,
        make_config(repository, str(conversation_id)),
    )

    # Cancellation must go through staff approval.
    assert result["pending_action"] == {
        "action": ApprovalAction.CANCEL,
        "booking_id": 10,
    }

    # The repository must check the exact conversation.
    repository.find_cancellable_booking.assert_awaited_once_with(
        booking_id=10,
        conversation_id=conversation_id,
    )

    # No success message before staff approval.
    assert "reply" not in result


async def test_prepare_cancel_other_patients_booking() -> None:
    """A patient must not cancel another conversation's booking."""

    conversation_id = uuid4()
    repository = make_repository()

    # Ownership lookup returns None for another patient's booking.
    repository.find_cancellable_booking.return_value = None

    state: ConversationState = {
        "messages": [],
        "entities": {
            "booking_id": 20,
        },
    }

    result = await prepare_cancel(
        state,
        make_config(repository, str(conversation_id)),
    )

    assert result["pending_action"] is None
    assert result["reply"] == NOT_FOUND
    assert len(result["messages"]) == 1

    repository.find_cancellable_booking.assert_awaited_once_with(
        booking_id=20,
        conversation_id=conversation_id,
    )


async def test_prepare_cancel_unknown_booking() -> None:
    """An unknown booking must not enter the approval workflow."""

    repository = make_repository()

    state: ConversationState = {
        "messages": [],
        "entities": {
            "booking_id": 999,
        },
    }

    result = await prepare_cancel(
        state,
        make_config(repository, str(uuid4())),
    )

    assert result["pending_action"] is None
    assert result["reply"] == NOT_FOUND


async def test_prepare_cancel_missing_booking_id() -> None:
    """Ask the patient for a booking number when it is missing."""

    repository = make_repository()

    state: ConversationState = {
        "messages": [],
        "entities": {},
    }

    result = await prepare_cancel(
        state,
        make_config(repository, str(uuid4())),
    )

    assert result["pending_action"] is None
    assert result["reply"] == MISSING_BOOKING_ID
    assert result["messages"][0].response_metadata["reply_kind"] == CLARIFYING

    # No database query is needed.
    repository.find_cancellable_booking.assert_not_awaited()


async def test_prepare_cancel_invalid_booking_id() -> None:
    """A non-positive booking ID is not a valid cancellation target."""

    repository = make_repository()

    state: ConversationState = {
        "messages": [],
        "entities": {
            "booking_id": -5,
        },
    }

    result = await prepare_cancel(
        state,
        make_config(repository, str(uuid4())),
    )

    assert result["pending_action"] is None
    assert result["reply"] == MISSING_BOOKING_ID
    repository.find_cancellable_booking.assert_not_awaited()


async def test_prepare_cancel_repository_missing() -> None:
    """Missing repository configuration is a server error."""

    state: ConversationState = {
        "messages": [],
        "entities": {
            "booking_id": 10,
        },
    }

    config: RunnableConfig = {
        "configurable": {
            "thread_id": str(uuid4()),
        }
    }

    with pytest.raises(
        RuntimeError,
        match="Approval repository is not configured",
    ):
        await prepare_cancel(state, config)


async def test_prepare_cancel_thread_id_missing() -> None:
    """The graph must identify the patient's conversation."""

    repository = make_repository()

    state: ConversationState = {
        "messages": [],
        "entities": {
            "booking_id": 10,
        },
    }

    config: RunnableConfig = {
        "configurable": {
            "approval_repository": repository,
        }
    }

    with pytest.raises(
        RuntimeError,
        match="Conversation thread ID is missing",
    ):
        await prepare_cancel(state, config)


async def test_prepare_cancel_routing() -> None:
    """Only a valid pending cancellation enters record_approval."""

    from clinic_assistant.agent.routing import route_after_cancel

    pending_state: ConversationState = {
        "messages": [],
        "pending_action": {
            "action": ApprovalAction.CANCEL,
            "booking_id": 10,
        },
    }

    refused_state: ConversationState = {
        "messages": [],
        "pending_action": None,
    }

    assert route_after_cancel(pending_state) == "record_approval"
    assert route_after_cancel(refused_state) == "__end__"
