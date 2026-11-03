# Day 1: Sprint planning (2026-11-02)

**Facilitator:** @6qzr (team lead: Product Owner + Scrum Master)
**Attendees:** @6qzr, @MohammedAlkahali, @baraah34, @NoorAlbusaidi
**Schedule:** shifted to the team's 14:00–17:00 session. The planning sign-off moved to 17:00 (see #6).

## 1. Kick-off
- @6qzr confirmed as lead.
- Scope rule: every Must (FR-1 to FR-7) is merged before any Should or Could starts.
- Tracking: GitHub Issues and a Projects board instead of ClickUp. Our team repository's guidelines already use GitHub issue IDs (ADR 0004).
- Assumptions agreed and recorded in #6:
  - "Same-day" uses Asia/Muscat time.
  - There is no patient authentication; a booking is tied to its `conversation_id`.
  - A patient can cancel only bookings from their own conversation.
  - A pending same-day booking holds its slot.
  - While waiting for approval, the patient sees `awaiting_approval`.
  - English only in v1.

## 2. Parallel start: spikes and infra
| Slot | Owner | Issue | Output |
|---|---|---|---|
| R1 Checkpoints | @MohammedAlkahali | #2 | `docs/research/R1-checkpoints.md`, `experiments/r1_checkpoints/` (PR #9) |
| R2 Human in the loop | @baraah34 | #3 | `docs/research/R2-human-in-the-loop.md`, experiment (PR #7) |
| R3 RAG | @NoorAlbusaidi | #4 | `docs/research/R3-rag.md`, `experiments/r3_rag/` (PR #8) |
| Infra | @6qzr | #1 | Repo skeleton, CI (lint, typecheck, test, compose-up), templates, branch protection (PR #5) |

## 3. Spike share-out: decisions
- **R1:** `AsyncPostgresSaver`, with one `thread_id` per conversation (a server-generated UUID) and `setup()` run once at start-up (ADR 0001).
- **R2:** a real `interrupt()` and `Command(resume=…)`. The approval row is written *before* the pausing node, because the interrupted node re-runs on resume. Staff list pending items from an `approvals` table (ADR 0002).
- **R3:** PostgreSQL full-text search with a configurable threshold, answers that name their source, and an honest "I don't know". pgvector is a later option (ADR 0003).
- **All I/O is async:** `async def`, `ainvoke`, `AsyncConnectionPool`, `AsyncOpenAI` (ADR 0007).

## 4. Architecture review
Accepted in PR #57: `docs/architecture.md` (system view, workflow, approval sequence, API, data model, ownership) and ADRs 0001–0009.

## 5. Backlog, estimation and assignment
- Stories US-02 to US-11 posted as #10–#19, with acceptance criteria and points (43 in total, at most 11 per person, under the 30% cap).
- **Restructured for clarity** (see #6):
  - The separate task issues were merged back into their stories.
  - Every issue now has exactly **one owner** and lists only that owner's 1–3 h steps.
  - New issues: #55 (DB foundation, @NoorAlbusaidi) and #56 (VM, @6qzr).
- The DB foundation task moved from @MohammedAlkahali to @NoorAlbusaidi, to protect the critical path. Points are unchanged.

| Owner | Issues |
|---|---|
| @6qzr | #11 intent routing, #12 emergency, #56 VM |
| @MohammedAlkahali | #10 conversations, #18 compose + health, #19 release |
| @baraah34 | #14 slots, #16 approvals, #17 cancel |
| @NoorAlbusaidi | #55 DB foundation, #13 RAG answers, #15 booking |

## 6. Sprint goal
A patient conversation running on the VM can:
- ask a clinic question and get an answer that cites its source;
- book, or cancel through a real staff approval that survives a restart;
- trigger an emergency instruction that never reaches the LLM.

## Risks named
| Risk | Mitigation |
|---|---|
| Concurrent double booking | Partial unique index on `bookings(slot_id)` (ADR 0006) |
| Checkpointer tables in PostgreSQL | `setup()` at start-up; no manual SQL |
| Model latency | Timeouts on every LLM call; `LLMError` → 502 |
| Freeze slip | 1–3 h steps; merge at least once per build block |
