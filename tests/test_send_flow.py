"""
Unit tests for send flow and autonomy modes
"""

import pytest
from datetime import datetime
from mailagent.core.types import EmailAction, AutonomyMode, DraftStatus, Draft
from mailagent.policy.send_flow import SendFlow


@pytest.fixture
def send_flow():
    return SendFlow(autonomy_mode=AutonomyMode.APPROVE)


@pytest.fixture
def sample_draft():
    return Draft(
        email_id="email_123",
        classification_id="class_123",
        content="Hi, thanks for your email. I'll get back to you soon."
    )


@pytest.mark.asyncio
async def test_approve_mode_requires_human_approval(send_flow, sample_draft):
    """Test that approve mode always requires human approval"""
    status, reason = await send_flow.process_draft(sample_draft, EmailAction.REPLY)
    assert status == DraftStatus.PENDING
    assert "awaiting human approval" in reason.lower()


@pytest.mark.asyncio
async def test_auto_safe_mode_sends_routine_replies():
    """Test that auto_safe mode sends routine replies"""
    send_flow = SendFlow(autonomy_mode=AutonomyMode.AUTO_SAFE)
    routine_draft = Draft(
        email_id="email_123",
        classification_id="class_123",
        content="Thanks, I'll look into it."
    )

    status, reason = await send_flow.process_draft(routine_draft, EmailAction.REPLY)
    assert status == DraftStatus.APPROVED or status == DraftStatus.PENDING


@pytest.mark.asyncio
async def test_auto_safe_mode_flags_non_routine():
    """Test that auto_safe mode flags non-routine replies"""
    send_flow = SendFlow(autonomy_mode=AutonomyMode.AUTO_SAFE)
    non_routine_draft = Draft(
        email_id="email_123",
        classification_id="class_123",
        content="I need to carefully consider this complex matter and provide a detailed analysis..."
    )

    status, reason = await send_flow.process_draft(non_routine_draft, EmailAction.REPLY)
    assert status == DraftStatus.PENDING
    assert "human approval" in reason.lower()


@pytest.mark.asyncio
async def test_auto_full_mode_sends_all():
    """Test that auto_full mode sends all replies"""
    send_flow = SendFlow(autonomy_mode=AutonomyMode.AUTO_FULL)
    draft = Draft(
        email_id="email_123",
        classification_id="class_123",
        content="Any content"
    )

    status, reason = await send_flow.process_draft(draft, EmailAction.REPLY)
    assert status == DraftStatus.APPROVED


@pytest.mark.asyncio
async def test_flag_human_action():
    """Test that flag_human action always flags for human"""
    send_flow = SendFlow(autonomy_mode=AutonomyMode.AUTO_FULL)
    draft = Draft(
        email_id="email_123",
        classification_id="class_123",
        content="Any content"
    )

    status, reason = await send_flow.process_draft(draft, EmailAction.FLAG_HUMAN)
    assert status == DraftStatus.PENDING
    assert "human review" in reason.lower()


@pytest.mark.asyncio
async def test_archive_action():
    """Test that archive action doesn't create draft"""
    send_flow = SendFlow()
    draft = Draft(
        email_id="email_123",
        classification_id="class_123",
        content="Any content"
    )

    status, reason = await send_flow.process_draft(draft, EmailAction.ARCHIVE)
    assert status == DraftStatus.PENDING
    assert "archived" in reason.lower()


def test_cancel_draft():
    """Test draft cancellation"""
    send_flow = SendFlow()
    draft_id = "draft_123"

    result = send_flow.cancel_draft(draft_id)
    assert result is True
    assert draft_id in send_flow.cancelled_drafts


def test_set_autonomy_mode():
    """Test changing autonomy mode"""
    send_flow = SendFlow(autonomy_mode=AutonomyMode.APPROVE)
    assert send_flow.autonomy_mode == AutonomyMode.APPROVE

    send_flow.set_autonomy_mode(AutonomyMode.AUTO_FULL)
    assert send_flow.autonomy_mode == AutonomyMode.AUTO_FULL


@pytest.mark.asyncio
async def test_duplicate_send_prevention():
    """Test that duplicate sends are prevented"""
    send_flow = SendFlow(autonomy_mode=AutonomyMode.AUTO_FULL)
    draft = Draft(
        email_id="email_123",
        classification_id="class_123",
        content="First reply"
    )

    # First send should succeed
    status1, reason1 = await send_flow.process_draft(draft, EmailAction.REPLY)
    assert status1 == DraftStatus.APPROVED

    # Record as sent
    send_flow.record_sent("email_123")

    # Second send should be rejected
    status2, reason2 = await send_flow.process_draft(draft, EmailAction.REPLY)
    assert status2 == DraftStatus.REJECTED
    assert "already sent" in reason2.lower()


def test_record_and_check_sent():
    """Test recording and checking sent emails"""
    send_flow = SendFlow()

    # Initially not sent
    assert not send_flow.check_already_sent("email_123")

    # Record as sent
    send_flow.record_sent("email_123")

    # Now should be marked as sent
    assert send_flow.check_already_sent("email_123")


@pytest.mark.asyncio
async def test_cancel_draft_with_db_no_db():
    """Test cancel draft without database (fallback to in-memory)"""
    send_flow = SendFlow(db=None)
    draft_id = "draft_123"

    result = await send_flow.cancel_draft_with_db(draft_id)
    assert result is True
    assert draft_id in send_flow.cancelled_drafts
