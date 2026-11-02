# ADR 0004: GitHub Issues, one owner per issue

- **Status:** accepted
- **Date:** 2026-11-02
- **Deciders:** @6qzr (Product Owner)
- **Related:** #6

## Context
The brief mentions ClickUp, but our team repository's contribution guidelines already use GitHub issue IDs. The brief requires stories with acceptance criteria and points, and tasks of 1–3 hours with owners.

## Options considered
1. **ClickUp**, as in the brief: a second tool to keep in sync with GitHub.
2. **GitHub Issues with one issue per task**: too much overhead (45+ issues), and it confused the team.
3. **GitHub Issues with one issue per piece of work and one owner per issue**: 1–3 hour steps are a checklist inside the issue.

## Decision
We chose option 3:
- Stories (#10–#19), foundation and ops work (#55, #56) and the spikes are issues.
- Each issue has exactly one owner and lists only that owner's steps.
- The board is the GitHub Projects view linked to the repository.
- Branches are named `feature/<issue#>-<user>-<title>`.
- PRs are titled `#<issue#>: <step>` with `Part of #<issue#>` in the body. The last PR of an issue uses `Closes #<issue#>`.

## Consequences
- One tool covers code, reviews and planning, and "who owns what" is always the assignee.
- The requirement for tasks with owners is met by the checklist steps.
- Product Owner decisions are recorded as comments on #6.
