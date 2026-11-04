"""Answer clinic questions from the clinic documents and name the source.

Owner: @NoorAlbusaidi (#13)."""

from typing import cast

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.kb.retriever import Retriever
from clinic_assistant.llm import LLM


async def answer_from_docs(
    state: ConversationState,
    config: RunnableConfig,
    llm: LLM,
) -> Update:
    """Answer only from retrieved passages, or say I don't know."""

    # 1. Get the patient's latest question.
    question = next(
        (
            str(message.content)
            for message in reversed(state["messages"])
            if isinstance(message, HumanMessage)
        ),
        "",
    )

    if not question.strip():
        return {"sources": [], **reply_update("I don't know")}

    # 2. Get the retriever injected by the graph.
    configurable = config.get("configurable", {})
    retriever = cast(Retriever | None, configurable.get("retriever"))

    if retriever is None:
        return {"sources": [], **reply_update("I don't know")}

    # 3. Search the clinic documents.
    chunks = await retriever.search(question)

    # 4. If no relevant documents were found, don't call the LLM.
    if not chunks:
        return {"sources": [], **reply_update("I don't know")}

    # 5. Collect unique source document names.
    sources = list(dict.fromkeys(str(chunk["source"]) for chunk in chunks))

    # 6. Prepare the retrieved passages for the LLM.
    passages = "\n\n".join(f"Source: {chunk['source']}\n{chunk['content']}" for chunk in chunks)

    messages: list[AnyMessage] = [
        SystemMessage(
            content=(
                "You are a clinic front-desk assistant. "
                "Answer the patient's question using ONLY the clinic "
                "document passages provided. Do not use outside knowledge "
                "or invent information. If the passages do not contain "
                "enough information, say that you don't know. "
                "Give a clear and simple answer."
            )
        ),
        HumanMessage(
            content=(
                f"Patient question:\n{question}\n\nRetrieved clinic document passages:\n{passages}"
            )
        ),
    ]

    # 7. Ask the LLM to generate an answer.
    answer = await llm.complete(messages)

    # 8. Include the source names in the final answer and graph state.
    answer = f"{answer.strip()}\n\nSource: {', '.join(sources)}"

    return {"sources": sources, **reply_update(answer)}
