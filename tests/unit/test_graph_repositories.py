"""build_graph hands injected repositories to the nodes that need them."""

from typing import Any, cast
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.graph import Repositories, build_graph, with_configurable
from clinic_assistant.agent.nodes import Update
from clinic_assistant.agent.nodes.approval import record_approval
from clinic_assistant.agent.state import ConversationState, PendingAction
from clinic_assistant.domain import ApprovalAction
from clinic_assistant.llm import FakeLLM
from clinic_assistant.repository.approvals import ApprovalsRepository


class FakeApprovals(ApprovalsRepository):
    """Records create() calls instead of touching PostgreSQL."""

    def __init__(self) -> None:
        super().__init__(cast(Any, None))  # never queried: create() is overridden
        self.created: list[tuple[UUID, int, ApprovalAction]] = []

    async def create(self, conversation_id: UUID, booking_id: int, action: ApprovalAction) -> int:
        self.created.append((conversation_id, booking_id, action))
        return 42


def pending_cancel() -> ConversationState:
    return {
        "messages": [],
        "pending_action": PendingAction(action=ApprovalAction.CANCEL, booking_id=7),
    }


async def test_injected_repository_reaches_record_approval() -> None:
    fake = FakeApprovals()
    node = with_configurable(record_approval, {"approval_repository": fake})
    thread = uuid4()

    update = await node(pending_cancel(), {"configurable": {"thread_id": str(thread)}})

    assert update == {"approval_id": 42}
    assert fake.created == [(thread, 7, ApprovalAction.CANCEL)]


async def test_value_set_by_the_caller_wins() -> None:
    injected, passed = FakeApprovals(), FakeApprovals()

    async def which(state: ConversationState, config: RunnableConfig) -> Update:
        return {"repo": config["configurable"]["approval_repository"]}

    node = with_configurable(which, {"approval_repository": injected})

    update = await node(pending_cancel(), {"configurable": {"approval_repository": passed}})

    assert update["repo"] is passed


def test_graph_builds_with_and_without_repositories() -> None:
    assert build_graph(FakeLLM()).get_graph().nodes
    assert build_graph(FakeLLM(), repositories=Repositories(approvals=FakeApprovals()))
