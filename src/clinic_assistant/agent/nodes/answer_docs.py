"""Answer clinic questions from the clinic documents and name the source.

Owner: @NoorAlbusaidi (#13). Stubs from the graph skeleton: replace the bodies, keep the names.
"""

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.llm import LLM


async def answer_from_docs(state: ConversationState, config: RunnableConfig, llm: LLM) -> Update:
    """Answer only from retrieved passages, or say I don't know.

    config["configurable"]["retriever"] is the kb Retriever (wired in graph.py).
    """
    return reply_update("I don't know yet.")
