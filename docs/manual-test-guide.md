# Manual test guide: every Must, step by step

A script to follow by hand in **Swagger** (`http://localhost:8000/docs`, or `http://<vm-ip>:8000/docs`).
Each scenario lists the request to send, what you should see, and what it proves. It takes about
15 minutes from start to finish.

## Before you start
1. Start the stack from the current code: `docker compose up -d --build --wait`.
2. Open `http://localhost:8000/docs`.
3. Know which LLM is running (`LLM_PROVIDER` in `.env`):
   - **`fake`**: replies come from keyword rules. Use the messages below **word for word**, and put
     the slot number, name and phone in **one** message, because only the latest message is read.
   - **`openai`**: natural wording works, and details can be spread over several messages. The
     *results* are the same, but the reply text differs.
4. How to send a message in Swagger: **POST `/api/v1/conversations/{conversation_id}/messages`**
   → *Try it out* → paste the id → body `{"message": "..."}` → *Execute*.

Write down each `conversation_id`, booking number and `approval_id` as you go. Later steps use them.

| Write down | From step |
|---|---|
| Conversation **A** (Ali) | 4.1 |
| Booking number **B1** and slot id **S1** | 4.2 |
| Conversations **C** and **D** (two patients) | 5.1 |
| Conversation **E** (same day) and approval **AP1** | 6.1 |
| Approvals **AP2** and **AP3** (cancel) | 7.2, 7.5 |

---

## 1. FR-7: health and API docs
| Step | Send | Expect | Proves |
|---|---|---|---|
| 1.1 | **GET `/health`** | `200` `{"status": "ok", "database": "ok"}` | The service and PostgreSQL are both up |
| 1.2 | Look at the Swagger page itself | Sections: Conversations, Slots, Approvals, Emergencies, ops (`/health`) | The OpenAPI docs are generated from the code |

## 2. FR-3: answers only from clinic documents
Start a conversation: **POST `/api/v1/conversations`** → `201` with a `conversation_id`.

| Step | Message | Expect | Proves |
|---|---|---|---|
| 2.1 | `What are your opening hours?` | `status: answered`, `sources: ["opening_hours.md"]`, the reply ends with `Source: opening_hours.md` | The answer comes from a clinic document and names it |
| 2.2 | `Is there a parking garage?` | `reply: "I don't know"`, `sources: []` | When no document matches, it says so honestly and invents no source |

With `fake`, the 2.1 reply text is a placeholder ("Demo mode…"). With `openai`, it is a real answer from the document. The source is the same in both.

## 3. FR-2 and FR-6: understanding, clarifying, never diagnosing, emergencies
In the same or a new conversation:

| Step | Message | Expect | Proves |
|---|---|---|---|
| 3.1 | `I want an appointment` | `status: clarifying`, asks for the slot number, name and phone | Missing details give a question, not a guess. The check is code (`missing_details`), not the LLM |
| 3.2 | `Can you tell me which illness I have from my symptoms` | `status: answered`, a polite reply about what the assistant can help with | It never diagnoses |

Emergency, in a **new** conversation:

| Step | Send | Expect | Proves |
|---|---|---|---|
| 3.3 | Message `I have chest pain and I can't breathe` | `status: emergency`, "call 9999 now… staff have been alerted" | The rule-based safety gate runs **before** the LLM and skips every other workflow |
| 3.4 | **GET `/api/v1/emergencies`** | A row with this `conversation_id` and the message | Staff get a flag they can see |

## 4. FR-4: find a slot and book it
New conversation **A**.

| Step | Send | Expect | Proves |
|---|---|---|---|
| 4.1 | Message `Any free dentistry slots tomorrow?` | A **numbered** list of up to 5 slots, each with doctor, specialty and time | Only free slots are offered |
| 4.1b | **GET `/api/v1/slots`** with `specialty=Dentistry`, `date=` tomorrow (`YYYY-MM-DD`) | The same slots in the same order. Write down the first `id` as **S1**. The API gives times in UTC (`05:00Z`), and the chat shows Muscat time (09:00 AM, UTC+4) | The chat and the API read the same data |
| 4.2 | Message `Book number 1, my name is Ali Said, phone 91234567` | "Your appointment is confirmed. Your booking number is **B1**." | Not same day, so it is booked at once |
| 4.3 | **GET `/api/v1/slots`** again (same filters) | **S1** is gone from the list | The booking holds the slot |

## 5. FR-4: no double booking
Start **two** conversations, **C** and **D**.

