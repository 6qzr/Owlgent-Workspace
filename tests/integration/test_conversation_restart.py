"""A conversation survives an API restart: a fresh pool, checkpointer and graph see it all (R1)."""

import pytest

from clinic_assistant.agent.checkpointer import open_checkpointer
from clinic_assistant.agent.graph import build_graph
from clinic_assistant.agent.nodes.classify import Classification
from clinic_assistant.config import Settings
from clinic_assistant.domain import Intent
from clinic_assistant.llm import FakeLLM
from clinic_assistant.repository.db import DictPool, create_pool
from clinic_assistant.services.conversation import ConversationService

pytestmark = pytest.mark.integration

OTHER = Classification(intent=Intent.OTHER, confidence=0.9)
POOL_OPEN_TIMEOUT_SECONDS = 10.0


async def start_app(settings: Settings, llm: FakeLLM) -> tuple[ConversationService, DictPool]:
    """What the API builds at start-up: a new pool, checkpointer and graph."""
    pool = create_pool(settings)
    await pool.open(wait=True, timeout=POOL_OPEN_TIMEOUT_SECONDS)
    saver = await open_checkpointer(pool)
    return ConversationService(build_graph(llm, saver), pool), pool


async def test_history_survives_a_restart(settings: Settings) -> None:
    # Before the restart: two turns.
    first, first_pool = await start_app(settings, FakeLLM([OTHER, OTHER]))
    conversation_id = await first.create_conversation()
    await first.send_message(conversation_id, "Hello")
    await first.send_message(conversation_id, "Are you there?")
    await first_pool.close()  # the "restart": every connection of the old app is gone

    # After the restart: a brand-new app instance continues the same conversation.
    llm_after = FakeLLM([OTHER])
    second, second_pool = await start_app(settings, llm_after)
    try:
        await second.send_message(conversation_id, "Still me")
        view = await second.get_conversation(conversation_id)
    finally:
        await second_pool.close()

    assert [m.content for m in view.messages if m.role == "patient"] == [
        "Hello",
        "Are you there?",
        "Still me",
    ]
    assert len(view.messages) == 6
    # The model saw the earlier turns too: system prompt + 5 stored messages.
    assert len(llm_after.calls[0]) == 1 + 5
