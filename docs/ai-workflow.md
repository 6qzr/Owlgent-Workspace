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

## How we used AI so far

Each member records how they actually worked: tools, a real example, and what they checked themselves. Keep it short and honest; the trainer reads this.

### @6qzr (lead: planning, CI, graph, routing, safety)

- **Tool:** Claude Code (desktop app and VS Code extension), in the *Learning* output style.
- **Planning:** the tool drafted the Day 1 plan, the kick-off assumptions, the stories and the architecture pack with ADRs. I took each draft to the team, we changed it together, and I recorded the decisions in #6. When the first issues were too heavy (user stories plus tasks), I asked for one owner per issue and simpler steps.
- **Code:** the tool set up the structure (skeleton, CI, graph skeleton, LLM adapter) and left the key design choices as `TODO(human)` for me to write, for example the `Entities` fields in `agent/state.py`. Every PR is one logical step with its own commits.
- **Reviews:** for every teammate PR I first asked for a plain-words explanation of what it does, then decided the verdict myself (approve or request changes, e.g. #68, #75, #76). For merge conflicts on teammates' branches, the tool proposed the resolution and I posted a comment explaining it.
- **Verification:** I always asked the tool to re-check the live state (open PRs, CI) before a status update, and ran the stack with `docker compose` from a fresh clone before calling M1 done.
- **Understanding:** Phase 1 study guide (PDF, then an interactive page) with the data flow, the boundaries and the trade-offs, plus "interrogation questions" I answered before reading the model answers. Example question: *"How does 'I have chest pain' become an emergency?"*. Answer: a rule in `safety_gate`, before any LLM call (`test_emergency_never_reaches_the_llm`).
- **Still learning:** checkpoint internals (`checkpoint_writes`), and RAG ranking once #13 lands.

### @MohammedAlkahali (R1: checkpointer, conversations, Docker, release)

- **Tool:**
- **Planning:**
- **Code:**
- **Reviews:**
- **Verification:**
- **Understanding (one real question you asked, and the answer):**
- **Still learning:**

### @baraah34 (R2: approvals, slots, cancel)

- **Tool:**
- **Planning:**
- **Code:**
- **Reviews:**
- **Verification:**
- **Understanding (one real question you asked, and the answer):**
- **Still learning:**

### @NoorAlbusaidi (R3: database foundation, health, RAG, booking)

- **Tool:**
- **Planning:**
- **Code:**
- **Reviews:**
- **Verification:**
- **Understanding (one real question you asked, and the answer):**
- **Still learning:**
