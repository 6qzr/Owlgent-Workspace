# R1: Conversation checkpoints

**Owner:** MohammedAlkahali · **Spike issue:** #2 · **Experiment:** experiments/r1_checkpoints/


## Question

How do we keep each patient's conversation state, including a graph paused for staff
approval, so it survives an API restart or redeploy?


## Options compared

| Option | Survives restart? | Allowed by AGENTS.md? | Notes |
|---|---|---|---|
| `InMemorySaver` | No (RAM only) | Only for learning | Lost when the process exits |
| `SqliteSaver` | Yes (file) | **No**: "PostgreSQL only" | Ruled out without testing |
| `PostgresSaver` | Yes | Yes | Package `langgraph-checkpoint-postgres` |


## Sources (official documentation first)

- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- `langgraph-checkpoint-postgres` on PyPI: https://pypi.org/project/langgraph-checkpoint-postgres/
- Versions tested (from `uv.lock`): langgraph 1.2.19, langgraph-checkpoint-postgres 3.2.0, psycopg 3.3.6, PostgreSQL 17.6


## What the experiment showed

1. `step1_in_memory.py`: within one process, thread `ahmed` saw 3 messages on his 2nd turn,
   thread `fatima` saw 1. Memory is per `thread_id`. Running the script again started from 1:
   `InMemorySaver` loses everything on process exit.
2. Removing the `operator.add` reducer made each update replace the list instead of appending.
3. `step2_postgres.py`, each message in a **new process**: `ahmed`'s 2nd turn saw 3 messages,
   `fatima` saw 1. `setup()` created 4 tables (`checkpoints`, `checkpoint_blobs`,
   `checkpoint_writes`, `checkpoint_migrations`) in a database that was empty before.
4. After `docker compose down` + `up` (container destroyed, volume kept), `ahmed`'s 3rd turn
   saw 5 messages. State lives in the volume.
5. Each `invoke()` of this one-node graph wrote 3 checkpoint rows (steps -1, 0, 1):
   6 rows for 2 turns of `ahmed`. LangGraph saves after every step, so a crashed or paused
   run (e.g. `interrupt()`) resumes from the last finished step.



## Bounding what is sent to the model

The checkpoint stores the full conversation; the model only receives a recent window.
The node that calls the LLM slices the state before building the prompt, e.g.
`state["messages"][-MAX_HISTORY_MESSAGES:]`, with `MAX_HISTORY_MESSAGES` read from
configuration (AGENTS.md: thresholds live in config). The stored history is never
trimmed, so staff review and audit still see everything.
To check later: LangChain's `trim_messages` helper, which trims by token count instead of message count.



   ## Recommendation

Use `PostgresSaver` against the project's PostgreSQL service, with one `thread_id` per patient
conversation. Run `setup()` once at application startup, not per request. Read the connection
string from an environment variable and fail fast if it is missing.
Store the full history in the checkpoint; send only a configurable recent-message window to the model.


## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Checkpoint tables grow ~3+ rows per turn | Decide a retention/cleanup policy for old threads |
| `thread_id` collision would mix two patients' data | Generate thread IDs server-side (UUID), never from user input |
| `docker compose down -v` deletes all conversations | Document it; back up the volume on the VM |
| Hard-coded DB URL in the spike | App reads it from env config (AGENTS.md) |
| API is async (FastAPI); spike used the sync saver | Check `AsyncPostgresSaver` when building the API |


