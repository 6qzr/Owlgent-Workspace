"""Book a slot; same-day bookings go to staff approval.

Owner: @NoorAlbusaidi (#15). Stubs from the graph skeleton: replace the bodies, keep the names.
"""

from langchain_core.runnables import RunnableConfig

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState


async def prepare_booking(state: ConversationState, config: RunnableConfig) -> Update:
    """Hold the slot; set pending_action when the booking is same-day.

    config["configurable"]["bookings_repository"] is the BookingsRepository (wired in graph.py).
    Always write pending_action: None for a future day, so an old value never reroutes this turn.
    """
    return {"pending_action": None}


async def confirm_booking(state: ConversationState) -> Update:
    """Confirm a future-day booking."""
    return reply_update("Your appointment is booked.")
