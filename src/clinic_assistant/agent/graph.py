"""Builds the conversation graph; matches docs/architecture.md §2. Only the lead edits this file."""

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Protocol, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from clinic_assistant.agent.nodes import Update
from clinic_assistant.agent.nodes.answer_docs import answer_from_docs
from clinic_assistant.agent.nodes.approval import (
    apply_decision,
    await_staff,
    notify_outcome,
    record_approval,
)
from clinic_assistant.agent.nodes.booking import confirm_booking, prepare_booking
from clinic_assistant.agent.nodes.cancel import prepare_cancel
from clinic_assistant.agent.nodes.clarify import clarify
from clinic_assistant.agent.nodes.classify import classify
from clinic_assistant.agent.nodes.safety import emergency_reply, safety_gate
from clinic_assistant.agent.nodes.scope import polite_scope_reply
from clinic_assistant.agent.nodes.slots import find_slots
from clinic_assistant.agent.routing import (
    route_after_booking,
    route_after_cancel,
    route_after_safety,
    route_intent,
)
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.kb.retriever import Retriever
from clinic_assistant.llm import LLM
from clinic_assistant.repository.approvals import ApprovalsRepository
from clinic_assistant.repository.bookings import BookingsRepository
from clinic_assistant.repository.emergencies import EmergencyFlagsRepository
from clinic_assistant.repository.slots import SlotsRepository

type ConversationGraph = CompiledStateGraph[
    ConversationState, None, ConversationState, ConversationState
]


class ConfigNode(Protocol):
    """A node that also takes the run config; LangGraph matches the `config` name."""

    def __call__(self, state: ConversationState, config: RunnableConfig) -> Awaitable[Update]: ...


@dataclass(frozen=True)
class Repositories:
    """Database access the nodes need; built from the shared pool at start-up."""

    approvals: ApprovalsRepository | None = None
    slots: SlotsRepository | None = None
    emergencies: EmergencyFlagsRepository | None = None
    bookings: BookingsRepository | None = None
    retriever: Retriever | None = None


def with_configurable(node: ConfigNode, values: dict[str, Any]) -> ConfigNode:
    """Wrap a node so it always finds `values` in config["configurable"].

    Keeps owners' nodes unchanged while the service never has to pass repositories itself.
    Values the caller already set (e.g. on resume) win.
    """

    async def run(state: ConversationState, config: RunnableConfig) -> Update:
        configurable = {**values, **config.get("configurable", {})}
        return await node(state, cast(RunnableConfig, {**config, "configurable": configurable}))

    return run


# Nodes that end the turn with a reply.
REPLY_NODES = (
    "emergency_reply",
    "clarify",
    "answer_from_docs",
    "find_slots",
    "polite_scope_reply",
    "confirm_booking",
    "notify_outcome",
)


def build_graph(
    llm: LLM,
    checkpointer: BaseCheckpointSaver[str] | None = None,
    repositories: Repositories | None = None,
) -> ConversationGraph:
    """Wire every node and route; LLM, checkpointer and repositories are injected (ADR 0008)."""
    repos = repositories or Repositories()
    approvals = {"approval_repository": repos.approvals} if repos.approvals else {}
    slots = {"slots_repository": repos.slots} if repos.slots else {}
    bookings = {"bookings_repository": repos.bookings} if repos.bookings else {}
    retriever = {"retriever": repos.retriever} if repos.retriever else {}

    async def classify_with_llm(state: ConversationState) -> Update:
        return await classify(state, llm)

    async def emergency_reply_with_flags(
        state: ConversationState, config: RunnableConfig
    ) -> Update:
        return await emergency_reply(state, config, repos.emergencies)

    async def answer_with_llm(state: ConversationState, config: RunnableConfig) -> Update:
        return await answer_from_docs(state, config, llm)

    builder = StateGraph(ConversationState)
    builder.add_node("safety_gate", safety_gate)
    builder.add_node("emergency_reply", emergency_reply_with_flags)
    builder.add_node("classify", classify_with_llm)
    builder.add_node("clarify", clarify)
    builder.add_node("answer_from_docs", with_configurable(answer_with_llm, retriever))
    builder.add_node("find_slots", with_configurable(find_slots, slots))
    builder.add_node("polite_scope_reply", polite_scope_reply)
    builder.add_node("prepare_booking", with_configurable(prepare_booking, bookings))
    builder.add_node("confirm_booking", confirm_booking)
    builder.add_node("prepare_cancel", with_configurable(prepare_cancel, approvals))
    builder.add_node("record_approval", with_configurable(record_approval, approvals))
    builder.add_node("await_staff", await_staff)
    builder.add_node("apply_decision", with_configurable(apply_decision, approvals))
    builder.add_node("notify_outcome", notify_outcome)

    builder.add_edge(START, "safety_gate")
    builder.add_conditional_edges("safety_gate", route_after_safety)
    builder.add_conditional_edges("classify", route_intent)
    builder.add_conditional_edges("prepare_booking", route_after_booking)
    builder.add_conditional_edges("prepare_cancel", route_after_cancel)
    builder.add_edge("record_approval", "await_staff")
    builder.add_edge("await_staff", "apply_decision")
    builder.add_edge("apply_decision", "notify_outcome")
    for node in REPLY_NODES:
        builder.add_edge(node, END)

    return builder.compile(checkpointer=checkpointer)
