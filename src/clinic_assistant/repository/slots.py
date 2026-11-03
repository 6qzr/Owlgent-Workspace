"""Find available appointment slots from PostgreSQL."""

from datetime import date
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


class SlotsRepository:
    """Find free appointment slots using PostgreSQL."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        # Use the shared database connection pool.
        self.pool = pool

    async def find_free_slots(
        self,
        doctor_id: int | None = None,
        doctor_name: str | None = None,
        specialty: str | None = None,
        booking_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Return future slots that are not already booked."""

        # Find future appointment slots.
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
                    AND b.status IN (
                        'pending_approval',
                        'confirmed'
                    )
              )
        """

        # Store filter values safely.
        params: list[Any] = []

        # Filter by doctor ID.
        if doctor_id is not None:
            query += " AND d.id = %s"
            params.append(doctor_id)

        # Filter by doctor name.
        if doctor_name is not None:
            query += " AND d.name ILIKE %s"
            params.append(doctor_name)

        # Filter by specialty.
        if specialty is not None:
            query += " AND d.specialty ILIKE %s"
            params.append(specialty)

        # Filter by appointment date in Oman.
        if booking_date is not None:
            query += """
                AND (
                    s.starts_at AT TIME ZONE 'Asia/Muscat'
                )::date = %s
            """
            params.append(booking_date)

        # Sort appointments from earliest to latest.
        query += " ORDER BY s.starts_at, d.name, s.id"

        # Connect to PostgreSQL.
        # dict_row returns results as dictionaries.
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(query, params)
            rows = await cursor.fetchall()

        # Return available appointments.
        return list(rows)
