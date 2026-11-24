# Shared contract (#314)

Everyone builds against this page, so nobody waits for anyone else. If something here looks wrong,
say so on the contract issue; don't change it silently in your own PR.

## Project layout

`clinic_assistant_v2/` is one uv project (Python 3.14). Each folder is a Python package, imported
from the project root:

| Folder | Package | Owner | Run with |
|---|---|---|---|
| `auth_reference/` | `auth_reference` | lead | – (copied, not run) |
| `api/` | `api` | lead | `uvicorn api.main:create_app --factory --host 0.0.0.0 --port 8000` |
| `servers/appointments/` | `servers.appointments` | Item 1 | `python -m servers.appointments.server` |
| `servers/pharmacy/` | `servers.pharmacy` | Item 2 | `python -m servers.pharmacy.server` |
| `servers/records/` | `servers.records` | Item 3 | `python -m servers.records.server` |
| `servers/knowledge/` | `servers.knowledge` | Item 5 | `python -m servers.knowledge.server` |
| `ingestion/` | `ingestion` | Item 4 | `python -m ingestion.ingest` |
| `tests/` | – | everyone | `uv run pytest` |

- Every package folder has an `__init__.py`, and so does `servers/` itself.
- Each server copies `auth_reference/tokens.py` into its own folder unchanged, and imports its own
  copy, for example `from servers.records.tokens import verify_token`.
- Docker: the **build context is `clinic_assistant_v2/`**, and each service names its own
  Dockerfile, for example `dockerfile: servers/records/Dockerfile`. A Dockerfile installs the locked
  dependencies with `uv sync --frozen --no-dev` and runs the module command above.
- Add the packages you need with `uv add <pkg>` from `clinic_assistant_v2/`, and commit `uv.lock`.

## Network and ports

All services are on one Docker network, `clinic_net`, and reach each other by service name, never
`localhost`.

| Service | Port | Inside Docker |
|---|---|---|
| `api` | 8000 (published) | `http://api:8000` |
| `appointments` | 8001 | `http://appointments:8001/mcp` |
| `pharmacy` | 8002 | `http://pharmacy:8002/mcp` |
| `records` | 8003 | `http://records:8003/mcp` |
| `knowledge` | 8004 | `http://knowledge:8004/mcp` |
| `qdrant` | 6333 | `http://qdrant:6333` |

MCP servers use the `http` transport on path `/mcp`, bound to `0.0.0.0`:
`mcp.run(transport="http", host="0.0.0.0", port=PORT)`.

**Health checks.** Every long-running service answers `GET /health` with 200, so compose can wait
on `service_healthy`:

- `api`: `GET http://api:8000/health` returns `{"status": "ok"}`.
- Each MCP server registers its own route:

  ```python
  from starlette.requests import Request
  from starlette.responses import PlainTextResponse


  @mcp.custom_route("/health", methods=["GET"])
  async def health(request: Request) -> PlainTextResponse:
      """Tell docker compose the server is up."""
      return PlainTextResponse("OK")
  ```

- Compose healthchecks use Python, since the images have no curl:
  `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"`.
  Here `localhost` is correct, because the check runs inside the container itself.

## Environment variables

All values come from `.env` (gitignored). `.env.example` lists every name with placeholders.

