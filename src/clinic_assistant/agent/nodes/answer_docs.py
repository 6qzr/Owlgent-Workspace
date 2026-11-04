"""Answer clinic questions from the clinic documents and name the source."""

from typing import cast

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.nodes.safety import latest_patient_text
from clinic_assistant.agent.prompts import (
    ANSWER_DOCS_SYSTEM_PROMPT,
    DONT_KNOW,
)
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.kb.retriever import Retriever
from clinic_assistant.llm import LLM


async def answer_from_docs(
    state: ConversationState,
    config: RunnableConfig,
    llm: LLM,
) -> Update:
    """Answer only from retrieved passages, or say I don't know."""

    # Get the latest patient question using the shared helper.
    question = latest_patient_text(state)

    if not question.strip():
        return {"sources": [], **reply_update(DONT_KNOW)}

    # Get the retriever injected by the graph.
    configurable = config.get("configurable", {})
    retriever = cast(Retriever | None, configurable.get("retriever"))

    if retriever is None:
        raise RuntimeError("Document retriever is not configured")

    # Search the clinic documents.
    chunks = await retriever.search(question)

    # Do not call the LLM when no relevant documents are found.
    if not chunks:
        return {"sources": [], **reply_update(DONT_KNOW)}

    # Collect unique source document names.
    sources = list(dict.fromkeys(str(chunk["source"]) for chunk in chunks))

    # Prepare the retrieved passages for the LLM.
    passages = "\n\n".join(f"Source: {chunk['source']}\n{chunk['content']}" for chunk in chunks)

    messages: list[AnyMessage] = [
        SystemMessage(content=ANSWER_DOCS_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Patient question:\n{question}\n\nRetrieved clinic document passages:\n{passages}"
            )
        ),
    ]

    # Generate an answer using only the retrieved passages.
    answer = (await llm.complete(messages)).strip()

    # If the LLM does not know, do not attach a potentially misleading source.
    normalized_answer = answer.rstrip(".!?").strip().casefold()

    if normalized_answer == DONT_KNOW.casefold():
        return {"sources": [], **reply_update(DONT_KNOW)}

    # Include source names in the answer and graph state.
    answer = f"{answer}\n\nSource: {', '.join(sources)}"

    return {"sources": sources, **reply_update(answer)}
