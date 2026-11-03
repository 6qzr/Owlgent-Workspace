"""Liveness endpoint, so Docker and the VM can tell whether the API is working.

T-31 extends this with the database check and the 503 response.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    """What /health reports."""

    status: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report that the service is up."""
    return HealthResponse(status="ok")
