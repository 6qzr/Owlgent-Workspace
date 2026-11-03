"""Service for staff approval decisions."""

from typing import Any, Protocol

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from clinic_assistant.domain import ApprovalStatus
from clinic_assistant.repository.approvals import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
    ApprovalsRepository,
)


class ApprovalGraph(Protocol):
    """Graph that resumes paused conversations."""

    async def ainvoke(
        self,
        input: Any,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        """Run or resume the graph."""


class ApprovalResumeError(Exception):
    """Approval workflow could not finish."""


class ApprovalService:
    """Manage pending approvals and staff decisions."""

    def __init__(
        self,
        repository: ApprovalsRepository,
        graph: ApprovalGraph,
    ) -> None:
        self.repository = repository
        self.graph = graph

    async def list_pending(self) -> list[dict[str, Any]]:
        """Get pending approvals from the database."""

        return await self.repository.list_pending()

    async def decide(
        self,
        approval_id: int,
        approved: bool,
        reason: str,
        staff: str,
    ) -> dict[str, str]:
        """Resume the conversation with the staff decision."""

        reason = reason.strip()
        staff = staff.strip()

        if not reason or not staff:
            raise ValueError("Reason and staff are required")

        # Get the pending approval.
        approval = await self.repository.get_by_id(approval_id)

        if approval is None:
            raise ApprovalNotFoundError("Approval not found")

        if approval["status"] != ApprovalStatus.PENDING:
            raise ApprovalAlreadyDecidedError("Approval already decided")

        # Resume the conversation that created this approval.
        thread_id = str(approval["conversation_id"])

        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "approval_repository": self.repository,
            }
        }

        decision = {
            "approved": approved,
            "reason": reason,
            "staff": staff,
        }

        # Resume the interrupted graph.
        try:
            result = await self.graph.ainvoke(
                Command(resume=decision),
                config=config,
            )
        except (
            ApprovalAlreadyDecidedError,
            ApprovalNotFoundError,
        ):
            raise
        except Exception as exc:
            raise ApprovalResumeError("Could not resume the approval workflow") from exc

        if "__interrupt__" in result:
            raise ApprovalResumeError("Approval workflow is still paused")

        # Verify that the graph returned the decision.
        saved_decision = result.get("decision")

        if not isinstance(saved_decision, dict):
            raise ApprovalResumeError("Workflow did not return a decision")

        if (
            saved_decision.get("approved") is not approved
            or saved_decision.get("reason") != reason
            or saved_decision.get("staff") != staff
        ):
            raise ApprovalResumeError("Workflow returned a different decision")

        # Verify that the database contains the final decision.
        updated = await self.repository.get_by_id(approval_id)

        expected_status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED

        if updated is None or updated["status"] != expected_status:
            raise ApprovalResumeError("Approval decision was not saved")

        reply = result.get("reply")

        if not isinstance(reply, str) or not reply:
            raise ApprovalResumeError("Workflow did not return a reply")

        return {"outcome": reply}
