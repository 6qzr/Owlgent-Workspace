"""Staff view of flagged emergency messages (FR-6); built from the runtime like the other routes."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from clinic_assistant.api.deps import get_runtime
from clinic_assistant.repository.emergencies import EmergencyFlagsRepository
from clinic_assistant.runtime import Runtime

router = APIRouter(prefix="/api/v1/emergencies", tags=["Emergencies"])


class EmergencyFlagOut(BaseModel):
    """One flagged message."""

    id: int
    conversation_id: UUID
    message: str
    created_at: datetime


def get_flags_repository(
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> EmergencyFlagsRepository:
    """Build the repository on the shared pool of the runtime opened at start-up."""
    return EmergencyFlagsRepository(runtime.pool)


@router.get("")
async def list_emergencies(
    flags: Annotated[EmergencyFlagsRepository, Depends(get_flags_repository)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[EmergencyFlagOut]:
    """Newest flagged messages first."""
    return [EmergencyFlagOut(**flag) for flag in await flags.list_recent(limit)]
