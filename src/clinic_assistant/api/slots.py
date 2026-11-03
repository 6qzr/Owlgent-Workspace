"""API endpoint for finding free appointment slots."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from clinic_assistant.repository.slots import SlotsRepository

router = APIRouter(prefix="/api/v1/slots", tags=["Slots"])


class SlotResponse(BaseModel):
    """One available appointment slot."""

    id: int
    doctor_id: int
    doctor_name: str
    specialty: str
    starts_at: datetime
    ends_at: datetime


def get_slots_repository(request: Request) -> SlotsRepository:
    """Read the repository provided by the app at startup."""

    repository = getattr(request.app.state, "slots_repository", None)

    if not isinstance(repository, SlotsRepository):
        raise HTTPException(
            status_code=503,
            detail="Slots service is not available.",
        )

    return repository


@router.get("", response_model=list[SlotResponse])
async def get_free_slots(
    repository: Annotated[SlotsRepository, Depends(get_slots_repository)],
    specialty: Annotated[str | None, Query(min_length=1)] = None,
    doctor_id: Annotated[int | None, Query(gt=0)] = None,
    doctor_name: Annotated[str | None, Query(min_length=1)] = None,
    booking_date: Annotated[date | None, Query(alias="date")] = None,
) -> list[SlotResponse]:
    """Find real available appointments from PostgreSQL."""

    # Reject requests containing only spaces.
    for value in (specialty, doctor_name):
        if value is not None and not value.strip():
            raise HTTPException(
                status_code=422,
                detail="Search values cannot be blank.",
            )

    slots = await repository.find_free_slots(
        doctor_id=doctor_id,
        doctor_name=doctor_name.strip() if doctor_name else None,
        specialty=specialty.strip() if specialty else None,
        booking_date=booking_date,
    )

    return [SlotResponse.model_validate(slot) for slot in slots]
