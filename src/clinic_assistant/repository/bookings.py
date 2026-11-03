"""SQL for bookings; the partial unique index makes a double booking impossible (ADR 0006).

Owner: @NoorAlbusaidi (#15). Shell from #83 so the graph and app can wire it: add the methods.
"""

from clinic_assistant.repository.db import DictPool


class BookingsRepository:
    """Create bookings on the shared pool."""

    def __init__(self, pool: DictPool) -> None:
        self.pool = pool
