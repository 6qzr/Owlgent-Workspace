# Working with agentic AI tools

How the team uses Claude Code, OpenCode or similar tools to finish the remaining work **and understand it**. The rule: you may let the tool write code, but you must be able to explain, test and change every line you merge.

## The loop for every PR

1. **Plan before code.** Give the tool the issue and the files it may touch. Ask for a plan first, not code. Check the plan against `AGENTS.md`, the architecture doc and the state fields in `agent/state.py`. Change it until you agree with it.
2. **Generate one small step.** One function or one test at a time. Keep the PR under ~400 lines.
3. **Explain it back.** For each function, ask the tool *why*, not *what*: why this order, why this SQL, what happens on failure. Then say it in your own words. If you can't, don't merge it.
4. **Predict, then test.** Before running `uv run pytest`, write down which tests you expect to pass or fail. Then break one line on purpose and check that a test catches it.
5. **Fill in the PR.** Complete the *AI use and understanding* section of the PR template.

## Prompts that help you understand

- "Trace what happens to the state when a patient sends `<message>`, node by node, using the real code."
- "Which state field does this node write? Which node reads it next?"
- "What does the database contain before and after this function? Show the rows."
- "Give me 3 questions a reviewer would ask about this diff, then check my answers."
- "If I delete line N, which test fails, and why?"

## What the tool must not decide

These stay human decisions, recorded in #6 when they change behaviour:

- the safety rules, routing order and the confidence threshold;
- anything about approvals (what needs staff, what happens on reject);
- schema changes and what counts as a free slot;
- skipping a test, a type check or a review.

## Understanding phases

| Phase | What | Done when |
|---|---|---|
| 1. Own slice | Every file you own: what it does, the state fields it reads and writes, the test that proves it | You can explain it without the tool open |
| 2. Others' slices | Learn through review: how each teammate's node plugs into the graph | You've reviewed at least 2 teammates' PRs with real questions |
| 3. Mock evaluation | Teammates quiz you, including "change X now" | You make the change and predict which tests change |
