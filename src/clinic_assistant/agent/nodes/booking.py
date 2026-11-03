"""Book a slot; same-day bookings go to staff approval.

Owner: @NoorAlbusaidi (#15). Stubs from the graph skeleton: replace the bodies, keep the names.
"""

from clinic_assistant.agent.nodes import Update, reply_update
from clinic_assistant.agent.state import ConversationState


async def prepare_booking(state: ConversationState) -> Update:
    """Hold the slot; set pending_action when the booking is same-day."""
    return {}


async def confirm_booking(state: ConversationState) -> Update:
    """Confirm a future-day booking."""
    return reply_update("Your appointment is booked.")
