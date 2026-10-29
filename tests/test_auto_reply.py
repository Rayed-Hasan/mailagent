"""Owner-toggle and mocked outbound auto-reply coverage."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from mailagent.core.types import (
    AutonomyMode,
    ClassificationResult,
    DraftStatus,
    EmailAction,
    EmailCategory,
    EmailMessage,
)
from mailagent.dashboard import app as dashboard
from mailagent.core.config import settings


@pytest.mark.asyncio
async def test_owner_can_enable_safe_auto_replies_but_demo_cannot():
    mock_db = MagicMock()
    mock_db.set_auto_reply_enabled = AsyncMock(return_value=True)
    with patch.object(settings, "public_demo_mode", False), patch.object(dashboard, "db", mock_db):
        result = await dashboard.set_auto_reply_setting(
            dashboard.AutoReplyRequest(enabled=True), user_id="owner-1"
        )
    assert result == {"enabled": True, "mode": "auto_safe"}
    mock_db.set_auto_reply_enabled.assert_awaited_once_with("owner-1", True)

    with patch.object(settings, "public_demo_mode", True):
        with pytest.raises(HTTPException) as exc:
            await dashboard.set_auto_reply_setting(
                dashboard.AutoReplyRequest(enabled=True), user_id="owner-1"
            )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enabled, expected",
    [(True, AutonomyMode.AUTO_SAFE), (False, AutonomyMode.APPROVE)],
)
async def test_agent_loads_owner_auto_reply_setting(enabled, expected):
    from mailagent.core.agent import EmailAgent

    mock_db = MagicMock()
    mock_db.initialize = AsyncMock()
    mock_db.get_auto_reply_enabled = AsyncMock(return_value=enabled)
    mock_db.get_voice_profile = AsyncMock(return_value=None)
    mock_db.get_provider_settings_by_user = AsyncMock(return_value=[])
    mock_db.get_accounts_by_user = AsyncMock(return_value=[])
    with patch("mailagent.core.agent.Database", return_value=mock_db):
        agent = EmailAgent("owner-1")
    await agent.initialize()
    assert agent.autonomy_mode == expected
    assert agent.send_flow.autonomy_mode == expected


@pytest.mark.asyncio
async def test_eligible_auto_safe_message_sends_one_mocked_thread_reply():
    from mailagent.core.agent import EmailAgent
    from mailagent.policy.send_flow import SendFlow

    mock_db = MagicMock()
    mock_db.save_draft = AsyncMock(return_value="draft-1")
    mock_db.save_rate_limit = AsyncMock(return_value="rate-1")
    mock_db.log_audit = AsyncMock(return_value="audit-1")
    mock_db.is_kill_switch_active = AsyncMock(return_value=False)
    mock_db.update_draft_status = AsyncMock(return_value=True)
    mock_provider = MagicMock()
    mock_provider.create_draft = AsyncMock(return_value="gmail-draft-1")
    mock_provider.send_reply = AsyncMock(return_value=True)

    with patch("mailagent.core.agent.Database", return_value=mock_db):
        agent = EmailAgent("owner-1", autonomy_mode=AutonomyMode.AUTO_SAFE)
    agent.send_flow = SendFlow(AutonomyMode.AUTO_SAFE, db=None)
    agent.draft_generator.generate_draft = AsyncMock(return_value="Thanks, Thursday works for me.")
    agent.worth_sending_policy.should_send_reply = AsyncMock(return_value=(True, "eligible"))
    agent.rate_limiter.check_rate_limit = MagicMock(
        return_value=MagicMock(can_send=True, reason="within limit")
    )
    agent.rate_limiter.record_reply = MagicMock()

    email = EmailMessage(
        message_id="gmail-id-1",
        thread_id="thread-1",
        sender="Casey Example <casey@example.invalid>",
        sender_email="casey@example.invalid",
        subject="Meeting time",
        body="Would Thursday work for you?",
        received_at=datetime.now(timezone.utc),
        raw_headers={"Message-ID": "<message@example.invalid>"},
    )
    classification = ClassificationResult(
        email_id="email-1",
        category=EmailCategory.PERSONAL,
        priority_score=80,
        action=EmailAction.REPLY,
        confidence=0.99,
        reason="Needs a reply",
    )

    await agent._generate_and_handle_draft(
        email,
        classification,
        "email-1",
        "classification-1",
        "account-1",
        mock_provider,
        [],
        [email],
    )

    mock_provider.create_draft.assert_awaited_once_with(
        to="casey@example.invalid",
        subject="Re: Meeting time",
        body="Thanks, Thursday works for me.",
        in_reply_to="<message@example.invalid>",
        thread_id="thread-1",
        references=[],
    )
    mock_provider.send_reply.assert_awaited_once_with("gmail-draft-1")
    mock_db.update_draft_status.assert_awaited_once_with("draft-1", DraftStatus.SENT)
    assert agent.send_flow.check_already_sent("email-1")


@pytest.mark.asyncio
async def test_database_audit_adapter_accepts_agent_dict_entries():
    from mailagent.core.database import Database

    database = Database.__new__(Database)
    database.storage = MagicMock()
    database.storage.log_audit = AsyncMock(return_value="audit-1")
    result = await database.log_audit(
        {
            "email_id": "fictional-email-1",
            "event_type": "draft_created",
            "reason": "Auto-safe reply",
            "context": {"autonomy_mode": "auto_safe"},
        }
    )
    assert result == "audit-1"
    entry = database.storage.log_audit.await_args.args[0]
    assert entry.email_id == "fictional-email-1"
    assert entry.context == {"autonomy_mode": "auto_safe"}
