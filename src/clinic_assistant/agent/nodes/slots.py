"""Find free slots by doctor or specialty and date.

This node is used in the agent graph to search for available appointments
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState
from clinic_assistant.repository.slots import SlotsRepository

OMAN_TIMEZONE = ZoneInfo("Asia/Muscat")
MAX_OFFERED_SLOTS = 5


def get_slots_repository(config: RunnableConfig) -> SlotsRepository:
    """Get the shared repository from graph configuration."""

    repository = config.get("configurable", {}).get("slots_repository")

    if not isinstance(repository, SlotsRepository):
        raise RuntimeError("Slots repository is not configured.")

    return repository


def parse_booking_day(value: str) -> date | None:
    """Convert a patient date to a Python date."""

    text = value.strip().lower()
    today = datetime.now(OMAN_TIMEZONE).date()

    if text == "today":
        return today

    if text == "tomorrow":
        return today + timedelta(days=1)

    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


async def find_slots(
    state: ConversationState,
    config: RunnableConfig,
) -> Update:
    """Search available appointments and reply to the patient."""

    # Get the details extracted from the patient message.
    entities = state.get("entities", {})

    doctor_name = entities.get("doctor_name")
    specialty = entities.get("specialty")
    booking_day = entities.get("booking_day")

    # Ask for a doctor or specialty if neither is available.
    if not doctor_name and not specialty:
        return {
            **reply_update("Which doctor or specialty would you like to see?"),
            "slots_offered": [],
        }

    # Convert the requested date, if one was provided.
    booking_date = None

    if booking_day:
        booking_date = parse_booking_day(booking_day)

        if booking_date is None:
            return {
                **reply_update("Please provide the date as YYYY-MM-DD, or say today or tomorrow."),
                "slots_offered": [],
            }

    # Get the repository configured for this conversation.
    repository = get_slots_repository(config)

    # Search the real database.
    slots = await repository.find_free_slots(
        doctor_name=doctor_name,
        specialty=specialty,
        booking_date=booking_date,
    )

    # Give a friendly message if nothing is available.
    if not slots:
        return {
            **reply_update(
                "Sorry, no free appointments were found. "
                "Would you like to try another date or doctor?"
            ),
            "slots_offered": [],
        }

    # Show up to five options to keep the reply short.
    offered = slots[:MAX_OFFERED_SLOTS]
    slot_ids: list[int] = []
    lines = ["Here are the available appointments:"]

    for slot in offered:
        slot_ids.append(slot["id"])

        # Display appointment times in Oman.
        start = slot["starts_at"].astimezone(OMAN_TIMEZONE)

        lines.append(f"- {slot['doctor_name']} ({slot['specialty']}): {start:%Y-%m-%d at %I:%M %p}")

    lines.append("Which appointment would you like?")

    # Save the offered slot IDs for later booking steps.
    return {
        **reply_update("\n".join(lines)),
        "slots_offered": slot_ids,
    }
