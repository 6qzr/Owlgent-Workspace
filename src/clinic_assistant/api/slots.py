"""API endpoint for finding free appointment slots."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, StringConstraints

from clinic_assistant.api.deps import get_runtime
from clinic_assistant.repository.slots import SlotsRepository
from clinic_assistant.runtime import Runtime

router = APIRouter(prefix="/api/v1/slots", tags=["Slots"])


class SlotResponse(BaseModel):
    """One available appointment slot."""

    id: int
    doctor_id: int
    doctor_name: str
    specialty: str
    starts_at: datetime
    ends_at: datetime


# Trimmed, then required: a blank filter ("   ") is rejected with 422 like an empty one.
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def get_slots_repository(runtime: Annotated[Runtime, Depends(get_runtime)]) -> SlotsRepository:
    """Build the repository on the shared pool of the runtime opened at start-up."""
    return SlotsRepository(runtime.pool)


@router.get("", response_model=list[SlotResponse])
async def get_free_slots(
    repository: Annotated[SlotsRepository, Depends(get_slots_repository)],
    specialty: Annotated[NonBlank | None, Query()] = None,
    doctor_id: Annotated[int | None, Query(gt=0)] = None,
    doctor_name: Annotated[NonBlank | None, Query()] = None,
    booking_date: Annotated[date | None, Query(alias="date")] = None,
) -> list[SlotResponse]:
    """Find real available appointments from PostgreSQL."""
    slots = await repository.find_free_slots(
        doctor_id=doctor_id,
        doctor_name=doctor_name,
        specialty=specialty,
        booking_date=booking_date,
    )

    return [SlotResponse.model_validate(slot) for slot in slots]
