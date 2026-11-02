"""R1 spike, step 2: prove the checkpointer survives a process restart (PostgreSQL)."""

import operator
import os
import sys
from typing import Annotated, TypedDict

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph

DB_URI = os.environ.get(
    "DATABASE_URL", "postgresql://clinic:clinic@localhost:5432/clinic?connect_timeout=5"
)


class State(TypedDict):
    messages: Annotated[list[str], operator.add]


def reply(state: State) -> dict:
    """One tiny node: answer with how many messages it can see."""
    seen = len(state["messages"])
    return {"messages": [f"(assistant) I can see {seen} message(s) in this conversation."]}


builder = StateGraph(State)
builder.add_node("reply", reply)
builder.add_edge(START, "reply")
builder.add_edge("reply", END)

thread_id, text = sys.argv[1], sys.argv[2]

with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()
    graph = builder.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"messages": [f"(patient) {text}"]}, config)
    print(f"--- thread_id={thread_id!r} ---")
    for line in result["messages"]:
        print("   ", line)