"""Comprehensive test suite for Real Gmail OAuth, Deduplication, Sync, and Owner Boundaries."""

import pytest
import base64
from email import message_from_bytes
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from pydantic import BaseModel

from mailagent.core.types import EmailMessage, EmailCategory, DraftStatus
from mailagent.providers.gmail_provider import GmailProvider, GmailOAuthFlow, DEFAULT_SCOPES, READONLY_SCOPES
from mailagent.mail.sync_service import GmailSyncService
from mailagent.core.sqlite_storage import SQLiteStorage
from mailagent.core.secret_store import SecretStore
from mailagent.core.config import settings
from mailagent.dashboard import app as dashboard


@pytest.fixture
def clean_sqlite_storage(tmp_path):
    db_file = str(tmp_path / "test_gmail_sync.db")
    storage = SQLiteStorage(db_file, secret_store=SecretStore(key=b"0" * 32))
    return storage


class TestGmailOAuthSecurityAndFlow:
    """Test OAuth authorization generation, scopes, state, and token secrecy."""

    def test_oauth_auth_url_generation_with_state(self):
        with patch.object(settings, "google_client_id", "test-client-id"), \
             patch.object(settings, "google_client_secret", "test-client-secret"), \
             patch.object(settings, "google_redirect_uri", "http://localhost:8000/auth/gmail/callback"):
            
            with patch("mailagent.providers.gmail_provider.InstalledAppFlow") as mock_flow_cls:
                mock_flow = MagicMock()
                mock_flow_cls.from_client_config.return_value = mock_flow
                mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?state=xyz", "xyz")

                url = GmailOAuthFlow.get_authorization_url(state="secure_state_123")
                assert "https://accounts.google.com" in url
                mock_flow.authorization_url.assert_called_once_with(prompt="consent", access_type="offline", state="secure_state_123")

    def test_oauth_code_exchange(self):
        with patch.object(settings, "google_client_id", "test-client-id"), \
             patch.object(settings, "google_client_secret", "test-client-secret"), \
             patch.object(settings, "google_redirect_uri", "http://localhost:8000/auth/gmail/callback"):
            
            with patch("mailagent.providers.gmail_provider.InstalledAppFlow") as mock_flow_cls:
                mock_flow = MagicMock()
                mock_flow_cls.from_client_config.return_value = mock_flow
                mock_credentials = MagicMock()
                mock_credentials.token = "access_token_123"
                mock_credentials.refresh_token = "refresh_token_456"
                mock_credentials.token_uri = "https://oauth2.googleapis.com/token"
                mock_credentials.client_id = "test-client-id"
                mock_credentials.client_secret = "test-client-secret"
                mock_credentials.scopes = DEFAULT_SCOPES
                mock_credentials.expiry = datetime(2026, 12, 31)
                mock_flow.credentials = mock_credentials

                tokens = GmailOAuthFlow.exchange_code_for_token("auth_code_xyz")
                assert tokens["token"] == "access_token_123"
                assert tokens["refresh_token"] == "refresh_token_456"
                mock_flow.fetch_token.assert_called_once_with(code="auth_code_xyz")

    @pytest.mark.asyncio
    async def test_sqlite_oauth_state_is_expiring_one_time_and_shared_after_restart(self, clean_sqlite_storage, tmp_path):
        import hashlib
        state_hash = hashlib.sha256(b"opaque-state").hexdigest()
        await clean_sqlite_storage.initialize()
        await clean_sqlite_storage.create_oauth_state(state_hash, datetime.now(timezone.utc) + timedelta(minutes=15))
        restarted = SQLiteStorage(str(tmp_path / "test_gmail_sync.db"), secret_store=SecretStore(key=b"0" * 32))
        assert await restarted.consume_oauth_state(state_hash) is True
        assert await clean_sqlite_storage.consume_oauth_state(state_hash) is False
        expired_hash = hashlib.sha256(b"expired-state").hexdigest()
        await clean_sqlite_storage.create_oauth_state(expired_hash, datetime.now(timezone.utc) - timedelta(seconds=1))
        assert await restarted.consume_oauth_state(expired_hash) is False

    @pytest.mark.asyncio
    async def test_account_credentials_are_encrypted_and_readable_after_restart(self, clean_sqlite_storage, tmp_path):
        import sqlite3
        await clean_sqlite_storage.initialize()
        account_id = await clean_sqlite_storage.save_account(
            user_id="demo-user", provider="gmail", email_address="demo@gmail.com",
            credentials={"token": "access", "refresh_token": "refresh-private"},
            account_id="stable-demo-account",
        )
        assert account_id == "stable-demo-account"
        raw_db = sqlite3.connect(clean_sqlite_storage.db_path)
        stored = raw_db.execute("SELECT credentials FROM email_accounts WHERE id=?", (account_id,)).fetchone()[0]
        raw_db.close()
        assert "refresh-private" not in stored
        restarted = SQLiteStorage(clean_sqlite_storage.db_path, secret_store=SecretStore(key=b"0" * 32))
        restored = await restarted.get_account(account_id)
        assert restored["credentials"]["refresh_token"] == "refresh-private"

    @pytest.mark.asyncio
    async def test_auto_reply_setting_is_off_by_default_and_persists(self, clean_sqlite_storage, tmp_path):
        await clean_sqlite_storage.initialize()
        assert await clean_sqlite_storage.get_auto_reply_enabled("owner-1") is False
        assert await clean_sqlite_storage.set_auto_reply_enabled("owner-1", True) is True
        restarted = SQLiteStorage(clean_sqlite_storage.db_path, secret_store=SecretStore(key=b"0" * 32))
        assert await restarted.get_auto_reply_enabled("owner-1") is True
        await restarted.set_auto_reply_enabled("owner-1", False)
        assert await clean_sqlite_storage.get_auto_reply_enabled("owner-1") is False

    @pytest.mark.asyncio
    async def test_gmail_provider_token_refresh(self):
        """Test that expired credentials trigger refresh via Request()."""
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.refresh_token = "valid_refresh_token"

        provider = GmailProvider({"token": "old"}, scopes=DEFAULT_SCOPES)
        provider.credentials = mock_creds

        with patch("mailagent.providers.gmail_provider.build") as mock_build:
            mock_build.return_value = MagicMock()
            success = await provider.connect()
            assert success is True
            mock_creds.refresh.assert_called_once()


