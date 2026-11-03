# Day 2: Mid-day sync (2026-11-03, 13:00, 10 minutes)

**Facilitator:** @6qzr · **Attendees:** _fill in_

> Fill this in during the sync. The brief asks for three things: what is merged, CI status on `main`, and explicit scope cuts needed to make the 15:00 freeze. Every cut is also logged on #6 with a reason.

## Merged since standup
- _#PR: title (owner)_

## CI on `main`
- _green / red, plus the failing job if red_

## Milestone 1 status
| Step of the M1 demo | Issue | Status |
|---|---|---|
| `docker compose up` → both healthy, DB seeded | #18, #55 | |
| `GET /health` checks the DB | #65 | |
| `GET /api/v1/slots` returns seed slots | #14 | |
| Conversation answers; emergency skips the LLM | #10, #11, #12 | |
| History survives `docker compose restart api` (R1) | #10 | |

## Scope cuts (decided by the PO)
| Cut | Reason |
|---|---|
| _e.g. move #14 to @NoorAlbusaidi_ | _not started at 13:00_ |

## Until the freeze (15:00)
- _who merges what_
