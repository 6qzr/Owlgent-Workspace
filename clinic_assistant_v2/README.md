# Clinic Assistant v2

The clinic front-desk assistant, refactored for #314. A patient signs in with Google, gets a JWT,
and chats with an assistant that books appointments, checks the pharmacy, reads the patient's own
medical records and answers questions from the clinic's documents.

The assistant never asks who you are. Every tool call carries your JWT, and each MCP server reads
the user only from the token, so you can only ever see your own data.

```text
browser ──Google sign-in──▶ api :8000 ──Bearer JWT──▶ appointments :8001
                            (FastAPI +               pharmacy     :8002
                             LangGraph agent)        records      :8003
                                                     knowledge    :8004 ──▶ qdrant :6333
                                                                  ingest (one-shot) ──▶ qdrant
```

- [docs/architecture.md](docs/architecture.md): diagrams, the JWT flow, who trusts whom, and where
  each secret lives.
- [docs/contract.md](docs/contract.md): ports, env vars, tools, scopes and test users.

## What you need

- Docker Desktop (or Docker Engine with Compose v2)
- [uv](https://docs.astral.sh/uv/), only to run the tests
- A Google account, to create the OAuth client
- An OpenAI API key

All commands below run from this folder, `clinic_assistant_v2/`.

## 1. Create the Google OAuth client

1. Open the [Google Cloud console](https://console.cloud.google.com/) and pick or create a project.
2. Go to **APIs & Services → OAuth consent screen**. Choose **External**, fill in the app name
   and your email, and add your own Google account under **Test users**.
3. Go to **APIs & Services → Credentials → Create credentials → OAuth client ID**.
4. Set **Application type** to **Web application**.
5. Under **Authorized redirect URIs**, add exactly:

   ```text
   http://localhost:8000/auth/callback
   ```

6. Click **Create** and keep the **Client ID** and **Client secret** for the next step.

## 2. Fill in `.env`

Copy the example file:

```powershell
Copy-Item .env.example .env
```

(On macOS or Linux: `cp .env.example .env`.)

Then open `.env` and set:

| Variable | Value |
|---|---|
| `GOOGLE_CLIENT_ID` | the Client ID from step 1 |
| `GOOGLE_CLIENT_SECRET` | the Client secret from step 1 |
| `OPENAI_API_KEY` | your OpenAI key |
| `JWT_SECRET` | a long random string (see below) |

Generate `JWT_SECRET` with:

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

It must be at least 32 bytes and must not be the placeholder `change-me`; otherwise every service
refuses to start. Leave the other values as they are: they already point at the Docker service
names.

`.env` is gitignored. Never commit it, and never paste its values into an issue or chat.

## 3. Start everything

```powershell
docker compose up --build
```

Compose starts the services in this order, each waiting for the previous one to be healthy:

1. `qdrant`
2. `ingest`, which loads the PDFs (see step 4), then exits
3. `appointments`, `pharmacy`, `records` and `knowledge`
4. `api`, published on `http://localhost:8000`

In a second terminal, check that everything is up:

```powershell
docker compose ps -a
```

Every service should show `healthy`, except `ingest`, which shows `Exited (0)` because it runs once
and stops.

## 4. Ingestion

`docker compose up` already runs ingestion once. In its log you should see one line per PDF:

```text
ingest-1  | doctors.pdf: 3 chunks stored
ingest-1  | facilities.pdf: 3 chunks stored
ingest-1  | policies.pdf: 3 chunks stored
```

To run it again (for example after changing a PDF in `ingestion/pdfs/`):

```powershell
docker compose run --rm ingest
```

Re-running is safe: point ids come from the file name and chunk number, so the same chunks are
overwritten, not duplicated. The Qdrant data is kept in the `qdrant_storage` volume, and its
dashboard is at <http://localhost:6333/dashboard>.

## 5. Sign in and copy your token

1. Open <http://localhost:8000/auth/login> in your browser.
2. Sign in with the Google account you added as a test user.
3. The browser shows JSON like this:

   ```json
   {"access_token": "eyJhbGciOi...", "token_type": "bearer"}
   ```

4. Copy the `access_token` value. It is valid for one hour (`TOKEN_TTL_SECONDS`).

**About the sample data.** The servers start with sample appointments and records for two test
users, `user-a` and `user-b`. Your real Google account has its own id, so at first it has no
records: "Show me my last medical record" correctly answers that there are none. To try the
sample data locally, make a token for a test user inside the running API container:

```powershell
docker compose exec api python -c "from api.config import USER_SCOPES; from api.tokens import create_token; print(create_token('user-a', 'user-a@example.com', USER_SCOPES))"
```

This only works for someone who can already run commands in your containers, and it uses the
same `JWT_SECRET` as everything else. It is for local demos, not a sign-in method.

## 6. Chat

PowerShell:

```powershell
$token = "<paste your access_token here>"
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body '{"message": "Show me the last medical record"}'
```

curl (macOS, Linux, or `curl.exe` on Windows):

```bash
TOKEN="<paste your access_token here>"
curl -s -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me the last medical record"}'
```

The answer is `{"reply": "..."}`. With a `user-a` token from step 5, the reply mentions the Flu
record from 2026-10-02. Other messages to try:

- `Which doctor sees skin problems?` (answered from `doctors.pdf`)
- `Book me with Dr. Lina on 2026-12-15 at 11:00`
- `What medicines are in stock?`

| Status | Meaning |
|---|---|
| 200 | `{"reply": "..."}` |
| 401 | the token is missing, malformed, expired, or not sent as `Bearer <token>` |
| 422 | the message is empty or longer than 2000 characters |
| 503 | OpenAI could not be reached; try again |

To stop everything: `docker compose down`. Appointments and pharmacy stock are kept in memory, so
they reset when the servers restart.

## 7. Run the tests

The tests need no Docker, no `.env` and no network: Google and OpenAI are faked, and the MCP
servers run in-process.

```powershell
uv sync
uv run pytest -v
```

The pieces on their own:

```powershell
uv run pytest tests/e2e -v
uv run pytest tests/api -v
uv run pytest tests/servers -v
```

- `tests/e2e`: the real MCP servers over HTTP. Covers cross-user isolation, no ID question,
  token rejection by every tool, and booking, pharmacy and document search.
- `tests/api`: Google sign-in and `/chat`.
- `tests/servers`: each MCP server on its own.

The same checks CI runs:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Troubleshooting

**Every service must use the same `JWT_SECRET`.** The API signs tokens with it, and each MCP server
verifies them with it. Compose passes the one value from `.env` to all of them. If you change it,
restart everything (`docker compose up -d --force-recreate`) and sign in again: tokens signed
with the old secret are now rejected, and each tool returns `{"error": "unauthorized"}`.

**The header is `Bearer`, one space, then the token.** Exactly `Authorization: Bearer eyJ...`.
`bearer` (lowercase), a missing space, quotes around the token, or the whole JSON instead of just
the `access_token` value all give 401.

**Inside Docker, use service names, not `localhost`.** Containers reach each other as
`http://records:8003/mcp`, `http://qdrant:6333` and so on; `.env.example` already has those. Inside
a container, `localhost` means that same container. Only your browser and curl, which run on your
machine, use `localhost:8000`.

**More problems:**

| Symptom | Fix |
|---|---|
| `docker compose up` stops with `set JWT_SECRET in .env` (or another name) | That variable is missing from `.env`. Fill it in (step 2). |
| A service exits with `JWT_SECRET must be at least 32 bytes` or `placeholder` | Generate a real secret (step 2). |
| Google shows `redirect_uri_mismatch` | The redirect URI in the Google console must be exactly `http://localhost:8000/auth/callback`. |
| Google shows `access_denied` or "app not verified" | Add your account under **Test users** on the consent screen (step 1). |
| `/auth/callback` says `Invalid OAuth state` | Start again at `/auth/login` in the same browser, and finish within 10 minutes. |
| `/chat` gave 200 before and now gives 401 | The token expired after an hour. Sign in again. |
| `knowledge` and `api` never start | `ingest` failed. Run `docker compose logs ingest`; it's usually the OpenAI key. |
| The assistant says a service is unavailable | Run `docker compose ps` and `docker compose logs <service>` for the one that is down. |
| "No records" for your Google account | Expected: the sample records belong to `user-a` and `user-b` (step 5). |
| Port 8000 or 6333 is already in use | Stop whatever uses it, or change the left side of `ports:` in `docker-compose.yml`. |
