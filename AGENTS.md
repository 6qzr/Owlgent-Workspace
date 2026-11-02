# AGENTS.md: conventions for humans and coding agents

## Hard rules
- **PostgreSQL only.** Use psycopg with parameterised SQL. No SQLAlchemy or any other ORM. No SQLite or in-memory DB, not even in tests.
- **No real LLM in tests or CI.** Every workflow takes the LLM adapter as a dependency, and tests pass the fake.
- **Safety decisions are code.** Emergency short-circuit, intent routing and "needs staff approval" are plain functions over state, never an LLM answer.
- **Human approval is a real LangGraph `interrupt()`**, resumed via the API and persisted by the PostgreSQL checkpointer. It is never a status flag.
- **Config comes from environment variables.** The app fails fast with a clear message if a required one is missing. Never commit `.env` or secrets.
- **Use uv.** Never install with pip. Commit `uv.lock`.

## Code style
- One module per concern.
- Small functions with type hints and a one-line docstring.
- mypy strict: any `# type: ignore` needs a comment explaining why.
- Routes contain no business logic; they call a service.
- Graph nodes read state and return **only the keys they change**. Each state field has exactly one writer.
- Model names, thresholds and prompts live in configuration, not at call sites.
- Bound what is sent to the model (recent-message window, trimmed inputs).
- Every external call (LLM, DB, HTTP) has a timeout. A failure becomes a clear HTTP error plus a log line, never a stack trace.

## Tests
- `tests/unit`: nodes, routing branches, retriever.
- `tests/api`: status codes and validation through `TestClient`.
- `tests/integration`: real PostgreSQL; mark them `@pytest.mark.integration`.

## Git
Follow the contribution guidelines in `README.md`. Commits and PRs carry only the human author's identity.
