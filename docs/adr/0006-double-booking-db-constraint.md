# ADR 0006: Double booking prevented by a database constraint

- **Status:** accepted
- **Date:** 2026-11-02
- **Deciders:** @NoorAlbusaidi, team
- **Related:** #15, #55

## Context
Double booking must be impossible, even when two requests arrive at the same moment (FR-4). A same-day booking holds its slot while it waits for approval (assumption recorded in #6).

## Options considered
1. **Check in Python, then insert**: there is a race between the check and the insert.
2. **`SELECT ... FOR UPDATE` locking**: works, but every booking path must remember to lock.
3. **A partial unique index**: the database itself rejects the second insert.

## Decision
- Create a partial unique index: `CREATE UNIQUE INDEX ... ON bookings (slot_id) WHERE status IN ('pending_approval', 'confirmed')`.
- A unique violation becomes a `SlotTaken` error, and the patient is offered other slots.

## Consequences
- Correct under any concurrency, with no locking code to forget.
- Cancelled or rejected bookings free their slot automatically.
- An integration test runs two concurrent bookings to prove it.
