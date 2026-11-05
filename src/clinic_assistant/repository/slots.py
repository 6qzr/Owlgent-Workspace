"""Find available appointment slots from PostgreSQL."""

import asyncio
from datetime import date
from typing import Any

from clinic_assistant.repository.db import DB_TIMEOUT_SECONDS, DictPool


class SlotsRepository:
    """Find free appointment slots using PostgreSQL."""

    def __init__(self, pool: DictPool) -> None:
        self.pool = pool

    async def find_free_slots(
        self,
        doctor_id: int | None = None,
        doctor_name: str | None = None,
        specialty: str | None = None,
        booking_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Return future slots that are not already booked."""

        # Free means no booking that still holds the slot (the partial unique index's statuses).
        query = """
            SELECT
                s.id,
                s.doctor_id,
                d.name AS doctor_name,
                d.specialty,
                s.starts_at,
                s.ends_at
            FROM slots AS s
            JOIN doctors AS d
                ON d.id = s.doctor_id
            WHERE s.starts_at > CURRENT_TIMESTAMP
              AND NOT EXISTS (
                  SELECT 1
                  FROM bookings AS b
                  WHERE b.slot_id = s.id
                    AND b.status IN ('pending_approval', 'confirmed')
              )
        """
        params: list[Any] = []

        if doctor_id is not None:
            query += " AND d.id = %s"
            params.append(doctor_id)

        if doctor_name is not None:
            query += " AND d.name ILIKE %s"
            params.append(doctor_name)

        if specialty is not None:
            query += " AND d.specialty ILIKE %s"
            params.append(specialty)

        # The appointment's calendar day in Oman.
        if booking_date is not None:
            query += """
                AND (
                    s.starts_at AT TIME ZONE 'Asia/Muscat'
                )::date = %s
            """
            params.append(booking_date)

        query += " ORDER BY s.starts_at, d.name, s.id"

        async with (
            asyncio.timeout(DB_TIMEOUT_SECONDS),
            self.pool.connection() as conn,
            conn.cursor() as cursor,
        ):
            await cursor.execute(query, params)
            return list(await cursor.fetchall())
