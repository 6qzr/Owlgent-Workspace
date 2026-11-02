# R2 — Human in the Loop Research

## 1. Research Question

How can LangGraph pause a workflow for staff approval and continue it later through an API? What does the patient see while waiting?

## 2. What is Human in the Loop?

Human in the Loop (HITL) means the AI waits for a human to approve or reject an important action.

In our clinic project, staff approval is needed for:

- Cancelling an appointment.
- Booking an appointment on the same day.

## 3. How Does It Work?

1. The patient asks to cancel an appointment.
2. LangGraph pauses the workflow.
3. The system saves the paused workflow.
4. The patient receives a waiting message.
5. Staff approve or reject the request through the API.
6. LangGraph continues with the staff decision.
7. The patient receives the final result.

## 4. Important Concepts

- **Interrupt:** Pauses the workflow.
- **Resume:** Continues the workflow after a decision.
- **Checkpointer:** Saves the workflow state.
- **Thread ID:** Helps find the correct paused workflow.
- **Pending Approval:** A request waiting for staff approval.

## 5. Options Compared

### Option 1: Simple Status Flag

- Advantage: Easy to create.
- Disadvantage: Does not actually pause LangGraph.

### Option 2: In-Memory Checkpointer

- Advantage: Easy for testing.
- Disadvantage: Loses saved state after restarting the application.

### Option 3: PostgreSQL Checkpointer

- Advantage: Saves workflow state across restarts.
- Disadvantage: Needs database setup.

## 6. What Does the Patient See?

**While waiting:**

"Your request is waiting for staff approval."

The API can return a status called `awaiting_approval` and an approval ID.

**If approved:**

"Your appointment has been cancelled."

**If rejected:**

"Your cancellation request was rejected."

These are suggested messages for our clinic system.
## 7. Experiment Results

**Experiment Goal:** Test how LangGraph pauses a workflow and continues after staff approval or rejection.

**What I Tested:**
- Used `interrupt()` to pause the workflow.
- Used `get_state()` to show the pending request.
- Used `Command(resume=...)` to continue the workflow.
- Tested approval and rejection using different Thread IDs.

**Results:**
- Appointment 101: Successfully approved.
- Appointment 102: Successfully rejected.
- Both requests paused and resumed correctly.

**What Still Needs to Be Done:**
- Connect the workflow to PostgreSQL so pending requests can be saved after a restart.
- Connect staff approval to a REST API in the final application.

**Conclusion:** The experiment successfully demonstrated LangGraph Human in the Loop using `InMemorySaver`.

## 8. Recommendation

I recommend using **LangGraph Interrupt and Resume with a PostgreSQL Checkpointer**.

Why?

- The workflow waits for staff approval.
- Pending requests are saved.
- The workflow can continue after a restart.
- The correct request can be resumed using its Thread ID.

We should agree with the R1 owner on how to save and identify paused workflows.

## 9. Risks

- Pending requests could be lost without persistent storage.
- The wrong Thread ID could resume the wrong request.
- A cancellation could happen before approval if the workflow is designed incorrectly.
- The same request could be processed twice.
- Database or API errors could prevent the workflow from continuing.

## 10. Conclusion

Human in the Loop helps keep our clinic system safe.

**Interrupt pauses the workflow. Checkpointer saves it. Thread ID identifies it. Resume continues it.**

PostgreSQL is recommended because our clinic needs to remember pending approvals even after a restart.

## 11. Sources

1. [LangGraph Official Documentation — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
2. [LangGraph Official Documentation — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
3. Clinic Front-Desk Assistant — Team Challenge, Section 5, Research R2.