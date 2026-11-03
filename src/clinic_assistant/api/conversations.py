"""Conversation routes (docs/architecture.md §4): validate, call the service, map its errors."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, StringConstraints

from clinic_assistant.llm import LLMError
from clinic_assistant.services.conversation import (
    AwaitingApproval,
    ConversationNotFound,
    ConversationService,
    DatabaseUnavailable,
    TurnStatus,
)

# Bounds what one patient message can send to the model. Move to Settings later.
MAX_MESSAGE_CHARS = 2000

# Domain error → HTTP status and fixed detail; the exception text never reaches the client.
ERROR_RESPONSES: dict[type[Exception], tuple[int, str]] = {
    ConversationNotFound: (status.HTTP_404_NOT_FOUND, "Conversation not found"),
    AwaitingApproval: (status.HTTP_409_CONFLICT, "Conversation is waiting for a staff decision"),
    LLMError: (status.HTTP_502_BAD_GATEWAY, "The assistant could not answer; please try again"),
    DatabaseUnavailable: (status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable"),
}

router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations"])


class SendMessageRequest(BaseModel):
    """A patient message; surrounding whitespace is stripped before the length check."""

    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)
    ]


class ConversationCreated(BaseModel):
    """The server-generated id of a new conversation."""

    conversation_id: UUID


class MessageReply(BaseModel):
    """What one patient message produced."""

    reply: str | None
    status: TurnStatus
    sources: list[str]
    approval_id: int | None


class HistoryMessageOut(BaseModel):
    """One stored message."""

    role: str
    content: str


class ConversationOut(BaseModel):
    """Full history and current status of a conversation."""

    conversation_id: UUID
    status: TurnStatus
    messages: list[HistoryMessageOut]


def get_conversation_service(request: Request) -> ConversationService:
    """Build the service from the runtime opened at start-up."""
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Service is starting up")
    return ConversationService(runtime.graph, runtime.pool)


Service = Annotated[ConversationService, Depends(get_conversation_service)]


@contextmanager
def service_errors() -> Iterator[None]:
    """Turn the service's domain errors into their HTTP responses."""
    try:
        yield
    except tuple(ERROR_RESPONSES) as exc:
        code, detail = next(v for t, v in ERROR_RESPONSES.items() if isinstance(exc, t))
        raise HTTPException(code, detail) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(service: Service) -> ConversationCreated:
    """Start a conversation."""
    with service_errors():
        return ConversationCreated(conversation_id=await service.create_conversation())


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID, body: SendMessageRequest, service: Service
) -> MessageReply:
    """Send a patient message and return the assistant's turn."""
    with service_errors():
        result = await service.send_message(conversation_id, body.message)
    return MessageReply(
        reply=result.reply,
        status=result.status,
        sources=result.sources,
        approval_id=result.approval_id,
    )


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: UUID, service: Service) -> ConversationOut:
    """Return the full history and status of a conversation."""
    with service_errors():
        view = await service.get_conversation(conversation_id)
    return ConversationOut(
        conversation_id=conversation_id,
        status=view.status,
        messages=[HistoryMessageOut(role=m.role, content=m.content) for m in view.messages],
    )
