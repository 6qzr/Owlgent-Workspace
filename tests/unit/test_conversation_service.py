"""Turning graph state into a turn result: only what changed this turn is reported."""

from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from clinic_assistant.domain import Intent
from clinic_assistant.services.conversation import (
    HistoryMessage,
    TurnStatus,
    to_history,
    turn_result,
)

FIRST_TURN: dict[str, Any] = {
    "messages": [HumanMessage("What are your hours?"), AIMessage("8 to 4.")],
    "sources": ["hours.md"],
    "reply": "8 to 4.",
}


def test_reply_and_sources_from_this_turn_are_reported() -> None:
    result = turn_result(before={}, after=FIRST_TURN, paused=False)

    assert result.reply == "8 to 4."
    assert result.sources == ["hours.md"]
    assert result.status is TurnStatus.ANSWERED
    assert result.approval_id is None


def test_values_left_from_an_earlier_turn_are_not_reported() -> None:
    after = {
        **FIRST_TURN,
        "messages": [*FIRST_TURN["messages"], HumanMessage("Hi"), AIMessage("Hello!")],
        "reply": "Hello!",
    }

    result = turn_result(before=FIRST_TURN, after=after, paused=False)

    assert result.reply == "Hello!"
    assert result.sources == []


def test_paused_turn_reports_the_new_approval_and_no_stale_reply() -> None:
    after = {
        **FIRST_TURN,
        "messages": [*FIRST_TURN["messages"], HumanMessage("Cancel booking 7")],
        "approval_id": 3,
    }

    result = turn_result(before=FIRST_TURN, after=after, paused=True)

    assert result.status is TurnStatus.AWAITING_APPROVAL
    assert result.approval_id == 3
    assert result.reply is None


# The checkpoint may hand the intent back as a plain string; it still counts.
@pytest.mark.parametrize("marker", [{"emergency": True}, {"intent": Intent.EMERGENCY.value}])
def test_emergency_flag_or_intent_gives_emergency_status(marker: dict[str, Any]) -> None:
    after = {"messages": [HumanMessage("Chest pain")], **marker}

    assert turn_result(before={}, after=after, paused=False).status is TurnStatus.EMERGENCY


def test_history_labels_patient_and_assistant() -> None:
    history = to_history(FIRST_TURN["messages"])

    assert history == [
        HistoryMessage(role="patient", content="What are your hours?"),
        HistoryMessage(role="assistant", content="8 to 4."),
    ]
