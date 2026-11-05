"""Emergency short-circuit: rules run before any LLM call (ADR 0005).

Owner: @6qzr (#12).
"""

import logging

import psycopg
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import Update, conversation_id, reply_update
from clinic_assistant.agent.safety_rules import EMERGENCY_INSTRUCTION, STAFF_ALERTED, is_emergency
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.repository.emergencies import EmergencyFlagsRepository

logger = logging.getLogger(__name__)


def latest_patient_text(state: ConversationState) -> str:
    """Text of the newest patient message; earlier messages were already checked."""
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            return str(message.text)
    return ""


async def safety_gate(state: ConversationState) -> Update:
    """Flag the message as an emergency when it matches the emergency phrase list."""
    return {"emergency": is_emergency(latest_patient_text(state))}


async def flag_for_staff(
    state: ConversationState, config: RunnableConfig, flags: EmergencyFlagsRepository | None
) -> bool:
    """Store an emergency_flags row; any failure is logged and reported as False."""
    if flags is None:
        return False
    try:
        await flags.insert(conversation_id(config), latest_patient_text(state))
    except (psycopg.Error, TimeoutError, RuntimeError, ValueError) as exc:
        # The patient's text stays out of the log.
        logger.error("Could not store the emergency flag: %s", type(exc).__name__)
        return False
    return True


async def emergency_reply(
    state: ConversationState,
    config: RunnableConfig,
    flags: EmergencyFlagsRepository | None = None,
) -> Update:
    """Answer with the fixed emergency instruction (never diagnosis or treatment advice).

    The instruction is always sent, even if the database is down; the reply says staff were
    alerted only when the flag was actually stored.
    """
    alerted = await flag_for_staff(state, config, flags)
    return reply_update(EMERGENCY_INSTRUCTION + (STAFF_ALERTED if alerted else ""))
