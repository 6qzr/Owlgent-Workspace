# ADR 0002: Staff approval as a real LangGraph interrupt

- **Status:** accepted
- **Date:** 2026-11-02
- **Deciders:** @baraah34, team
- **Related:** Spike R2 #3, [R2 note](../research/R2-human-in-the-loop.md), #16, #17

## Context
Every cancellation and every same-day booking must wait for staff approval, survive a restart, and then resume with the decision (FR-5). The brief lists "approval implemented as a flag instead of a real pause" as a red flag.

## Options considered
1. **Status flag in a table**: easy, but the workflow never really pauses.
2. **`interrupt()` + `Command(resume=...)` with a persistent checkpointer**: a real pause. The R2 experiment proved both the approve and the reject paths.

## Decision
- `record_approval` inserts an `approvals` row, which links the approval ID to the conversation's thread. It is a separate node that runs **before** `await_staff`.
- `await_staff` calls `interrupt()`, which pauses the graph.
- Staff list pending items from the `approvals` table.
- `POST /api/v1/approvals/{id}/decision` resumes that thread with `Command(resume={approved, reason, staff})`.

## Consequences
- The pause is real and is persisted by the checkpointer from ADR 0001.
- On resume, LangGraph re-runs the interrupted node from its start. Writes therefore never happen inside `await_staff`, so they aren't repeated.
- The `approvals` table is only an index for staff. The graph state remains the source of truth for the paused workflow.
- While a request is paused, the patient sees `status: awaiting_approval`. Sending another message returns 409 with a "still waiting" reply.
