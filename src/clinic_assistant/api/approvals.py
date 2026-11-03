"""API endpoints for staff approvals."""

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from clinic_assistant.repository.approvals import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
)
from clinic_assistant.services.approval import (
    ApprovalResumeError,
    ApprovalService,
)

router = APIRouter(
    prefix="/api/v1/approvals",
    tags=["Approvals"],
)


class DecisionRequest(BaseModel):
    """Staff approval or rejection request."""

    approved: bool
    reason: str = Field(min_length=1)
    staff: str = Field(min_length=1)


def get_approval_service(request: Request) -> ApprovalService:
    """Get the approval service created at app startup."""

    service = getattr(
        request.app.state,
        "approval_service",
        None,
    )

    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Approval service is not available",
        )

    return cast(ApprovalService, service)


@router.get("")
async def list_pending_approvals(
    service: Annotated[
        ApprovalService,
        Depends(get_approval_service),
    ],
    status: Literal["pending"] = "pending",
) -> list[dict[str, Any]]:
    """List pending approvals from all conversations."""

    return await service.list_pending()


@router.post("/{approval_id}/decision")
async def decide_approval(
    approval_id: int,
    body: DecisionRequest,
    service: Annotated[
        ApprovalService,
        Depends(get_approval_service),
    ],
) -> dict[str, str]:
    """Approve or reject and resume the paused conversation."""

    try:
        return await service.decide(
            approval_id=approval_id,
            approved=body.approved,
            reason=body.reason,
            staff=body.staff,
        )

    except ApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Approval not found",
        ) from exc

    except ApprovalAlreadyDecidedError as exc:
        raise HTTPException(
            status_code=409,
            detail="Approval already decided",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except ApprovalResumeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Approval workflow could not finish",
        ) from exc
