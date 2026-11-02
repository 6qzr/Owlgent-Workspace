# ADR 0005: Safety and routing decisions in plain code, not the LLM

- **Status:** accepted
- **Date:** 2026-11-02
- **Deciders:** @6qzr, team
- **Related:** #11, #12

## Context
The assistant must never diagnose. Emergencies must be short-circuited without passing through any other workflow (FR-6), and intents must be routed predictably (FR-2). The evaluation marks "the LLM decides safety" as weak design.

## Options considered
1. The LLM chooses the next step.
2. The LLM only classifies, and plain functions decide the path.

## Decision
- `safety_gate` is rule-based, using an emergency phrase list in config, and runs before any LLM call.
- `classify` returns the intent, confidence and entities.
- `route_intent`, the confidence threshold and `is_same_day` are plain functions.

## Consequences
- Every branch can be unit-tested with the FakeLLM, and emergency handling never depends on model output.
- If the LLM detects an `emergency` intent, that also routes to `emergency_reply`, as a second line of defence.
- The phrase list needs care to avoid missed emergencies. It is reviewed against sample messages.
