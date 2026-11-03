"""Emergency short-circuit: rules run before any LLM call (ADR 0005).

Owner: @6qzr (#12).
"""

from langchain_core.messages import HumanMessage

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.safety_rules import EMERGENCY_INSTRUCTION, is_emergency
from clinic_assistant.agent.state import ConversationState


def latest_patient_text(state: ConversationState) -> str:
    """Text of the newest patient message; earlier messages were already checked."""
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            return str(message.text)
    return ""


async def safety_gate(state: ConversationState) -> Update:
    """Flag the message as an emergency when it matches the emergency phrase list."""
    return {"emergency": is_emergency(latest_patient_text(state))}


async def emergency_reply(state: ConversationState) -> Update:
    """Answer with the fixed emergency instruction (never diagnosis or treatment advice).

    The staff flag (emergency_flags row) is added when the database is wired into the graph.
    """
    return reply_update(EMERGENCY_INSTRUCTION)