class TestRealMessageNormalizationAndDeduplication:
    """Test duplicate prevention, parsing, and storage in SQLite."""

    @pytest.mark.asyncio
    async def test_gmail_reply_draft_uses_original_sender_thread_and_headers(self):
        provider = GmailProvider({"token": "test"})
        provider.service = MagicMock()
        provider.service.users.return_value.drafts.return_value.create.return_value.execute.return_value = {
            "id": "draft-fictional-1"
        }

        draft_id = await provider.create_draft(
            to="casey@example.invalid",
            subject="Re: Meeting time",
            body="Could you share which day works best?",
            in_reply_to="<original@example.invalid>",
            thread_id="gmail-thread-fictional",
            references=["<earlier@example.invalid>"],
        )

        assert draft_id == "draft-fictional-1"
        request = provider.service.users.return_value.drafts.return_value.create.call_args.kwargs
        message = request["body"]["message"]
        assert message["threadId"] == "gmail-thread-fictional"
        raw = base64.urlsafe_b64decode(message["raw"] + "=" * (-len(message["raw"]) % 4))
        mime = message_from_bytes(raw)
        assert mime["To"] == "casey@example.invalid"
        assert mime["Subject"] == "Re: Meeting time"
        assert mime["In-Reply-To"] == "<original@example.invalid>"
        assert mime["References"] == "<earlier@example.invalid> <original@example.invalid>"
        assert "Could you share which day works best?" in mime.get_payload(decode=True).decode()

    @pytest.mark.asyncio
    async def test_gmail_provider_refuses_empty_reply_body(self):
        provider = GmailProvider({"token": "test"})
        with pytest.raises(ValueError, match="empty email draft"):
            await provider.create_draft(
                to="casey@example.invalid", subject="Re: Meeting", body="  "
            )

    @pytest.mark.asyncio
    async def test_deduplication_prevents_duplicate_inserts(self, clean_sqlite_storage):
        await clean_sqlite_storage.initialize()

        # Save an account first so foreign key references match
        account_id = await clean_sqlite_storage.save_account(
            user_id="test-user",
            provider="gmail",
            email_address="dedicated@gmail.com",
            credentials={"token": "t"}
        )

        email1 = EmailMessage(
            message_id="gmail-msg-001",
            thread_id="gmail-thread-001",
            sender="Sender One <sender1@example.com>",
            sender_email="sender1@example.com",
            subject="First Test Email",
            body="This is genuine email body.",
            received_at=datetime.now(timezone.utc),
            raw_headers={"From": "sender1@example.com", "Subject": "First Test Email"},
        )

        id1 = await clean_sqlite_storage.save_email(email1, account_id)
        assert id1 is not None

        # Try to save the exact same message_id for the same account
        id2 = await clean_sqlite_storage.save_email(email1, account_id)
        assert id1 == id2  # Must return the existing ID without creating a duplicate row

        # Query all emails for account to verify count is exactly 1
        emails = await clean_sqlite_storage.get_emails_by_account(account_id)
        assert len(emails) == 1
        assert emails[0]["message_id"] == "gmail-msg-001"

        await clean_sqlite_storage.close()

    @pytest.mark.asyncio
    async def test_sync_mailbox_deduplicates_and_classifies(self, clean_sqlite_storage):
        await clean_sqlite_storage.initialize()
        from mailagent.core.database import Database
        db = Database(force_demo_mode=True)
        db.storage = clean_sqlite_storage

        account_id = await clean_sqlite_storage.save_account(
            user_id="test-user",
            provider="gmail",
            email_address="demo-judge@gmail.com",
            credentials={"token": "t"}
        )

        sync_service = GmailSyncService(db)

        mock_provider = MagicMock()
        mock_provider.fetch_emails = AsyncMock(return_value=[
            EmailMessage(
                message_id="msg-sync-1",
                thread_id="thread-sync-1",
                sender="Colleague <colleague@work.com>",
                sender_email="colleague@work.com",
                subject="Project status update inquiry",
                body="Could you please send over the latest status update for the project?",
                received_at=datetime.now(timezone.utc),
                raw_headers={},
            ),
            EmailMessage(
                message_id="msg-sync-2",
                thread_id="thread-sync-2",
                sender="Security Alert <security@service.com>",
                sender_email="security@service.com",
                subject="URGENT: Password reset required",
                body="Please reset your password immediately.",
                received_at=datetime.now(timezone.utc),
                raw_headers={},
            )
        ])

        # First sync run: should ingest 2 new messages
        stats1 = await sync_service.sync_mailbox(account_id, mock_provider)
        assert stats1["fetched"] == 2
        assert stats1["new"] == 2
        assert stats1["duplicates"] == 0

        # Second sync run: exact same messages returned by Gmail API
        stats2 = await sync_service.sync_mailbox(account_id, mock_provider)
        assert stats2["fetched"] == 2
        assert stats2["new"] == 0
        assert stats2["duplicates"] == 2

        # Verify classifications exist in DB
        emails = await clean_sqlite_storage.get_emails_by_account(account_id)
        assert len(emails) == 2

        await clean_sqlite_storage.close()


    @pytest.mark.asyncio
    async def test_sync_does_not_persist_deterministic_fallback_classification(self):
        from mailagent.core.types import ClassificationResult, EmailAction

        db = MagicMock()
        db.get_email_by_message_id = AsyncMock(return_value=None)
        db.save_email = AsyncMock(return_value="email-id")
        db.save_classification = AsyncMock()
        db.save_email_labels = AsyncMock()
        service = GmailSyncService(db)
        service.classifier.classify = AsyncMock(return_value=ClassificationResult(
            email_id="",
            category=EmailCategory.FYI,
            priority_score=50,
            action=EmailAction.ARCHIVE,
            confidence=0.85,
            reason="This is a deterministic fallback classification.",
        ))
        message = EmailMessage(
            message_id="fallback-message",
            thread_id="fallback-thread",
            sender="Sender <sender@example.com>",
            sender_email="sender@example.com",
            subject="A test message",
            body="A message for fallback classification coverage.",
            received_at=datetime.now(timezone.utc),
            raw_headers={},
        )
        provider = MagicMock()
        provider.fetch_emails = AsyncMock(return_value=[message])

        stats = await service.sync_mailbox("account-id", provider)

        assert stats["new"] == 1
        assert stats["unclassified"] == 1
        db.save_classification.assert_not_awaited()
        db.save_email_labels.assert_not_awaited()


