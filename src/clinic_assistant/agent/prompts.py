"""Prompts and model-facing limits, kept out of node code (AGENTS.md: prompts live in config)."""

# Only the most recent messages are sent to the model; the checkpoint keeps the full history.
# Move to Settings.max_history_messages once the config from #55 is merged.
CLASSIFY_HISTORY_WINDOW = 10

# Below this confidence the assistant asks a clarifying question instead of guessing (FR-2).
ROUTING_CONFIDENCE_THRESHOLD = 0.6

CLASSIFY_SYSTEM_PROMPT = """\
You classify messages sent to a private clinic's front-desk assistant.
Return the patient's intent for their LATEST message, using the conversation for context:
- question: asks about clinic policies, opening hours, visit preparation or insurance
- find_slots: wants to see free appointment times
- book: wants to book an appointment
- cancel: wants to cancel an existing appointment
- emergency: describes urgent symptoms (e.g. chest pain, trouble breathing, heavy bleeding)
- other: anything else, including requests for a diagnosis or treatment advice

Also return a confidence between 0 and 1, and any details the patient gave:
doctor_name, specialty, booking_day (as the patient said it, e.g. "Thursday"), booking_id,
patient_name, patient_phone, and slot_choice (the number of the offered slot the patient picked,
e.g. "book number 2" -> 2).
For a booking, also include details the patient gave in earlier messages of the same request.
Leave a detail empty when the patient did not give it. Never invent details.
"""
DONT_KNOW = "I don't know"

ANSWER_DOCS_SYSTEM_PROMPT = """\
You are a clinic front-desk assistant.
Answer the patient's question using ONLY the clinic document passages provided.
Do not use outside knowledge or invent information.
If the passages do not contain enough information, say "I don't know".
Give a clear and simple answer.
"""
