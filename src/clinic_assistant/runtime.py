"""The long-lived objects built once at start-up (main.py) and read by every request (api/)."""

from dataclasses import dataclass

from clinic_assistant.agent.graph import ConversationGraph
from clinic_assistant.repository.db import DictPool


@dataclass(frozen=True)
class Runtime:
    """Long-lived objects built once at start-up and shared by every request."""

    graph: ConversationGraph
    pool: DictPool
