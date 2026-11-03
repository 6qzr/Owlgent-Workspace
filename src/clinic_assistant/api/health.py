"""Health endpoint for checking API and database availability (FR-7)."""

import asyncio
import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ops"])

DB_CHECK_TIMEOUT_SECONDS = 2


class HealthResponse(BaseModel):
    """What /health reports."""

    status: str
    database: str


UNREACHABLE = HealthResponse(status="degraded", database="unreachable")


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health(request: Request) -> HealthResponse | JSONResponse:
    """Check whether the service and its database are reachable."""
    runtime = getattr(request.app.state, "runtime", None)
    try:
        if runtime is None:
            raise RuntimeError("runtime not opened")
        async with asyncio.timeout(DB_CHECK_TIMEOUT_SECONDS):
            async with runtime.pool.connection() as conn:
                await conn.execute("SELECT 1")
    except Exception as exc:
        logger.warning("Health check failed: database unreachable (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=UNREACHABLE.model_dump()
        )
    return HealthResponse(status="ok", database="ok")