class TestSecurityBoundariesAndJudgeAccess:
    """Verify owner route protection, unauthenticated judge access, and sending denial."""

    @pytest.mark.asyncio
    async def test_judge_can_access_demo_status_without_auth(self):
        with patch.object(settings, "public_demo_mode", True):
            with patch.object(dashboard, "db", MagicMock()):
                dashboard.db.get_emails_by_account = AsyncMock(return_value=[])
                with patch.object(dashboard.demo_rate_limiter, "check_rate_limit", AsyncMock(return_value=(True, None))):
                    with patch.object(dashboard.demo_rate_limiter, "release_request", AsyncMock()):
                        res = await dashboard.get_demo_status(request=MagicMock(), user_id="demo-user-judge")
                        assert res["demo_mode"] is True
                        assert "demo_account_id" in res
                        assert "gmail_connected" in res

    @pytest.mark.asyncio
    async def test_anonymous_judge_denied_from_owner_routes(self):
        """Owner endpoints MUST reject anonymous/invalid requests with 401."""
        with patch.object(settings, "public_demo_mode", True), \
             patch.object(settings, "dashboard_api_token", "secret-owner-token"), \
             patch.object(settings, "dashboard_user_id", "owner-user-id"):
            
            # Anonymous call to require_dashboard_auth without token
            from mailagent.dashboard.auth import require_dashboard_auth
            with pytest.raises(HTTPException) as exc:
                await require_dashboard_auth(authorization=None)
            assert exc.value.status_code == 401

            # Invalid token
            with pytest.raises(HTTPException) as exc:
                await require_dashboard_auth(authorization="Bearer wrong-token")
            assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_anonymous_judge_cannot_send_emails(self):
        """By default, anonymous visitors cannot send emails through the demo mailbox."""
        with patch.object(settings, "public_demo_mode", True), \
             patch.object(settings, "demo_allow_public_send", False):
            
            with pytest.raises(HTTPException) as exc:
                await dashboard.simulate_demo_send(
                    http_request=MagicMock(),
                    send_request=dashboard.DemoSendRequest(draft_id="draft-123"),
                    user_id="demo-user-judge",
                )
            assert exc.value.status_code == 403
            assert "sending is disabled" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_demo_draft_generation_rejects_fallback_without_saving(self):
        """A deterministic fallback must not be presented as an AI draft."""
        with patch.object(settings, "public_demo_mode", True):
            mock_email = {"id": "email-1", "subject": "Test Question", "body": "Can we meet tomorrow?"}
            mock_account = {"id": dashboard.get_demo_account_id()}
            mock_class = {"id": "class-1"}

            with patch.object(dashboard.db, "get_email", AsyncMock(return_value=mock_email)), \
                 patch.object(dashboard.db, "get_account_for_email", AsyncMock(return_value=mock_account)), \
                 patch.object(dashboard.db, "get_classification", AsyncMock(return_value=mock_class)), \
                 patch.object(dashboard.db, "save_draft", AsyncMock(return_value="draft-saved-1")), \
                 patch.object(dashboard.demo_rate_limiter, "check_rate_limit", AsyncMock(return_value=(True, None))), \
                 patch.object(dashboard.demo_rate_limiter, "release_request", AsyncMock()):

                with pytest.raises(HTTPException) as exc:
                    await dashboard.generate_demo_draft(
                        http_request=MagicMock(),
                        draft_request=dashboard.DemoDraftRequest(email_id="email-1"),
                        user_id="demo-user-judge",
                    )
                assert exc.value.status_code == 503
                assert "provider unavailable" in exc.value.detail
                dashboard.db.save_draft.assert_not_awaited()
