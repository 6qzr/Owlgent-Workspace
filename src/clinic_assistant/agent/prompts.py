"""Prompts and model-facing limits, kept out of node code (AGENTS.md: prompts live in config)."""

# Only the most recent messages are sent to the model; the checkpoint keeps the full history.
# Move to Settings.max_history_messages once the config from #55 is merged.
CLASSIFY_HISTORY_WINDOW = 10

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
doctor_name, specialty, booking_day (as the patient said it, e.g. "Thursday"), booking_id.
Leave a detail empty when the patient did not give it. Never invent details.
"""
