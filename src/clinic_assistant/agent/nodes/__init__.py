"""Graph nodes, one module per slice; each owner replaces the stub body in their own file."""

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig

from clinic_assistant.repository.approvals import ApprovalsRepository

type Update = dict[str, Any]

# Stored on the reply message itself, so it belongs to exactly one turn and never goes stale.
# response_metadata is kept in the checkpoint but never sent to the model.
REPLY_KIND = "reply_kind"
CLARIFYING = "clarifying"


def reply_update(text: str, kind: str | None = None) -> Update:
    """Update for a node that ends the turn: the reply text, also appended to the history.

    `kind` marks special replies (e.g. CLARIFYING) so the service can report the turn's status.
    """
    metadata = {REPLY_KIND: kind} if kind else {}
    return {"reply": text, "messages": [AIMessage(text, response_metadata=metadata)]}


def get_repository(config: RunnableConfig) -> ApprovalsRepository:
    """The ApprovalsRepository graph.py injects into config; shared by the approval nodes."""
    repository = config.get("configurable", {}).get("approval_repository")
    if not isinstance(repository, ApprovalsRepository):
        raise RuntimeError("Approval repository is not configured")
    return repository


def reply_kind(message: BaseMessage) -> str | None:
    """The kind a node attached to its reply, or None for an ordinary answer."""
    kind = message.response_metadata.get(REPLY_KIND)
    return kind if isinstance(kind, str) else None
