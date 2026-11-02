# R2 — Human in the Loop Research

## 1. Research Question

How can LangGraph pause a workflow for staff approval and continue it later through an API? What does the patient see while waiting?

## 2. What is Human in the Loop?

Human in the Loop (HITL) means the AI waits for a human to approve or reject an important action.

In our clinic project, staff approval is needed for:

- Cancelling an appointment.
- Booking an appointment on the same day.

## 3. How Does It Work?

The proposed workflow for our clinic is:

1. The patient asks to cancel an appointment or make a same-day booking.
2. LangGraph pauses the workflow using `interrupt()`.
3. A checkpointer saves the paused workflow state.
4. The patient receives a waiting message.
5. Staff view pending requests and approve or reject through the API.
6. LangGraph resumes using `Command(resume=...)`.
7. The patient receives the final result.

Our experiment currently tests pause and resume directly in Python.

## 4. Important Concepts

- **Interrupt:** Pauses the workflow until a decision is provided.
- **Resume:** Continues the workflow after receiving the staff decision.
- **Checkpointer:** Saves the workflow state.
- **Thread ID:** Identifies the correct workflow.
- **Pending Approval:** A request waiting for staff approval.
- **Idempotency:** Makes an operation safe to repeat without creating duplicate results.

### Important: Node Execution After Resume

When LangGraph resumes a paused workflow, the interrupted node starts again from the beginning.

This means code before `interrupt()` can run twice.

For example, if we insert an approval record before `interrupt()`, it could create duplicate records when the node resumes.

To prevent this, we should create the approval record in an earlier node or make the database operation idempotent.

## 5. Options Compared

### Option 1: Simple Status Flag

- **Advantage:** Easy to implement.
- **Disadvantage:** Does not actually pause the LangGraph workflow.

### Option 2: In-Memory Checkpointer

- **Advantage:** Easy to use for experiments.
- **Disadvantage:** Saved state is lost when the application process restarts.

### Option 3: PostgreSQL Checkpointer

- **Advantage:** Can preserve workflow state across application restarts.
- **Disadvantage:** Requires database setup and integration.

## 6. What Does the Patient See?

**While waiting:**

"Your request is waiting for staff approval."

The API can return a status called `awaiting_approval` and an approval ID.

**If approved:**

"Your appointment has been cancelled."

**If rejected:**

"Your cancellation request was rejected."

These are suggested messages for our final clinic application.

## 7. Experiment Results

**Experiment Goal:** Test how LangGraph pauses a workflow and resumes after staff approval or rejection.

### What I Tested

- Used `interrupt()` to pause the workflow.
- Used `get_state()` to view a pending request.
- Used `Command(resume=...)` to continue the workflow.
- Tested approval and rejection using different Thread IDs.
- Used `InMemorySaver` to save the workflow state during the experiment.

### Results

- Appointment 101: Successfully paused and resumed with `approved`.
- Appointment 102: Successfully paused and resumed with `rejected`.
- Both tests worked successfully.

### Limitations

- PostgreSQL persistence has not been tested.
- Restarting the application container has not been tested.
- Staff approval through a REST API has not been implemented.
- Same-day booking approval has not been implemented in the experiment.
- The experiment changes the workflow status but does not update actual appointments in the database.

**Conclusion:** The experiment successfully demonstrated LangGraph Human in the Loop using `InMemorySaver`.

## 8. Recommendation

I recommend using **LangGraph `interrupt()` and `Command(resume=...)` with a PostgreSQL checkpointer** in the final clinic application.

### Why?

- The workflow can pause for staff approval.
- PostgreSQL checkpoints can preserve paused workflow states across restarts.
- The Thread ID helps resume the correct workflow.
- The system can continue after the staff makes a decision.

PostgreSQL restart persistence still needs to be tested with R1.

### Pending Approvals Design

`get_state()` requires a known `thread_id`, so it cannot directly list every pending approval across all conversations.

For the final application, we need an `approvals` table in PostgreSQL that stores:

- `approval_id`: Identifies the approval request.
- `thread_id`: Identifies the paused workflow.
- `status`: Shows whether the request is pending, approved, or rejected.
- `reason`: Stores the staff decision reason.

An approval record should be created before the workflow pauses, preferably in an earlier node.

Staff can use the approvals table to list pending requests through the API.

When staff approve or reject a request, the system uses its `thread_id` to resume the correct workflow with `Command(resume=...)`.

**The approvals table is only used to find and manage requests. The real workflow pause is handled by LangGraph `interrupt()`.**

## 9. Risks

- Pending requests could be lost without persistent checkpoints.
- The wrong Thread ID could resume the wrong workflow.
- A cancellation could happen before staff approval if the workflow is designed incorrectly.
- Code before `interrupt()` runs again when the node resumes, potentially creating duplicate approval records.
- The same approval request could be processed twice if repeated decisions are not handled safely.
- Database or API failures could prevent the workflow from continuing.

## 10. Conclusion

Human in the Loop helps keep our clinic system safe by requiring staff approval before important actions.

**Interrupt pauses the workflow. Checkpointer saves it. Thread ID identifies it. Resume continues it.**

For our final application, PostgreSQL checkpoints and an approvals table are recommended to manage pending requests safely.

## 11. Sources

1. [LangGraph Official Documentation — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
2. [LangGraph Official Documentation — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
3. Clinic Front-Desk Assistant — Team Challenge, Section 5, Research R2.