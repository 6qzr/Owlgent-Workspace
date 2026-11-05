"""API endpoints for staff approvals."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints

from clinic_assistant.api.deps import get_runtime
from clinic_assistant.repository.approvals import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
    ApprovalsRepository,
)
from clinic_assistant.runtime import Runtime
from clinic_assistant.services.approval import (
    ApprovalResumeError,
    ApprovalService,
)

router = APIRouter(
    prefix="/api/v1/approvals",
    tags=["Approvals"],
)


# Trimmed, then required: "   " is rejected with 422 like an empty string.
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DecisionRequest(BaseModel):
    """Staff approval or rejection request; the only place the decision's text is validated."""

    approved: bool
    reason: NonBlank
    staff: NonBlank


def get_approval_service(runtime: Annotated[Runtime, Depends(get_runtime)]) -> ApprovalService:
    """Build the approval service from the runtime opened at start-up."""
    return ApprovalService(ApprovalsRepository(runtime.pool), runtime.graph)


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

    except ApprovalResumeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Approval workflow could not finish",
        ) from exc
