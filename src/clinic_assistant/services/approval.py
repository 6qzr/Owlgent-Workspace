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
        """Resume the paused conversation with the staff decision; return the patient's reply.

        The request was validated by the API, and apply_decision raises if the database update
        fails, so the result only needs to show that the run finished with a reply.
        """
        approval = await self.repository.get_by_id(approval_id)

        if approval is None:
            raise ApprovalNotFoundError("Approval not found")

        if approval["status"] != ApprovalStatus.PENDING:
            raise ApprovalAlreadyDecidedError("Approval already decided")

        config: RunnableConfig = {"configurable": {"thread_id": str(approval["conversation_id"])}}
        decision = {"approved": approved, "reason": reason, "staff": staff}
        try:
            result = await self.graph.ainvoke(Command(resume=decision), config=config)
        except (
            ApprovalAlreadyDecidedError,
            ApprovalNotFoundError,
        ):
            raise
        except Exception as exc:
            raise ApprovalResumeError("Could not resume the approval workflow") from exc

        if "__interrupt__" in result:
            raise ApprovalResumeError("Approval workflow is still paused")
        reply = result.get("reply")
        if not isinstance(reply, str) or not reply:
            raise ApprovalResumeError("Workflow did not return a reply")
        return {"outcome": reply}