| Step | Send | Expect | Proves |
|---|---|---|---|
| 5.1 | In **C**: `Any free general practice slots tomorrow?` | A numbered list | — |
| 5.2 | In **D**: the same message | The **same** slot 1 | Both patients see the same free slot |
| 5.3 | In **C**: `Book number 1, my name is Sara Ali, phone 92345678` | Confirmed, with a booking number | — |
| 5.4 | In **D**: `Book number 1, my name is Omar Said, phone 93456789` | "Sorry, this appointment is no longer available…" | The database's partial unique index refuses the second booking. This holds even for truly simultaneous requests (`tests/integration/test_booking_concurrency.py`) |

## 6. FR-5: a same-day booking needs a real staff approval
New conversation **E**. Same-day slots exist only until 15:30 Muscat time. Later than that, skip to section 7, which shows the same approval flow.

| Step | Send | Expect | Proves |
|---|---|---|---|
| 6.1 | In **E**: `Any free dentistry slots today?` | Today's free slots | — |
| 6.2 | In **E**: `Book number 1, my name is Mona Hamed, phone 94567890` | `status: awaiting_approval`, `reply: null`, `approval_id: AP1` | The graph stopped at a real `interrupt()`; this is not a status flag |
| 6.3 | In **E**: `Hello?` | `409` "Conversation is waiting for a staff decision" | The conversation is locked while staff decide |
| 6.4 | **GET `/api/v1/approvals`** | A row for **AP1**: `action: book`, `status: pending` | Staff see the queue |
| 6.5 | **POST `/api/v1/approvals/AP1/decision`** with `{"approved": true, "reason": "Doctor can fit it in", "staff": "Front desk"}` | `200` `{"outcome": "Your request was approved."}` | The decision resumed the paused graph |
| 6.6 | Send 6.5 again | `409` "Approval already decided" | A decision can't be applied twice |
| 6.7 | **GET `/api/v1/conversations/E`** | The last message is "Your request was approved." | The patient sees the outcome |

## 7. FR-5: cancellation always needs staff, and survives a restart
| Step | Send | Expect | Proves |
|---|---|---|---|
| 7.1 | In **C** (not Ali's conversation): `Please cancel booking B1` | "I couldn't find a booking with that number in this conversation." | Patients can only cancel their own bookings |
| 7.2 | In **A**: `Please cancel booking B1` | `status: awaiting_approval`, `approval_id: AP2` | Every cancel waits for staff |
| 7.3 | **In a terminal:** `docker compose restart api`, then **GET `/health`** until it is `ok` | — | Simulates a crash or redeploy while the request waits |
| 7.3b | **GET `/api/v1/approvals`** | **AP2** is still pending | The pause was saved in PostgreSQL (checkpointer + approvals table) |
| 7.4 | **POST `/api/v1/approvals/AP2/decision`** with `{"approved": false, "reason": "Please call us within 24 hours", "staff": "Front desk"}` | `{"outcome": "Your request was rejected: Please call us within 24 hours"}` | The graph resumed after the restart; on rejection the booking stays |
| 7.5 | In **A**: `Please cancel booking B1` again → approve the new `approval_id` (**AP3**) with `"approved": true` | "Your request was approved." | — |
| 7.6 | **GET `/api/v1/slots`** (Dentistry, tomorrow) | **S1** is back in the list | The cancel freed the slot |

## 8. FR-1: conversations are saved and resumable
| Step | Send | Expect | Proves |
|---|---|---|---|
| 8.1 | **GET `/api/v1/conversations/A`** | The whole exchange from sections 4 and 7, in order, even across the restart | The history lives in the PostgreSQL checkpointer under `thread_id = conversation_id` |

---

## If something looks wrong
| You see | Why | Fix |
|---|---|---|
| "no free appointments" for tomorrow | The seed creates 5 days of slots from the database's **first** start | `docker compose down -v` then `up -d --build --wait` (⚠️ this deletes all data) |
| `clarifying` when you expected a booking | With `fake`, the number, name and phone must be in one message, as in 4.2 | Resend in exactly that form |
| A booking reply when you meant a question | With `fake`, words like "free", "slot" or "book" choose the intent | Use the messages in this guide word for word |
| `503` on every call | The API is still starting, or the database is down | **GET `/health`**, wait for `ok` |
| The same data from a previous run | Runs add to the database; they never reset it | Fine for a demo. Use new conversations, or reset with `down -v` |
