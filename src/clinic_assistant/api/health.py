"""Health endpoint for checking API and database availability."""

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    """What /health reports."""

    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Check whether the service and its database are reachable."""
    try:
        async with asyncio.timeout(2):
            async with request.app.state.pool.connection() as conn:
                await conn.execute("SELECT 1")

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "degraded",
                "database": "unreachable",
            },
        ) from exc

    return HealthResponse(status="ok", database="ok")
