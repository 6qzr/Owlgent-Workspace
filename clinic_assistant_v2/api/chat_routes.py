"""POST /chat: one patient message in, the assistant's reply out."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.agent import answer
from api.config import MAX_MESSAGE_CHARS
from api.dependencies import LLMDep, SettingsDep, UserTokenDep
from api.llm import LLMUnavailable
from api.mcp_tools import McpToolbox

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    """What the patient typed."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatReply(BaseModel):
    """What the assistant answers."""

    reply: str


@router.post("/chat")
async def chat(
    body: ChatRequest, token: UserTokenDep, settings: SettingsDep, llm: LLMDep
) -> ChatReply:
    """Answer the signed-in patient; their JWT goes with every MCP tool call."""
    toolbox = McpToolbox(settings.mcp_server_urls, token)
    try:
        reply = await answer(body.message, llm, toolbox)
    except LLMUnavailable as error:
        logger.warning("Chat model unavailable: %s", error)
        raise HTTPException(
            status_code=503, detail="The assistant is unavailable right now. Try again soon."
        ) from error
    return ChatReply(reply=reply)
