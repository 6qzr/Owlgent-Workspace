"""Database operations for booking appointment slots.

The PostgreSQL partial unique index prevents double booking.
"""

import asyncio
from datetime import datetime
from typing import cast
from uuid import UUID

from psycopg.errors import UniqueViolation

from clinic_assistant.domain import BookingStatus
from clinic_assistant.repository.db import DB_TIMEOUT_SECONDS, DictPool


class SlotTaken(Exception):
    """The selected appointment slot is already booked."""


class BookingsRepository:
    """Create bookings using the shared PostgreSQL pool."""

    def __init__(self, pool: DictPool) -> None:
        self.pool = pool

    async def create(
        self,
        slot_id: int,
        conversation_id: UUID,
        patient_name: str,
        patient_phone: str,
        status: BookingStatus,
    ) -> int:
        """Create a booking and return its database ID."""

        query = """
            INSERT INTO bookings (
                slot_id,
                conversation_id,
                patient_name,
                patient_phone,
                status
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """

        try:
            async with (
                asyncio.timeout(DB_TIMEOUT_SECONDS),
                self.pool.connection() as conn,
            ):
                cursor = await conn.execute(
                    query,
                    (
                        slot_id,
                        conversation_id,
                        patient_name,
                        patient_phone,
                        status.value,
                    ),
                )

                booking = await cursor.fetchone()

        except UniqueViolation as exc:
            # Only the active-slot unique index means SlotTaken.
            # Other database constraint errors must not be hidden.
            if exc.diag.constraint_name != "unique_active_booking_per_slot":
                raise

            raise SlotTaken("This appointment slot is already booked.") from exc

        if booking is None:
            raise RuntimeError("Could not create booking")

        return int(booking["id"])

    async def get_slot_start(self, slot_id: int) -> datetime | None:
        """Return the start time of a future appointment slot."""

        query = """
            SELECT starts_at
            FROM slots
            WHERE id = %s
              AND starts_at > CURRENT_TIMESTAMP
        """

        async with (
            asyncio.timeout(DB_TIMEOUT_SECONDS),
            self.pool.connection() as conn,
        ):
            cursor = await conn.execute(
                query,
                (slot_id,),
            )

            slot = await cursor.fetchone()

        if slot is None:
            return None

        return cast(datetime, slot["starts_at"])
