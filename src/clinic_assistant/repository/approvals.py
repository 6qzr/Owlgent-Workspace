"""Database operations for staff approvals."""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from clinic_assistant.domain import ApprovalAction, ApprovalStatus
from clinic_assistant.repository.db import DictPool


class ApprovalNotFoundError(Exception):
    """Approval does not exist."""


class ApprovalAlreadyDecidedError(Exception):
    """Approval has already been approved or rejected."""


class ApprovalsRepository:
    """Manage staff approval requests in PostgreSQL."""

    def __init__(self, pool: DictPool) -> None:
        # Save the database connection pool.
        self.pool = pool

    async def create(
        self,
        conversation_id: UUID,
        booking_id: int,
        action: ApprovalAction,
    ) -> int:
        """Create a pending approval without duplicates."""

        async with (
            self.pool.connection() as conn,
            conn.transaction(),
            conn.cursor(row_factory=dict_row) as cur,
        ):
            # Lock this action to prevent duplicate requests.
            lock_key = f"{conversation_id}:{booking_id}:{action.value}"

            await cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (lock_key,),
            )

            # Check whether the same approval is already pending.
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

            # Return the existing ID if found.
            if existing is not None:
                return int(existing["id"])

            # Create a new pending approval.
            await cur.execute(
                """
                INSERT INTO approvals (
                    conversation_id,
                    booking_id,
                    action,
                    status
                )
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
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT
                    id,
                    conversation_id,
                    booking_id,
                    action,
                    status,
                    reason,
                    decided_by,
                    decided_at
                FROM approvals
                WHERE status = 'pending'
                ORDER BY id
                """
            )

            rows = await cur.fetchall()

            return [dict(row) for row in rows]

    async def get_by_id(
        self,
        approval_id: int,
    ) -> dict[str, Any] | None:
        """Find one approval by its ID."""

        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT *
                FROM approvals
                WHERE id = %s
                """,
                (approval_id,),
            )

            row = await cur.fetchone()

            if row is None:
                return None

            return dict(row)

    async def find_cancellable_booking(
        self,
        booking_id: int,
        conversation_id: UUID,
    ) -> dict[str, Any] | None:
        """Find a confirmed booking owned by this conversation."""

        # Only allow cancellation of confirmed bookings
        # belonging to the current conversation.
        query = """
            SELECT
                id,
                slot_id,
                conversation_id,
                status
            FROM bookings
            WHERE id = %s
              AND conversation_id = %s
              AND status = 'confirmed'
            LIMIT 1
        """

        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                query,
                (booking_id, conversation_id),
            )
            booking = await cur.fetchone()

        # Return None if the booking does not exist,
        # belongs to another conversation,
        # or is not confirmed.
        return dict(booking) if booking is not None else None

    async def decide(
        self,
        approval_id: int,
        approved: bool,
        reason: str,
        staff: str,
    ) -> dict[str, Any]:
        """Update the booking and approval in one transaction."""

        # Remove extra spaces.
        reason = reason.strip()
        staff = staff.strip()

        # Staff must provide a name and reason.
        if not reason or not staff:
            raise ValueError("Reason and staff are required")

        # Select the new approval status.
        new_approval_status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED

        async with (
            self.pool.connection() as conn,
            conn.transaction(),
            conn.cursor(row_factory=dict_row) as cur,
        ):
            # Lock the approval to prevent duplicate decisions.
            await cur.execute(
                """
                SELECT id, status, booking_id, action
                FROM approvals
                WHERE id = %s
                FOR UPDATE
                """,
                (approval_id,),
            )

            approval = await cur.fetchone()

            # Check whether approval exists.
            if approval is None:
                raise ApprovalNotFoundError("Approval not found")

            # Prevent approving or rejecting twice.
            if approval["status"] != ApprovalStatus.PENDING:
                raise ApprovalAlreadyDecidedError("Approval already decided")

            # Lock the related booking.
            await cur.execute(
                """
                SELECT status
                FROM bookings
                WHERE id = %s
                FOR UPDATE
                """,
                (approval["booking_id"],),
            )

            booking = await cur.fetchone()

            if booking is None:
                raise ValueError("Booking not found")

            action = approval["action"]
            booking_status = booking["status"]
            new_booking_status = None

            # Handle a new booking request.
            if action == ApprovalAction.BOOK:
                if booking_status != "pending_approval":
                    raise ValueError("Booking is not pending approval")

                new_booking_status = "confirmed" if approved else "rejected"

            # Handle a cancellation request.
            elif action == ApprovalAction.CANCEL:
                if booking_status != "confirmed":
                    raise ValueError("Booking cannot be cancelled")

                # Only cancel if staff approves.
                if approved:
                    new_booking_status = "cancelled"

            else:
                raise ValueError("Unknown approval action")

            # Update the booking if its status should change.
            if new_booking_status is not None:
                await cur.execute(
                    """
                    UPDATE bookings
                    SET status = %s
                    WHERE id = %s
                    """,
                    (
                        new_booking_status,
                        approval["booking_id"],
                    ),
                )

            # Save the staff decision in approvals.
            await cur.execute(
                """
                UPDATE approvals
                SET status = %s,
                    reason = %s,
                    decided_by = %s,
                    decided_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (
                    new_approval_status.value,
                    reason,
                    staff,
                    approval_id,
                ),
            )

            updated = await cur.fetchone()

            if updated is None:
                raise RuntimeError("Could not update approval")

            return dict(updated)
