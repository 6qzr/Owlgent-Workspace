# ADR 0001: Conversation state in an async PostgreSQL checkpointer

- **Status:** accepted
- **Date:** 2026-11-02
- **Deciders:** @MohammedAlkahali, team
- **Related:** Spike R1 #2, [R1 note](../research/R1-checkpoints.md), #10

## Context
Patients must be able to resume a conversation by ID with its full context, even after the API restarts (FR-1). Paused approvals must survive a restart too (FR-5).

## Options considered
1. **InMemorySaver**: simple, but everything is lost when the process exits.
2. **SqliteSaver**: persistent, but the brief forbids any database other than PostgreSQL.
3. **PostgresSaver / AsyncPostgresSaver**: persistent in our PostgreSQL. The R1 experiment showed history surviving new processes and `docker compose down` / `up`.

## Decision
- Use `AsyncPostgresSaver` on the shared psycopg `AsyncConnectionPool`, configured with `autocommit=True`, `row_factory=dict_row` and `prepare_threshold=0`.
- Use one `thread_id` per conversation, equal to the server-generated UUID `conversation_id`.
- Run `setup()` once at API start-up.

## Consequences
- Conversations and paused approvals survive restarts and redeploys.
- The checkpoint keeps the full history. Only the last `CLASSIFY_HISTORY_WINDOW` messages (10, in `agent/prompts.py`) are sent to the model.
  *Update 2026-11-05 (#102): this was first planned as a `MAX_HISTORY_MESSAGES` setting; it was never read and was removed in #100.*
- Thread IDs never come from user input, so one patient can't read another's conversation.
- The checkpoint tables grow by about 3 rows per turn, which is acceptable for v1.
- `docker compose down -v` deletes all conversations. This is documented in the README.
