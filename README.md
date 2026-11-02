# Owlgent-Workspace: Clinic Front-Desk Assistant

A REST API driven by agentic LangGraph workflows for a small private clinic. It:
- answers patient messages from the clinic's own documents;
- finds and books appointments;
- pauses risky actions until front-desk staff approve them;
- never acts as a doctor.

Stack: Python 3.14 · uv · FastAPI · Pydantic · LangGraph · OpenAI SDK · PostgreSQL (psycopg, plain SQL, no ORM) · pytest · ruff · mypy · Docker Compose.

---

## Run it (anyone, from a fresh clone)

```bash
cp .env.example .env        # then set OPENAI_API_KEY
docker compose up -d --build
docker compose ps           # every service should be "healthy"
```

Nothing else is needed: no local Python, no manual SQL. PostgreSQL creates its schema and seed data from `db/` on first start.

## Develop

```bash
uv sync                      # creates .venv from uv.lock (never use pip)
uv run pre-commit install    # ruff + mypy before every commit
docker compose -f compose.yaml -f compose.dev.yaml up -d db   # local PostgreSQL on 127.0.0.1:5432
```

| Check | Command |
|---|---|
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format --check .` |
| Types | `uv run mypy` |
| Tests + coverage (≥ 80%) | `uv run pytest` |

To add a dependency, run `uv add <pkg>` (or `uv add --dev <pkg>`) and commit `uv.lock`. CI installs with `--frozen`.

## Project layout

| Path | Contents |
|---|---|
| `src/clinic_assistant/main.py` | App factory; wires dependencies at start-up |
| `src/clinic_assistant/api/` | Routes only |
| `src/clinic_assistant/services/` | The only layer that knows both API models and the graph |
| `src/clinic_assistant/agent/` | Graph state, nodes, graph construction |
| `src/clinic_assistant/llm/` | LLM adapter: real + deterministic fake |
| `src/clinic_assistant/kb/` | Clinic documents: loading, chunking, retrieval |
| `src/clinic_assistant/repository/` | PostgreSQL access (parameterised SQL) |
| `db/` | Schema and seed SQL, run automatically on first start |
| `tests/unit`, `tests/api`, `tests/integration` | Node/routing tests, HTTP tests, real-PostgreSQL tests |
| `docs/architecture.md`, `docs/adr/`, `docs/research/`, `docs/meetings/` | Design, decisions, spikes, Scrum records |
| `experiments/` | Spike experiments (not shipped) |

## Contribution guidelines

The rules are the same as in our team repository, using **GitHub Issues** as the tracker.

1. Pick an issue on the project board and assign yourself. Every branch needs an issue.
2. Get up to date: `git switch main` then `git pull`.
3. Create a branch: `git switch -c feature/<issue-number>-<github-user>-<short-title>` (or `fix/`, `chore/`, `docs/`, `release/`).
4. Commit small steps using Conventional Commits: `feat(agent): add safety gate`.
5. Before opening the PR, run `git fetch origin` then `git rebase origin/main`. Then push and open the PR:
   - **Title:** `#<issue-number>: <issue title>`.
   - **Body:** fill in the template, including `Closes #<n>`.
6. Move the issue to **Ready for Review**. A PR is linked to every card in that column.
7. Wait for **2 approvals**. Never approve your own PR. Resolve every review thread.
8. **Squash merge**, then delete the branch. The issue closes itself and moves to **Done**.

Keep PRs to one task and under about 400 changed lines. Merge at least once per build block.

## Team agreements

**Definition of Ready.** A story is ready when:
- it has acceptance criteria the team understands;
- it has an agreed estimate;
- it has no unresolved dependency;
- one person can finish it within half a day.

**Definition of Done.** A story is done when:
- it is merged to `main` through a PR with 2 approvals;
- lint, format, types and tests pass in CI;
- coverage is ≥ 80%;
- new behaviour has tests;
- each acceptance criterion is shown by a test or a recorded request;
- the docs are updated;
- its issue is in Done.

**Product Owner decisions** (scope, priority, cuts) are written as a comment on the issue, with a one-line reason.

## Deploy and roll back (Ubuntu Server VM)

> Completed by the release story. Deploy = check out the release tag, then run `docker compose up -d --build`. Roll back = check out the previous tag and run the same command.

## Known limitations

> Kept up to date during the sprint.
