"""The LangGraph agent: llm -> (tools -> llm)* -> end, with a hard step limit."""

import json
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from api.config import MAX_AGENT_STEPS, STEP_LIMIT_REPLY, SYSTEM_PROMPT
from api.llm import LLM, LLMReply, Message, ToolSpec
from api.mcp_tools import McpToolbox


class AgentState(TypedDict):
    """One chat request's conversation and how many times the model has run."""

    # Append-only: the llm node adds its reply and the tools node adds the tool results.
    messages: Annotated[list[Message], operator.add]
    steps: int


def assistant_message(reply: LLMReply) -> Message:
    """Turn the model's reply into an OpenAI-format assistant message."""
    message: Message = {"role": "assistant", "content": reply.content}
    if reply.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in reply.tool_calls
        ]
    return message


def next_step(state: AgentState) -> str:
    """Run the tools if the model asked for them and the step limit allows; else stop."""
    last = state["messages"][-1]
    if last.get("tool_calls") and state["steps"] < MAX_AGENT_STEPS:
        return "tools"
    return END


def build_agent(llm: LLM, toolbox: McpToolbox, tools: list[ToolSpec]) -> CompiledStateGraph[Any]:
    """Build the graph for one request, wired to this user's toolbox."""

    async def call_llm(state: AgentState) -> dict[str, Any]:
        """Ask the model for its next reply, with the system prompt first."""
        prompt: list[Message] = [{"role": "system", "content": SYSTEM_PROMPT}, *state["messages"]]
        reply = await llm.complete(prompt, tools)
        return {"messages": [assistant_message(reply)], "steps": state["steps"] + 1}

    async def run_tools(state: AgentState) -> dict[str, Any]:
        """Run every tool call from the model's last reply, as the signed-in user."""
        results: list[Message] = []
        for call in state["messages"][-1]["tool_calls"]:
            arguments = json.loads(call["function"]["arguments"])
            content = await toolbox.call(call["function"]["name"], arguments)
            results.append({"role": "tool", "tool_call_id": call["id"], "content": content})
        return {"messages": results}

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", next_step, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    return graph.compile()


async def answer(message: str, llm: LLM, toolbox: McpToolbox) -> str:
    """Answer one patient message, calling MCP tools as needed."""
    tools = await toolbox.discover()
    agent = build_agent(llm, toolbox, tools)
    state = await agent.ainvoke({"messages": [{"role": "user", "content": message}], "steps": 0})

    last = state["messages"][-1]
    if last.get("tool_calls") or not last["content"]:
        # The model was still asking for tools when the step limit stopped it.
        return STEP_LIMIT_REPLY
    return str(last["content"])
