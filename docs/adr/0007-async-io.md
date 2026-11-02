# ADR 0007: All I/O is async

- **Status:** accepted
- **Date:** 2026-11-02
- **Deciders:** @6qzr (Product Owner), team
- **Related:** #6

## Context
FastAPI supports both sync and async endpoints. The course stressed never blocking the event loop, and mixing the two styles has caused bugs for us before.

## Options considered
1. **All sync**: `def` endpoints, which FastAPI runs in a thread pool. This is simpler.
2. **All async**: `async def` everywhere, with async drivers.
3. **Mixed**: blocking calls inside `async def`. Rejected, because it freezes the server.

## Decision
We use option 2:
- `async def` endpoints.
- `graph.ainvoke`, with async nodes for any I/O.
- `AsyncPostgresSaver` and the psycopg `AsyncConnectionPool`.
- `AsyncOpenAI`, with timeouts.
- `pytest-asyncio` and `httpx.AsyncClient` in tests.

## Consequences
- The whole codebase follows one style. Blocking calls (`time.sleep`, `requests`, the sync psycopg or OpenAI clients) are not allowed inside `async def`.
- The FakeLLM exposes the same async methods as the real adapter.
