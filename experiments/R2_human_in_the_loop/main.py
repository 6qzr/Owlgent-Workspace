
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


# Define the information shared between nodes.
class State(TypedDict):
    appointment_id: int
    status: str
    reason: str


# Pause the workflow and wait for staff approval.
def ask_staff(state: State) -> dict:
    decision = interrupt({
        "appointment_id": state["appointment_id"],
        "message": "Approve appointment cancellation?",
    })

    if decision["approved"]:
        return {
            "status": "approved",
            "reason": decision["reason"],
        }

    return {
        "status": "rejected",
        "reason": decision["reason"],
    }


# Create the LangGraph workflow.
builder = StateGraph(State)

# Add the approval function as a node.
builder.add_node("ask_staff", ask_staff)

# Connect START to the node, then to END.
builder.add_edge(START, "ask_staff")
builder.add_edge("ask_staff", END)

# Save the workflow state in memory.
workflow = builder.compile(checkpointer=InMemorySaver())


# Start a request and pause for staff approval.
def start_request(appointment_id: int) -> dict:
    config = {
        "configurable": {
            "thread_id": f"appointment-{appointment_id}"
        }
    }

    result = workflow.invoke(
        {
            "appointment_id": appointment_id,
            "status": "pending",
            "reason": "",
        },
        config=config,
    )

    print("Patient:", f"Cancel appointment {appointment_id}")
    print("Status: Waiting for staff approval")
    print("Interrupt:", result.get("__interrupt__"))

    return config


# Show the request waiting for approval.
def show_pending(config: dict) -> None:
    saved_state = workflow.get_state(config)

    if saved_state.interrupts:
        print("Pending request:", saved_state.interrupts[0].value)
    else:
        print("No pending request.")


# Continue the workflow with the staff decision.
def resume_request(
    config: dict,
    approved: bool,
    reason: str,
) -> None:
    result = workflow.invoke(
        Command(resume={
            "approved": approved,
            "reason": reason,
        }),
        config=config,
    )

    print("Final result:", result)


# Run both approval and rejection examples.
def main() -> None:
    print("=== Test 1: Approval ===")

    config1 = start_request(101)
    show_pending(config1)

    resume_request(
        config1,
        approved=True,
        reason="Approved by staff",
    )

    print("\n=== Test 2: Rejection ===")

    config2 = start_request(102)
    show_pending(config2)

    resume_request(
        config2,
        approved=False,
        reason="Rejected by staff",
    )


# Run the experiment when this file is executed.
if __name__ == "__main__":
    main()