| Name | Used by |
|---|---|
| `JWT_SECRET` | api, all four MCP servers |
| `TOKEN_TTL_SECONDS` (3600) | api |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_URI` | api |
| `OPENAI_API_KEY`, `CHAT_MODEL` | api (the agent's LLM) |
| `OPENAI_API_KEY`, `EMBEDDING_MODEL` (`text-embedding-3-small`) | knowledge, ingestion |
| `QDRANT_URL`, `QDRANT_COLLECTION` (`clinic_docs`) | knowledge, ingestion |
| `APPOINTMENTS_MCP_URL`, `PHARMACY_MCP_URL`, `RECORDS_MCP_URL`, `KNOWLEDGE_MCP_URL` | api |

The API holds no tool secrets: no Qdrant settings and no server data.

## The JWT

- HS256, signed with `JWT_SECRET`. The secret must be at least 32 bytes and must not be the
  `.env.example` placeholder `change-me`, otherwise `get_jwt_secret()` refuses to start.
- Exactly four claims: `sub` (str, Google's stable user id), `email` (str), `scopes` (list of str),
  and `exp` (now + `TOKEN_TTL_SECONDS`, in Unix seconds).
- Scopes: `appointments:read`, `appointments:write`, `pharmacy:read`, `pharmacy:write`,
  `records:read`, `docs:read`. In v2 a signed-in user gets all six.
- It's sent on every MCP call as the header `Authorization: Bearer <jwt>`.

## verify_token

Copy `auth_reference/tokens.py` unchanged. It provides:

- `verify_token(token: str | None, required_scope: str) -> dict`. It returns the claims, or raises
  `Unauthorized` for a missing or empty token, a malformed token, a bad signature, an expired token,
  a missing claim, or a missing scope.
- `token_from_header(authorization: str | None) -> str | None`. It strips the `Bearer ` prefix.
- `create_token(sub, email, scopes) -> str`. The API uses it to issue tokens, and tests use it to
  make test tokens.
- `get_jwt_secret()`. Call it once at server start-up, so a missing, placeholder or too-short `JWT_SECRET` fails
  fast.

Every tool that touches user data starts like this:

```python
from fastmcp.server.dependencies import get_http_headers

from servers.records.tokens import Unauthorized, token_from_header, verify_token


@mcp.tool
def get_my_last_medical_record() -> dict[str, str]:
    """Return the signed-in user's most recent medical record."""
    headers = get_http_headers(include={"authorization"})
    try:
        claims = verify_token(token_from_header(headers.get("authorization")), "records:read")
    except Unauthorized:
        return {"error": "unauthorized"}
    user_id = claims["sub"]
    ...
```

`include={"authorization"}` matters: by default FastMCP's `get_http_headers()` strips credential
headers such as `authorization`, so without it every call looks unauthorized.

## Tools

Each tool returns a plain dict or list, and `{"error": "..."}` on failure; it never raises to the
client. Tools that return personal data take **no user id argument**: the user is always
`claims["sub"]`.

| Tool | Server | Scope | Returns |
|---|---|---|---|
| `book_appointment(doctor: str, date: str, time: str)` | appointments | `appointments:write` | the new appointment |
| `list_my_appointments()` | appointments | `appointments:read` | the caller's appointments |
| `cancel_appointment(appointment_id: int)` | appointments | `appointments:write` | the cancelled appointment; someone else's gives `{"error": "not found"}` |
| `view_inventory()` | pharmacy | `pharmacy:read` | the inventory list |
| `add_inventory(medicine: str, quantity: int)` | pharmacy | `pharmacy:write` | the changed row |
| `get_my_medical_records()` | records | `records:read` | the caller's records |
| `get_my_last_medical_record()` | records | `records:read` | the caller's newest record |
| `search_clinic_docs(query: str, top_k: int = 3)` | knowledge | `docs:read` | `[{"text", "source", "score"}]`, or `[]` |

Dates use `YYYY-MM-DD` and times use `HH:MM`.

## Test users

Seed every domain server with these two users, so the isolation tests can tell them apart.

| `sub` | `email` | Last medical record |
|---|---|---|
| `user-a` | `user-a@example.com` | `{"date": "2026-10-02", "diagnosis": "Flu", "notes": "Rest"}` |
| `user-b` | `user-b@example.com` | `{"date": "2026-10-20", "diagnosis": "Sprained ankle", "notes": "Ice and rest"}` |

## Qdrant

- Collection `clinic_docs`, 1536-dimension vectors (`text-embedding-3-small`), cosine distance.
- Point payload `{"text": <chunk>, "source": "<file>.pdf"}`.
- Point id `uuid5(NAMESPACE_URL, f"{source}#{index}")`, so re-running ingestion overwrites instead
  of duplicating.

## Code rules

- Type hints and a one-line docstring on every function and tool.
- Named constants or env vars for ports, models, the collection and the token lifetime.
- Plain syntax and no dead code.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` and `uv run pytest` all
  pass.
- Tests never call real OpenAI, Google or the network: use fakes and test tokens from
  `create_token`.
