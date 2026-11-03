<!-- PR title: "#<issue-number>: <issue title>" -->

## Ticket
Closes #

## What changed
-
-

## How to test
```bash
uv run pytest
```
<!-- Add the requests a reviewer can run, e.g. curl / OpenAPI steps. -->

## Checklist
- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run mypy` passes
- [ ] `uv run pytest` passes (coverage ≥ 80%); tests use the fake LLM
- [ ] New behaviour has tests; acceptance criteria of the issue are met
- [ ] README / API docs / ADRs updated where behaviour changed
- [ ] Under ~400 changed lines; one task or story
- [ ] Issue moved to **Ready for Review** on the board
