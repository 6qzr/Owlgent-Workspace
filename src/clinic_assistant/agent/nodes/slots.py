"""Find available appointment slots for patients."""

from datetime import date, datetime, timedelta, timezone

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.repository.slots import SlotsRepository

# Oman uses UTC+4 throughout the year.
OMAN_TIMEZONE = timezone(timedelta(hours=4))

# Show a maximum of five appointments to the patient.
MAX_OFFERED_SLOTS = 5

BOOK_BY_NUMBER = (
    "To book, reply with the number of the appointment you want, your name and your phone number."
)


def get_slots_repository(config: RunnableConfig) -> SlotsRepository:
    """Get the slots repository from the graph configuration."""

    repository = config.get("configurable", {}).get("slots_repository")

    if not isinstance(repository, SlotsRepository):
        raise RuntimeError("Slots repository is not configured.")

    return repository


def parse_booking_day(value: str) -> date | None:
    """Convert a patient date or weekday into a Python date."""

    text = value.strip().lower()
    today = datetime.now(OMAN_TIMEZONE).date()

    # Handle today and tomorrow.
    if text == "today":
        return today

    if text == "tomorrow":
        return today + timedelta(days=1)

    # Python weekday numbers: Monday=0, Sunday=6.
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    # Find the next occurrence of the requested weekday.
    if text in weekdays:
        target_day = weekdays[text]

        # If the weekday is today, use today.
        days_ahead = (target_day - today.weekday()) % 7

        return today + timedelta(days=days_ahead)

    # Handle an exact date, such as 2026-11-05.
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


async def find_slots(
    state: ConversationState,
    config: RunnableConfig,
) -> Update:
    """Find available appointments and reply to the patient."""

    # Read patient details extracted by classify.
    entities = state.get("entities", {})

    doctor_name = entities.get("doctor_name")
    specialty = entities.get("specialty")
    booking_day = entities.get("booking_day")

    # Ask for the doctor or specialty if missing.
    if not doctor_name and not specialty:
        return {
            **reply_update("Which doctor or specialty would you like to see?"),
            "slots_offered": [],
        }

    # Convert the requested appointment date.
    booking_date = None

    if booking_day:
        booking_date = parse_booking_day(booking_day)

        # Explain if the date is not supported.
        if booking_date is None:
            return {
                **reply_update(
                    "Please provide a valid date, such as 2026-11-05, today, tomorrow, or Thursday."
                ),
                "slots_offered": [],
            }

    # Get the database repository.
    repository = get_slots_repository(config)

    # Find available slots in PostgreSQL.
    slots = await repository.find_free_slots(
        doctor_name=doctor_name,
        specialty=specialty,
        booking_date=booking_date,
    )

    # If no appointments are available, reply politely.
    if not slots:
        return {
            **reply_update(
                "Sorry, no free appointments were found. "
                "Would you like to try another date or doctor?"
            ),
            "slots_offered": [],
        }

    # Only offer the first five available appointments.
    offered = slots[:MAX_OFFERED_SLOTS]

    # Numbered from 1, because the patient books by number ("book number 2") and
    # prepare_booking reads slots_offered[slot_choice - 1].
    lines = ["Here are the available appointments:"]
    for number, slot in enumerate(offered, start=1):
        start = slot["starts_at"].astimezone(OMAN_TIMEZONE)
        when = f"{start:%Y-%m-%d at %I:%M %p}"
        lines.append(f"{number}. {slot['doctor_name']} ({slot['specialty']}): {when}")
    lines.append(BOOK_BY_NUMBER)

    return {
        **reply_update("\n".join(lines)),
        "slots_offered": [slot["id"] for slot in offered],
    }
