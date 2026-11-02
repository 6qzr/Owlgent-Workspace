# ADR 0008: LLM adapter injected, FakeLLM in tests and CI

- **Status:** accepted
- **Date:** 2026-11-02
- **Deciders:** team
- **Related:** #11

## Context
Every workflow must run with a deterministic fake LLM, so CI needs no API key.

## Options considered
1. Call the OpenAI SDK directly inside nodes, and mock it in tests.
2. **One async `LLM` interface injected into the graph**, with two implementations: `AsyncOpenAI` and a deterministic `FakeLLM`.

## Decision
- Nodes depend only on the `LLM` interface.
- `build_graph(llm=..., checkpointer=...)` receives both dependencies.
- Tests and CI always pass the `FakeLLM`.

## Consequences
- Tests are fast, free and deterministic, and CI needs no secrets.
- Changing the model or provider never touches the nodes.
