"""Database operations for staff approvals."""

import asyncio
from typing import Any
from uuid import UUID

from clinic_assistant.domain import ApprovalAction, ApprovalStatus, BookingStatus
from clinic_assistant.repository.db import DB_TIMEOUT_SECONDS, DictPool


class ApprovalNotFoundError(Exception):
    """Approval does not exist."""


class ApprovalAlreadyDecidedError(Exception):
    """Approval has already been approved or rejected."""


class ApprovalsRepository:
    """Manage staff approval requests in PostgreSQL."""

    def __init__(self, pool: DictPool) -> None:
        self.pool = pool

    async def create(
        self,
        conversation_id: UUID,
        booking_id: int,
        action: ApprovalAction,
    ) -> int:
        """Create a pending approval, or return the one already pending for this action."""
        async with (
            asyncio.timeout(DB_TIMEOUT_SECONDS),
            self.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            # Serialise concurrent requests for the same action, so only one row is created.
            lock_key = f"{conversation_id}:{booking_id}:{action.value}"
            await cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (lock_key,),
            )

            await cur.execute(
                """
                SELECT id
                FROM approvals
                WHERE conversation_id = %s
                  AND booking_id = %s
                  AND action = %s
                  AND status = 'pending'
                ORDER BY id
                LIMIT 1
                """,
                (conversation_id, booking_id, action.value),
            )
            existing = await cur.fetchone()
            if existing is not None:
                return int(existing["id"])

            await cur.execute(
                """
                INSERT INTO approvals (conversation_id, booking_id, action, status)
                VALUES (%s, %s, %s, 'pending')
                RETURNING id
                """,
                (conversation_id, booking_id, action.value),
            )
            created = await cur.fetchone()
            if created is None:
                raise RuntimeError("Could not create approval")
            return int(created["id"])

    async def list_pending(self) -> list[dict[str, Any]]:
        """List all pending approvals from all conversations."""
        async with (
            asyncio.timeout(DB_TIMEOUT_SECONDS),
            self.pool.connection() as conn,
            conn.cursor() as cur,
        ):
            await cur.execute(
                """
                SELECT id, conversation_id, booking_id, action, status, reason,
                       decided_by, decided_at
                FROM approvals
                WHERE status = 'pending'
                ORDER BY id
                """
            )
            return [dict(row) for row in await cur.fetchall()]

    async def get_by_id(
        self,
        approval_id: int,
    ) -> dict[str, Any] | None:
        """Find one approval by its ID."""
        async with (
            asyncio.timeout(DB_TIMEOUT_SECONDS),
            self.pool.connection() as conn,
            conn.cursor() as cur,
        ):
            await cur.execute("SELECT * FROM approvals WHERE id = %s", (approval_id,))
            row = await cur.fetchone()
            return dict(row) if row is not None else None

    async def find_cancellable_booking(
        self,
        booking_id: int,
        conversation_id: UUID,
    ) -> dict[str, Any] | None:
        """A confirmed booking owned by this conversation, or None (unknown, other or cancelled)."""
        async with (
            asyncio.timeout(DB_TIMEOUT_SECONDS),
            self.pool.connection() as conn,
            conn.cursor() as cur,
        ):
            await cur.execute(
                """
                SELECT id, slot_id, conversation_id, status
                FROM bookings
                WHERE id = %s
                  AND conversation_id = %s
                  AND status = 'confirmed'
                """,
                (booking_id, conversation_id),
            )
            booking = await cur.fetchone()
        return dict(booking) if booking is not None else None

    async def decide(
        self,
        approval_id: int,
        approved: bool,
        reason: str,
        staff: str,
    ) -> None:
        """Record the staff decision and update its booking, in one transaction.

        Reason and staff were already validated where they came in (API and await_staff).
        """
        async with (
            asyncio.timeout(DB_TIMEOUT_SECONDS),
            self.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            # Both rows are locked FOR UPDATE, so two staff can't decide the same approval.
            await cur.execute(
                "SELECT id, status, booking_id, action FROM approvals WHERE id = %s FOR UPDATE",
                (approval_id,),
            )
            approval = await cur.fetchone()
            if approval is None:
                raise ApprovalNotFoundError("Approval not found")
            if approval["status"] != ApprovalStatus.PENDING:
                raise ApprovalAlreadyDecidedError("Approval already decided")

            await cur.execute(
                "SELECT status FROM bookings WHERE id = %s FOR UPDATE",
                (approval["booking_id"],),
            )
            booking = await cur.fetchone()
            if booking is None:
                raise ValueError("Booking not found")

            new_booking_status = next_booking_status(
                approval["action"], booking["status"], approved
            )
            if new_booking_status is not None:
                await cur.execute(
                    "UPDATE bookings SET status = %s WHERE id = %s",
                    (new_booking_status.value, approval["booking_id"]),
                )

            new_approval_status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            await cur.execute(
                """
                UPDATE approvals
                SET status = %s, reason = %s, decided_by = %s, decided_at = NOW()
                WHERE id = %s
                """,
                (new_approval_status.value, reason, staff, approval_id),
            )


def next_booking_status(action: str, current: str, approved: bool) -> BookingStatus | None:
    """The booking's status after the decision, or None when it stays as it is."""
    if action == ApprovalAction.BOOK:
        if current != BookingStatus.PENDING_APPROVAL:
            raise ValueError("Booking is not pending approval")
        return BookingStatus.CONFIRMED if approved else BookingStatus.REJECTED
    if action == ApprovalAction.CANCEL:
        if current != BookingStatus.CONFIRMED:
            raise ValueError("Booking cannot be cancelled")
        # A rejected cancellation keeps the booking confirmed.
        return BookingStatus.CANCELLED if approved else None
    raise ValueError("Unknown approval action")
