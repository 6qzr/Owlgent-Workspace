"""As user-a, "Show me the last medical record" answers with user-a's own record (Flu) and
never asks for an ID or patient number."""

import re

import pytest

from api.config import SYSTEM_PROMPT
from tests.conftest import TokenFactory
from tests.e2e.helpers import RelayLLM, chat

pytestmark = pytest.mark.anyio

# Any reply that asks the patient to identify themselves.
ID_QUESTION = re.compile(
    r"\b(your|the)\s+(id|identifier|patient\s*(id|number|no\.?)|national\s+id|file\s+number)\b"
    r"|\bwho\s+are\s+you\b|\bwhat\s+is\s+your\s+name\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize(("sub", "diagnosis"), [("user-a", "Flu"), ("user-b", "Sprained ankle")])
async def test_last_record_comes_from_the_token_without_asking_for_an_id(
    servers: dict[str, str], make_token: TokenFactory, sub: str, diagnosis: str
) -> None:
    """The reply holds the caller's own newest record and no question about who they are."""
    llm = RelayLLM("get_my_last_medical_record")

    reply = await chat(llm, "Show me the last medical record", make_token(sub))

    assert diagnosis in reply
    assert not ID_QUESTION.search(reply), reply
    assert llm.calls[0][0] == {"role": "system", "content": SYSTEM_PROMPT}


@pytest.mark.parametrize(
    "asking",
    [
        "What is your patient ID?",
        "Please give me your patient number.",
        "Can you tell me your ID first?",
        "Who are you?",
    ],
)
def test_the_id_question_check_catches_real_id_questions(asking: str) -> None:
    """The regex really does catch the questions we never want to ask."""
    assert ID_QUESTION.search(asking)


def test_the_id_question_check_allows_normal_replies() -> None:
    """A normal answer that mentions an appointment id is not an ID question."""
    reply = "Your last medical record is from 2026-10-02: Flu (Rest). Appointment 3 is booked."

    assert not ID_QUESTION.search(reply)
