"""The v1 behaviour still works through the real servers: booking, the pharmacy, and clinic
document questions."""

import json

import pytest

from api.llm import FakeLLM, LLMReply
from tests.conftest import TokenFactory
from tests.e2e.helpers import call_tool, chat, tool_call, tool_results

pytestmark = pytest.mark.anyio


async def test_booking_through_chat(servers: dict[str, str], make_token: TokenFactory) -> None:
    """A booking made through /chat shows up in the patient's own list."""
    token = make_token("user-a")
    llm = FakeLLM(
        [
            tool_call("book_appointment", doctor="Dr. Lina", date="2026-12-15", time="11:00"),
            LLMReply(content="Booked with Dr. Lina on 2026-12-15 at 11:00."),
        ]
    )

    reply = await chat(llm, "Book me with Dr. Lina on 15 December at 11:00", token)
    mine = await call_tool(servers["appointments"], "list_my_appointments", {}, token)

    assert reply == "Booked with Dr. Lina on 2026-12-15 at 11:00."
    booked = json.loads(tool_results(llm)[0])
    assert booked["doctor"] == "Dr. Lina" and booked["status"] == "booked"
    assert any(item["appointment_id"] == booked["appointment_id"] for item in mine)


async def test_the_same_slot_cannot_be_booked_twice(
    servers: dict[str, str], make_token: TokenFactory
) -> None:
    """A slot someone else holds is refused."""
    slot = {"doctor": "Dr. Huda", "date": "2026-12-01", "time": "09:00"}  # user-a's seed booking

    result = await call_tool(
        servers["appointments"], "book_appointment", slot, make_token("user-b")
    )

    assert result == {"error": "slot already booked"}


async def test_pharmacy_view_and_add(servers: dict[str, str], make_token: TokenFactory) -> None:
    """Adding stock changes what view_inventory shows."""
    token = make_token("user-a")

    added = await call_tool(
        servers["pharmacy"], "add_inventory", {"medicine": "Paracetamol", "quantity": 10}, token
    )
    stock = await call_tool(servers["pharmacy"], "view_inventory", {}, token)

    assert added == {"medicine": "Paracetamol", "stock": 130}
    assert {"medicine": "Paracetamol", "stock": 130} in stock


async def test_clinic_doc_question_finds_the_doctors_pdf(
    servers: dict[str, str], make_token: TokenFactory
) -> None:
    """ "Which doctor sees skin problems?" finds the dermatologist in doctors.pdf."""
    question = "Which doctor sees skin problems?"
    llm = FakeLLM(
        [
            tool_call("search_clinic_docs", query=question),
            LLMReply(content="Dr. Lina Al Noor, our dermatologist."),
        ]
    )

    await chat(llm, question, make_token("user-a"))

    hits = json.loads(tool_results(llm)[0])
    assert hits[0]["source"] == "doctors.pdf"
    assert "Dermatolog" in hits[0]["text"]


async def test_an_unrelated_question_shows_the_model_an_empty_list(
    servers: dict[str, str], make_token: TokenFactory
) -> None:
    """A question the documents don't cover gives the model "[]", not an error or nothing."""
    llm = FakeLLM(
        [
            tool_call("search_clinic_docs", query="car insurance"),
            LLMReply(content="Sorry, I don't have information about that."),
        ]
    )

    await chat(llm, "Do you sell car insurance?", make_token("user-a"))

    assert tool_results(llm) == ["[]"]
