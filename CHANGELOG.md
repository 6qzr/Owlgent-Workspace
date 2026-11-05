# Changelog

All notable changes to the Clinic Front-Desk Assistant are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-05

First release. An agentic front desk for a clinic, reachable over a REST API.

### Added

**Conversations**
- Start a conversation and send messages over the API; the assistant classifies what the
  patient wants and asks a clarifying question when the request is incomplete.
- Requests outside the clinic's scope get a short, polite reply; the assistant never
  diagnoses.
- Conversation state is stored in PostgreSQL after every step, so a conversation can be
  resumed by its ID and survives an API restart or a redeploy.
- Read the full history of a conversation.

**Safety**
- Messages describing an emergency are detected by rules before the language model is
  called, and answered with an emergency instruction. Each one is recorded for staff.
- Staff can list flagged emergencies, newest first, at `GET /api/v1/emergencies`.

**Appointments**
- List free slots, filtered by specialty, doctor and date.
- Book a slot. A database constraint prevents the same slot being booked twice; a
  cancelled or rejected booking frees the slot again.
- Cancel a confirmed booking you made in the same conversation.

**Staff approval**
- Same-day bookings (judged in Oman time, UTC+4) and all cancellations pause and wait for a
  staff decision. The conversation resumes from the point it paused once staff approve or
  reject, including after an API restart.
- Staff endpoints to list pending approvals and record a decision. A decision needs a
  reason and the staff member's name, a rejection tells the patient the reason, and each
  approval can be decided only once.
- While a conversation waits for staff, new messages to it are refused with HTTP 409.

**Clinic documents**
- Questions about opening hours, doctors and specialties, insurance, visit and blood-test
  preparation, and the cancellation policy are answered from the clinic's own documents,
  with the source document named in the reply.
- When the documents don't cover a question, the assistant says "I don't know" instead of
  guessing.

**Running the system**
- `docker compose up -d --build` starts the API and PostgreSQL, with the schema and seed
  data applied automatically on first start.
- `/health` reports the API and database state, and is used as the container health check.
- `scripts/smoke.sh` checks a running deployment end to end: health, conversation, booking,
  cancellation, staff approval and history.
- `LLM_PROVIDER=fake` runs the system without an OpenAI key, for CI and demos. Routing,
  booking, cancellation, approval and emergencies all work; answers to document questions
  are a fixed placeholder, though the source document is still named.

### Known limitations
- There is no authentication: the staff endpoints for approvals and emergencies are open to
  anyone who can reach the API.
- Only the last 10 messages of a conversation are sent to the model for classification.
- `docker compose down -v` deletes the database volume and every conversation with it.
- The seed creates five days of slots from the day the volume was created.
