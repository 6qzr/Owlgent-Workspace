"""R1 spike, step 1: prove that a checkpointer remembers per thread_id."""

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


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

graph = builder.compile(checkpointer=InMemorySaver())


def send(thread_id: str, text: str) -> None:
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"messages": [f"(patient) {text}"]}, config)
    print(f"\n--- thread_id={thread_id!r} after sending {text!r} ---")
    for line in result["messages"]:
        print("   ", line)


send("ahmed", "Book me with a dermatologist")
send("ahmed", "Thursday please")
send("fatima", "What are your opening hours?")