"""The emergency reply stores a staff flag, and only claims an alert when the flag was saved."""

from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes.safety import emergency_reply
from clinic_assistant.agent.safety_rules import EMERGENCY_INSTRUCTION, STAFF_ALERTED
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.repository.emergencies import EmergencyFlagsRepository


class FakeFlags(EmergencyFlagsRepository):
    """Records inserts, or fails like an unreachable database."""

    def __init__(self, fail: bool = False) -> None:
        super().__init__(cast(Any, None))  # never queried: insert() is overridden
        self.fail = fail
        self.inserted: list[tuple[UUID, str]] = []

    async def insert(self, conversation_id: UUID, message: str) -> int:
        if self.fail:
            raise psycopg.OperationalError("database down")
        self.inserted.append((conversation_id, message))
        return 1


STATE: ConversationState = {"messages": [HumanMessage("I have chest pain")]}


def config_for(thread: UUID) -> RunnableConfig:
    return {"configurable": {"thread_id": str(thread)}}


async def test_stored_flag_is_announced_to_the_patient() -> None:
    flags, thread = FakeFlags(), uuid4()

    update = await emergency_reply(STATE, config_for(thread), flags)

    assert flags.inserted == [(thread, "I have chest pain")]
    assert update["reply"] == EMERGENCY_INSTRUCTION + STAFF_ALERTED


async def test_database_failure_still_sends_the_instruction_without_the_alert_claim() -> None:
    update = await emergency_reply(STATE, config_for(uuid4()), FakeFlags(fail=True))

    assert update["reply"] == EMERGENCY_INSTRUCTION


async def test_no_repository_means_no_alert_claim() -> None:
    update = await emergency_reply(STATE, config_for(uuid4()))

    assert update["reply"] == EMERGENCY_INSTRUCTION


async def test_non_uuid_thread_is_not_fatal() -> None:
    flags = FakeFlags()

    update = await emergency_reply(STATE, {"configurable": {"thread_id": "test"}}, flags)

    assert flags.inserted == []
    assert update["reply"] == EMERGENCY_INSTRUCTION
