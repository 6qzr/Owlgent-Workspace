"""Graph nodes, one module per slice; each owner replaces the stub body in their own file."""

from typing import Any

from langchain_core.messages import AIMessage

type Update = dict[str, Any]


def reply_update(text: str) -> Update:
    """Update for a node that ends the turn: the reply text, also appended to the history."""
    return {"reply": text, "messages": [AIMessage(text)]}
