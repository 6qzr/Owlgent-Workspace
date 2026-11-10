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
cp .env.example .env        # then set OPENAI_API_KEY, or LLM_PROVIDER=fake to run without a key
docker compose up -d --build
docker compose ps           # every service should be "healthy"
```

Nothing else is needed: no local Python, no manual SQL. PostgreSQL creates its schema and seed data from `db/` on first start.

## Develop

```bash
uv sync                      # creates .venv from uv.lock (never use pip)
uv run pre-commit install    # ruff + mypy before every commit
cp .env.example .env         # LLM_PROVIDER=fake runs the app locally without an OpenAI key
docker compose -f compose.yaml -f compose.dev.yaml up -d db   # local PostgreSQL on 127.0.0.1:5432
```

Tests give the same result whatever is in your shell or `.env`. They always use the fake LLM, and only read the database values from `.env`. If PostgreSQL isn't running, the integration tests stop at once and print the command above. To run without a database, use `uv run pytest -m "not integration"`.

On WSL, run everything from your own clone inside WSL, with its own `.venv` and `.env`. A `.venv` created on Windows doesn't work on Linux.

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

The VM builds and runs the **tagged source** with Docker Compose. There is no image registry (ADR 0009). Any team member can follow these steps.

### 1. Prepare the VM (once)

**VirtualBox:** Ubuntu Server LTS, 2 vCPU, 4 GB RAM, 20 GB disk. Networking: NAT with port forwarding **host 8000 → guest 8000** (API) and **host 2222 → guest 22** (SSH), or a bridged adapter.

**Docker Engine and tools** (from [Docker's Ubuntu guide](https://docs.docker.com/engine/install/ubuntu/)):

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git jq
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

`jq` is needed by `scripts/smoke.sh`.

**A deploy user that is not root:**

```bash
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy      # run docker without sudo; log in again to apply
sudo install -d -o deploy -g deploy /opt/clinic-assistant
```

**The code and its secrets**, as `deploy`:

```bash
sudo -iu deploy
git clone https://github.com/6qzr/Owlgent-Workspace.git /opt/clinic-assistant
cd /opt/clinic-assistant
cp .env.example .env
chmod 600 .env                      # only deploy can read the secrets
nano .env                           # set OPENAI_API_KEY and a strong POSTGRES_PASSWORD
```

Set `POSTGRES_PASSWORD` **before the first start**. PostgreSQL stores it in the volume on the first start, and changing `.env` later does not change it.

### 2. Deploy a release

```bash
cd /opt/clinic-assistant
git fetch --tags
git checkout v0.1.0                 # the release tag, never a branch
docker compose up -d --build --wait # rebuilds the image from this tag; waits until healthy
docker compose ps                   # api and db: "healthy"
bash scripts/smoke.sh               # exit 0: "All … smoke steps passed."
```

From the host machine, the API answers at `http://localhost:8000/health` (NAT forwarding) or at `http://<vm-ip>:8000/health` (bridged).

`git describe --tags` shows which release is running.

To walk through every Must scenario by hand in Swagger (for a demo or after a deploy), follow [`docs/manual-test-guide.md`](docs/manual-test-guide.md).

### 3. Roll back

Check out the **previous** tag and run the same commands:

```bash
git tag --sort=-creatordate         # newest first: pick the one before the running tag
git checkout <previous-tag>
docker compose up -d --build --wait
bash scripts/smoke.sh
```

Roll forward again the same way with the newer tag. To rehearse a rollback, there must already be an earlier tag on `main` to go back to.

- The `pgdata` volume is **kept** across deploys and rollbacks, so conversations, bookings and approvals survive.
- `db/*.sql` runs **only on the first start** (empty volume). A release that changes the schema needs a migration plan before it can be rolled back. `v0.1.0` has none.
- **Never run `docker compose down -v` on the VM.** `-v` deletes the database volume and every conversation with it.

## Known limitations

> Kept up to date during the sprint.
