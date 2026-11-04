"""Verify that a pending cancellation approval survives an app restart.

Issue #16: Staff approve or reject paused actions.
Uses a real PostgreSQL checkpointer and the real cancellation workflow.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from clinic_assistant.agent.checkpointer import open_checkpointer
from clinic_assistant.agent.graph import Repositories, build_graph
from clinic_assistant.agent.nodes.classify import Classification
from clinic_assistant.config import Settings
from clinic_assistant.domain import Intent
from clinic_assistant.llm import FakeLLM
from clinic_assistant.repository.approvals import ApprovalsRepository
from clinic_assistant.repository.db import DictPool, create_pool
from clinic_assistant.repository.slots import SlotsRepository
from clinic_assistant.services.approval import ApprovalService
from clinic_assistant.services.conversation import (
    ConversationService,
    TurnStatus,
    thread_config,
)

pytestmark = pytest.mark.integration

POOL_TIMEOUT = 10.0


async def open_pool(settings: Settings) -> DictPool:
    """Open a new PostgreSQL connection pool."""
    pool = create_pool(settings)
    await pool.open(wait=True, timeout=POOL_TIMEOUT)
    return pool


async def create_confirmed_booking(
    pool: DictPool,
    conversation_id: UUID,
) -> tuple[int, int, int]:
    """Create a confirmed booking owned by the test conversation."""

    # Give this test its own doctor and future appointment.
    start = datetime.now(UTC) + timedelta(days=30)
    end = start + timedelta(minutes=30)

    async with pool.connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO doctors (name, specialty)
            VALUES (%s, %s)
            RETURNING id
            """,
            (f"Restart Test Doctor {uuid4()}", "Test Specialty"),
        )
        doctor = await cursor.fetchone()
        assert doctor is not None
        doctor_id = int(doctor["id"])

        cursor = await conn.execute(
            """
            INSERT INTO slots (doctor_id, starts_at, ends_at)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (doctor_id, start, end),
        )
        slot = await cursor.fetchone()
        assert slot is not None
        slot_id = int(slot["id"])

        cursor = await conn.execute(
            """
            INSERT INTO bookings (
                slot_id,
                conversation_id,
                patient_name,
                patient_phone,
                status
            )
            VALUES (%s, %s, %s, %s, 'confirmed')
            RETURNING id
            """,
            (
                slot_id,
                conversation_id,
                "Restart Test Patient",
                "90000000",
            ),
        )
        booking = await cursor.fetchone()
        assert booking is not None

    return int(booking["id"]), slot_id, doctor_id


async def cleanup_test_data(
    settings: Settings,
    conversation_id: UUID | None,
    booking_id: int | None,
    slot_id: int | None,
    doctor_id: int | None,
) -> None:
    """Remove only this test's clinic records."""

    if conversation_id is None:
        return

    pool = await open_pool(settings)

    try:
        async with pool.connection() as conn, conn.transaction():
            await conn.execute(
                "DELETE FROM approvals WHERE conversation_id = %s",
                (conversation_id,),
            )

            if booking_id is not None:
                await conn.execute(
                    "DELETE FROM bookings WHERE id = %s",
                    (booking_id,),
                )

            if slot_id is not None:
                await conn.execute(
                    "DELETE FROM slots WHERE id = %s",
                    (slot_id,),
                )

            if doctor_id is not None:
                await conn.execute(
                    "DELETE FROM doctors WHERE id = %s",
                    (doctor_id,),
                )

            await conn.execute(
                "DELETE FROM conversations WHERE id = %s",
                (conversation_id,),
            )
    finally:
        await pool.close()


async def test_pending_cancel_approval_survives_restart(
    settings: Settings,
) -> None:
    """Resume an interrupted cancellation after rebuilding the app."""

    conversation_id: UUID | None = None
    booking_id: int | None = None
    slot_id: int | None = None
    doctor_id: int | None = None

    try:
        # -----------------------------------------
        # PART 1: BEFORE THE APPLICATION RESTART
        # -----------------------------------------

        first_pool = await open_pool(settings)

        try:
            first_saver = await open_checkpointer(first_pool)
            first_approvals = ApprovalsRepository(first_pool)

            # Create the conversation directly in PostgreSQL.
            # No graph is needed to insert a conversation.
            conversation_id = uuid4()

            async with first_pool.connection() as conn:
                await conn.execute(
                    "INSERT INTO conversations (id) VALUES (%s)",
                    (conversation_id,),
                )

            # Create a confirmed booking for this conversation.
            booking_id, slot_id, doctor_id = await create_confirmed_booking(
                first_pool,
                conversation_id,
            )

            # FakeLLM classifies the patient's request as cancellation.
            classification = Classification(
                intent=Intent.CANCEL,
                confidence=0.99,
                booking_id=booking_id,
            )

            # Build one graph and one service for the cancellation.
            first_graph = build_graph(
                FakeLLM([classification]),
                first_saver,
                Repositories(approvals=first_approvals),
            )

            first_conversations = ConversationService(
                first_graph,
                first_pool,
            )

            # Patient requests cancellation of their own booking.
            turn = await first_conversations.send_message(
                conversation_id,
                f"Cancel booking {booking_id}",
            )

            # The workflow must pause for staff approval.
            assert turn.status == TurnStatus.AWAITING_APPROVAL
            assert turn.approval_id is not None

            approval_id = turn.approval_id

            # Verify pending approval is stored in PostgreSQL.
            pending = await first_approvals.get_by_id(approval_id)

            assert pending is not None
            assert pending["status"] == "pending"
            assert pending["action"] == "cancel"
            assert pending["booking_id"] == booking_id
            assert pending["conversation_id"] == conversation_id

            # Verify LangGraph is paused.
            saved = await first_graph.aget_state(thread_config(conversation_id))

            assert saved.next
            assert saved.values["approval_id"] == approval_id

            # The booking must remain confirmed before approval.
            async with first_pool.connection() as conn:
                cursor = await conn.execute(
                    "SELECT status FROM bookings WHERE id = %s",
                    (booking_id,),
                )
                before = await cursor.fetchone()

            assert before is not None
            assert before["status"] == "confirmed"

        finally:
            # Close the old pool to simulate application shutdown.
            await first_pool.close()

        # -----------------------------------------
        # PART 2: AFTER THE APPLICATION RESTART
        # -----------------------------------------

        second_pool = await open_pool(settings)

        try:
            # Create a new pool, checkpointer, repository, and graph.
            second_saver = await open_checkpointer(second_pool)
            second_approvals = ApprovalsRepository(second_pool)

            second_graph = build_graph(
                FakeLLM(),
                second_saver,
                Repositories(approvals=second_approvals),
            )

            # Recover the paused state using the same conversation ID.
            restored = await second_graph.aget_state(thread_config(conversation_id))

            assert restored.next
            assert restored.values["approval_id"] == approval_id

            # Verify approval is still pending after restart.
            pending_after_restart = await second_approvals.get_by_id(approval_id)

            assert pending_after_restart is not None
            assert pending_after_restart["status"] == "pending"

            # Staff approves the pending cancellation.
            approval_service = ApprovalService(
                second_approvals,
                second_graph,
            )

            result = await approval_service.decide(
                approval_id=approval_id,
                approved=True,
                reason="Cancellation approved by reception",
                staff="Test Receptionist",
            )

            # Verify the patient receives the approval outcome.
            assert result["outcome"] == "Your request was approved."

            # Verify the booking is now cancelled.
            async with second_pool.connection() as conn:
                cursor = await conn.execute(
                    "SELECT status FROM bookings WHERE id = %s",
                    (booking_id,),
                )
                booking_after = await cursor.fetchone()

            assert booking_after is not None
            assert booking_after["status"] == "cancelled"

            # Verify the approval record was updated.
            final_approval = await second_approvals.get_by_id(approval_id)

            assert final_approval is not None
            assert final_approval["status"] == "approved"

            # Verify the cancelled appointment slot is available again.
            free_slots = await SlotsRepository(second_pool).find_free_slots(doctor_id=doctor_id)

            assert any(slot["id"] == slot_id for slot in free_slots)

            # Verify the patient's conversation contains the outcome.
            second_conversations = ConversationService(
                second_graph,
                second_pool,
            )

            history = await second_conversations.get_conversation(conversation_id)

            assert any(
                message.role == "assistant" and message.content == "Your request was approved."
                for message in history.messages
            )

            # The graph must finish after the staff decision.
            final_state = await second_graph.aget_state(thread_config(conversation_id))

            assert final_state.next == ()

        finally:
            await second_pool.close()

    finally:
        # Clean up test clinic records.
        await cleanup_test_data(
            settings,
            conversation_id,
            booking_id,
            slot_id,
            doctor_id,
        )
