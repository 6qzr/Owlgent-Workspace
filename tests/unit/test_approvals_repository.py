
"""Test approvals repository without PostgreSQL."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinic_assistant.domain import ApprovalAction
from clinic_assistant.repository.approvals import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
    ApprovalsRepository,
)


def make_repository() -> tuple[ApprovalsRepository, MagicMock]:
    """Create a repository using a fake database."""

    # Fake database cursor.
    cursor = MagicMock()
    cursor.execute = AsyncMock()
    cursor.fetchone = AsyncMock()
    cursor.fetchall = AsyncMock()

    # Fake database connection.
    connection = MagicMock()
    connection.cursor.return_value.__aenter__ = AsyncMock(
        return_value=cursor
    )

    # Fake connection pool.
    pool = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(
        return_value=connection
    )

    return ApprovalsRepository(pool), cursor


async def test_create_approval() -> None:
    """Create a new pending approval."""

    repository, cursor = make_repository()

    # No existing approval, then return new ID.
    cursor.fetchone.side_effect = [
        None,
        {"id": 1},
    ]

    result = await repository.create(
        conversation_id=uuid4(),
        booking_id=10,
        action=ApprovalAction.BOOK,
    )

    assert result == 1
    assert cursor.execute.await_count == 3


async def test_create_duplicate() -> None:
    """Do not create the same pending approval twice."""

    repository, cursor = make_repository()

    cursor.fetchone.return_value = {"id": 5}

    result = await repository.create(
        conversation_id=uuid4(),
        booking_id=10,
        action=ApprovalAction.CANCEL,
    )

    assert result == 5

    # Advisory lock and SELECT only.
    assert cursor.execute.await_count == 2


async def test_list_pending() -> None:
    """Get pending approvals from all conversations."""

    repository, cursor = make_repository()

    cursor.fetchall.return_value = [
        {"id": 1, "status": "pending"},
        {"id": 2, "status": "pending"},
    ]

    result = await repository.list_pending()

    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 2


async def test_get_by_id() -> None:
    """Find an approval by ID."""

    repository, cursor = make_repository()

    cursor.fetchone.return_value = {
        "id": 1,
        "status": "pending",
    }

    result = await repository.get_by_id(1)

    assert result is not None
    assert result["id"] == 1


async def test_get_unknown_id() -> None:
    """Return None for an unknown approval."""

    repository, cursor = make_repository()

    cursor.fetchone.return_value = None

    result = await repository.get_by_id(999)

    assert result is None


@pytest.mark.parametrize(
    (
        "action",
        "approved",
        "booking_status",
        "expected_booking",
        "expected_approval",
        "expected_queries",
    ),
    [
        (
            "book",
            True,
            "pending_approval",
            "confirmed",
            "approved",
            4,
        ),
        (
            "book",
            False,
            "pending_approval",
            "rejected",
            "rejected",
            4,
        ),
        (
            "cancel",
            True,
            "confirmed",
            "cancelled",
            "approved",
            4,
        ),
        (
            "cancel",
            False,
            "confirmed",
            None,
            "rejected",
            3,
        ),
    ],
)
async def test_staff_decision(
    action: str,
    approved: bool,
    booking_status: str,
    expected_booking: str | None,
    expected_approval: str,
    expected_queries: int,
) -> None:
    """Test approving and rejecting bookings or cancellations."""

    repository, cursor = make_repository()

    # First query returns approval.
    # Second query returns booking.
    # Last query returns updated approval.
    cursor.fetchone.side_effect = [
        {
            "id": 1,
            "status": "pending",
            "booking_id": 10,
            "action": action,
        },
        {
            "status": booking_status,
        },
        {
            "id": 1,
            "status": expected_approval,
        },
    ]

    result = await repository.decide(
        approval_id=1,
        approved=approved,
        reason="Staff decision",
        staff="Receptionist",
    )

    assert result["status"] == expected_approval
    assert cursor.execute.await_count == expected_queries

    # Check which SQL updates were executed.
    executed_sql = [
        call.args[0]
        for call in cursor.execute.await_args_list
    ]

    booking_updates = [
        sql for sql in executed_sql
        if "UPDATE bookings" in sql
    ]

    if expected_booking is None:
        # Rejected cancellation must not change the booking.
        assert booking_updates == []
    else:
        assert len(booking_updates) == 1


async def test_unknown_approval() -> None:
    """An unknown approval cannot be decided."""

    repository, cursor = make_repository()

    cursor.fetchone.return_value = None

    with pytest.raises(ApprovalNotFoundError):
        await repository.decide(
            approval_id=999,
            approved=True,
            reason="Approved",
            staff="Receptionist",
        )


async def test_already_decided() -> None:
    """Do not allow two decisions on the same approval."""

    repository, cursor = make_repository()

    cursor.fetchone.return_value = {
        "id": 1,
        "status": "approved",
    }

    with pytest.raises(ApprovalAlreadyDecidedError):
        await repository.decide(
            approval_id=1,
            approved=False,
            reason="Rejected",
            staff="Receptionist",
        )


async def test_missing_reason() -> None:
    """Staff must provide a reason."""

    repository, _ = make_repository()

    with pytest.raises(ValueError):
        await repository.decide(
            approval_id=1,
            approved=False,
            reason="",
            staff="Receptionist",
        )


async def test_missing_staff() -> None:
    """Staff must provide their name."""

    repository, _ = make_repository()

    with pytest.raises(ValueError):
        await repository.decide(
            approval_id=1,
            approved=True,
            reason="Approved",
            staff="",
        )


async def test_invalid_booking_status() -> None:
    """Reject decisions on an invalid booking state."""

    repository, cursor = make_repository()

    cursor.fetchone.side_effect = [
        {
            "id": 1,
            "status": "pending",
            "booking_id": 10,
            "action": "book",
        },
        {
            "status": "cancelled",
        },
    ]

    with pytest.raises(ValueError, match="not pending approval"):
        await repository.decide(
            approval_id=1,
            approved=True,
            reason="Approved",
            staff="Receptionist",
        )
