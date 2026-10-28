"""Security tests for public demo mode isolation."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

# Patch the Database class to avoid Supabase dependency
with patch("mailagent.core.database.Database.__init__", return_value=None):
    from mailagent.dashboard import app as dashboard
    from mailagent.dashboard.demo_auth import is_demo_allowlisted_route
    from mailagent.core.config import settings


class TestDemoModeSecurity:
    """Security tests to ensure demo mode doesn't expose real data."""

    @pytest.mark.asyncio
    async def test_demo_allowlisted_routes(self):
        """Test that only allowlisted routes are accessible without auth in demo mode."""
        with patch.object(settings, "public_demo_mode", True):
            # Allowlisted routes should return True
            assert is_demo_allowlisted_route("/") is True
            assert is_demo_allowlisted_route("/api/demo/status") is True
            assert is_demo_allowlisted_route("/api/demo/reset") is True

            # Non-allowlisted routes should return False
            assert is_demo_allowlisted_route("/api/accounts") is False
            assert is_demo_allowlisted_route("/api/emails") is False
            assert is_demo_allowlisted_route("/api/privacy") is False

    @pytest.mark.asyncio
    async def test_demo_mode_auth_dependency_fails_when_disabled(self):
        """Test that demo auth dependency fails when demo mode is disabled."""
        with patch.object(settings, "public_demo_mode", False):
            with patch.object(settings, "dashboard_api_token", "test-token"):
                with patch.object(settings, "dashboard_user_id", "test-user"):
                    with pytest.raises(HTTPException) as exc:
                        await dashboard.demo_mode_auth_dependency(
                            request=MagicMock(),
                            authorization=None,
                        )
                    assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_owner_auth_rejects_missing_dashboard_user_id(self):
        from mailagent.dashboard.auth import require_dashboard_auth

        with patch.object(settings, "dashboard_api_token", "configured-token"):
            with patch.object(settings, "dashboard_user_id", ""):
                with pytest.raises(HTTPException) as exc:
                    await require_dashboard_auth(authorization="Bearer configured-token")
                assert exc.value.status_code == 503
                assert exc.value.detail == "Dashboard authentication is not configured"

    @pytest.mark.asyncio
    async def test_owner_auth_accepts_configured_token_and_user_id(self):
        from mailagent.dashboard.auth import require_dashboard_auth

        with patch.object(settings, "dashboard_api_token", "configured-token"):
            with patch.object(settings, "dashboard_user_id", "demo-owner"):
                result = await require_dashboard_auth(
                    authorization="Bearer configured-token"
                )
                assert result == "demo-owner"

    @pytest.mark.asyncio
    async def test_owner_gmail_auth_url_returns_configuration_error_safely(self):
        with patch.object(settings, "demo_gmail_client_id", ""), \
             patch.object(settings, "google_client_id", ""), \
             patch.object(settings, "demo_gmail_client_secret", ""), \
             patch.object(settings, "google_client_secret", ""):
            with pytest.raises(HTTPException) as exc:
                await dashboard.get_owner_gmail_auth_url()
            assert exc.value.status_code == 400
            assert "Client ID" in exc.value.detail

    @pytest.mark.asyncio
    async def test_owner_gmail_auth_url_returns_authorization_url(self):
        with patch.object(settings, "demo_gmail_client_id", "client-id"), \
             patch.object(settings, "demo_gmail_client_secret", "client-secret"), \
             patch.object(settings, "demo_gmail_redirect_uri", "https://demo.invalid/callback"), \
             patch.object(dashboard.db, "create_oauth_state", AsyncMock()), \
             patch(
                 "mailagent.providers.gmail_provider.GmailOAuthFlow.get_authorization_url",
                 side_effect=lambda **kwargs: f"https://accounts.google.com/o/oauth2/auth?state={kwargs['state']}",
             ):
            result = await dashboard.get_owner_gmail_auth_url()
            assert result["auth_url"].startswith("https://accounts.google.com/")
            assert result["redirect_uri"] == "https://demo.invalid/callback"
            assert "state=" in result["auth_url"]
            assert "state" not in result

    @pytest.mark.asyncio
    async def test_browser_callback_rejects_missing_state(self):
        with patch.object(settings, "public_demo_mode", True), \
             patch.object(dashboard.db, "consume_oauth_state", AsyncMock(return_value=False)) as consume:
            response = await dashboard.receive_gmail_callback(code="code", state=None)
        assert response.status_code == 303
        assert "status=failed" in response.headers["location"]
        consume.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_browser_callback_exchanges_saves_and_syncs_without_exposing_code(self):
        from datetime import datetime, timezone
        tokens = {
            "token": "access-secret", "refresh_token": "refresh-secret",
            "client_id": "client", "client_secret": "client-secret",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        mock_provider = MagicMock()
        mock_provider.connect = AsyncMock(return_value=True)
        mock_provider.get_user_profile = AsyncMock(return_value={"emailAddress": "demo@gmail.com"})
        mock_sync = MagicMock()
        mock_sync.sync_mailbox = AsyncMock(return_value={"new": 2, "synced_at": datetime.now(timezone.utc).isoformat()})
        with patch.object(settings, "public_demo_mode", True), \
             patch.object(settings, "demo_gmail_client_id", "client"), \
             patch.object(settings, "demo_gmail_client_secret", "secret"), \
             patch.object(settings, "demo_gmail_redirect_uri", "https://demo.invalid/callback"), \
             patch.object(dashboard.db, "consume_oauth_state", AsyncMock(return_value=True)), \
             patch.object(dashboard.db, "save_account", AsyncMock()) as save_account, \
             patch("mailagent.providers.gmail_provider.GmailOAuthFlow.exchange_code_for_token", return_value=tokens) as exchange, \
             patch("mailagent.providers.gmail_provider.GmailProvider", return_value=mock_provider), \
             patch("mailagent.mail.sync_service.GmailSyncService", return_value=mock_sync):
            response = await dashboard.receive_gmail_callback(code="one-time-code", state="opaque-state")
        assert response.status_code == 303
        assert "status=success" in response.headers["location"]
        assert "one-time-code" not in response.headers["location"]
        assert "access-secret" not in response.headers["location"]
        assert "refresh-secret" not in response.headers["location"]
        assert exchange.call_args.kwargs["redirect_uri"] == "https://demo.invalid/callback"
        assert save_account.call_args.kwargs["account_id"] == dashboard.get_demo_account_id()
        mock_sync.sync_mailbox.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_browser_callback_rejects_replay(self):
        with patch.object(settings, "public_demo_mode", True), \
             patch.object(dashboard.db, "consume_oauth_state", AsyncMock(return_value=False)) as consume, \
             patch("mailagent.providers.gmail_provider.GmailOAuthFlow.exchange_code_for_token") as exchange:
            response = await dashboard.receive_gmail_callback(code="code", state="replayed")
        assert response.status_code == 303
        assert "status=failed" in response.headers["location"]
        consume.assert_awaited_once()
        exchange.assert_not_called()

    @pytest.mark.asyncio
    async def test_browser_callback_sanitizes_google_exchange_failure(self):
        with patch.object(settings, "public_demo_mode", True), \
             patch.object(settings, "demo_gmail_client_id", "client"), \
             patch.object(settings, "demo_gmail_client_secret", "secret"), \
             patch.object(settings, "demo_gmail_redirect_uri", "https://demo.invalid/callback"), \
             patch.object(dashboard.db, "consume_oauth_state", AsyncMock(return_value=True)), \
             patch("mailagent.providers.gmail_provider.GmailOAuthFlow.exchange_code_for_token", side_effect=RuntimeError("invalid_grant one-time-code")):
            response = await dashboard.receive_gmail_callback(code="one-time-code", state="state")
        assert response.status_code == 303
        assert "one-time-code" not in response.headers["location"]
        assert "invalid_grant" not in response.headers["location"]

    @pytest.mark.asyncio
    async def test_browser_callback_rejects_missing_refresh_token(self):
        with patch.object(settings, "public_demo_mode", True), \
             patch.object(settings, "demo_gmail_client_id", "client"), \
             patch.object(settings, "demo_gmail_client_secret", "secret"), \
             patch.object(settings, "demo_gmail_redirect_uri", "https://demo.invalid/callback"), \
             patch.object(dashboard.db, "consume_oauth_state", AsyncMock(return_value=True)), \
             patch("mailagent.providers.gmail_provider.GmailOAuthFlow.exchange_code_for_token", return_value={"token": "access"}), \
             patch("mailagent.providers.gmail_provider.GmailProvider") as provider:
            response = await dashboard.receive_gmail_callback(code="code", state="state")
        assert response.status_code == 303
        provider.assert_not_called()

    @pytest.mark.asyncio
    async def test_classified_emails_returns_demo_data(self):
        with patch.object(settings, "public_demo_mode", True), \
             patch.object(dashboard, "db", MagicMock()) as mock_db:
            mock_db.get_emails_with_classifications = AsyncMock(
                return_value={"emails": [], "total": 0}
            )
            result = await dashboard.get_emails_with_classifications(
                account_id="demo-account-001",
                limit=50,
                offset=0,
                min_priority=None,
                max_priority=None,
                sort_by="priority",
                request=MagicMock(),
                user_id="demo-user-judge",
            )
            assert result["emails"] == []
            assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_classified_emails_storage_failure_is_sanitized(self):
        with patch.object(settings, "public_demo_mode", True), \
             patch.object(dashboard, "db", MagicMock()) as mock_db:
            mock_db.get_emails_with_classifications = AsyncMock(
                side_effect=RuntimeError("database secret should not escape")
            )
            with pytest.raises(HTTPException) as exc:
                await dashboard.get_emails_with_classifications(
                    account_id="demo-account-001",
                    limit=50,
                    offset=0,
                    min_priority=None,
                    max_priority=None,
                    sort_by="priority",
                    request=MagicMock(),
                    user_id="demo-user-judge",
                )
            assert exc.value.status_code == 500
            assert exc.value.detail == "Unable to load classified emails"

    @pytest.mark.asyncio
    async def test_demo_mode_uses_separate_database(self):
        """Test that demo mode uses a separate SQLite database."""
        with patch.object(settings, "public_demo_mode", True):
            with patch.object(settings, "demo_sqlite_db_path", "mailagent-demo.db"):
                from mailagent.core.database import Database
                db = Database(force_demo_mode=True)
                assert db.storage is not None
                # The storage should use the demo database path
                assert db.storage.db_path == "mailagent-demo.db"

    @pytest.mark.asyncio
    async def test_normal_mode_uses_default_database(self):
        """Test that normal mode uses the default SQLite database."""
        with patch.object(settings, "public_demo_mode", False):
            with patch.object(settings, "sqlite_db_path", "mailagent.db"):
                from mailagent.core.database import Database
                db = Database()
                assert db.storage is not None
                # The storage should use the default database path
                assert db.storage.db_path == "mailagent.db"

    @pytest.mark.asyncio
    async def test_demo_data_isolation(self):
        """Test that demo data is isolated to demo user and account."""
        from mailagent.demo.demo_data import (
            get_demo_user_id,
            get_demo_account_id,
            get_demo_account_email,
        )

        demo_user_id = get_demo_user_id()
        demo_account_id = get_demo_account_id()
        demo_account_email = get_demo_account_email()

        # Demo IDs should be deterministic and not match typical production IDs
        assert demo_user_id == "demo-user-judge"
        assert demo_account_id == "demo-account-001"
        assert demo_account_email == "judge@example.com"

        # Demo account should not use real provider
        assert "demo" in demo_account_id.lower()

    @pytest.mark.asyncio
    async def test_demo_reset_endpoint_disabled_when_configured(self):
        """Test that demo reset endpoint can be disabled."""
        with patch.object(settings, "public_demo_mode", True):
            with patch.object(settings, "demo_reset_endpoint_enabled", False):
                with pytest.raises(HTTPException) as exc:
                    await dashboard.reset_demo_data(
                        request=MagicMock(),
                        user_id="demo-user",
                    )
                assert exc.value.status_code == 403
                assert "reset is disabled" in exc.value.detail

    @pytest.mark.asyncio
    async def test_demo_status_endpoint_includes_disclaimer(self):
        """Test that demo status endpoint returns demo configuration and mailbox status."""
        with patch.object(settings, "public_demo_mode", True):
            with patch.object(settings, "openrouter_api_key", ""):
                with patch.object(dashboard, "db", MagicMock()):
                    dashboard.db.get_emails_by_account = AsyncMock(return_value=[])
                    with patch.object(dashboard.demo_rate_limiter, "check_rate_limit", AsyncMock(return_value=(True, None))):
                        with patch.object(dashboard.demo_rate_limiter, "release_request", AsyncMock()):
                            response = await dashboard.get_demo_status(
                                request=MagicMock(),
                                user_id="demo-user",
                            )
                            assert response["demo_mode"] is True
                            assert "demo mailbox" in response["note"].lower()
                            assert "gmail_connected" in response

    @pytest.mark.asyncio
    async def test_demo_mode_rate_limiting(self):
        """Test that rate limiting is applied in demo mode."""
        from mailagent.dashboard.rate_limiter import demo_rate_limiter

        with patch.object(settings, "public_demo_mode", True):
            with patch.object(settings, "demo_rate_limit_per_minute", 2):
                with patch.object(settings, "demo_max_concurrent_requests", 5):
                    # First request should be allowed
                    allowed, _ = await demo_rate_limiter.check_rate_limit("127.0.0.1")
                    assert allowed is True
                    await demo_rate_limiter.release_request("127.0.0.1")

                    # Second request should be allowed
                    allowed, _ = await demo_rate_limiter.check_rate_limit("127.0.0.1")
                    assert allowed is True
                    await demo_rate_limiter.release_request("127.0.0.1")

                    # Third request should be rate limited (per-minute limit exceeded)
                    allowed, error = await demo_rate_limiter.check_rate_limit("127.0.0.1")
                    assert allowed is False
                    assert "Rate limit exceeded" in error

    @pytest.mark.asyncio
    async def test_different_clients_have_separate_rate_limits(self):
        """Test that rate limiting is per-client."""
        from mailagent.dashboard.rate_limiter import demo_rate_limiter

        with patch.object(settings, "public_demo_mode", True):
            with patch.object(settings, "demo_rate_limit_per_minute", 1):
                # Client 1 makes a request
                allowed1, _ = await demo_rate_limiter.check_rate_limit("192.168.1.1")
                assert allowed1 is True

                # Client 2 should still be allowed
                allowed2, _ = await demo_rate_limiter.check_rate_limit("192.168.1.2")
                assert allowed2 is True

                # Client 1 should be rate limited
                allowed1_second, _ = await demo_rate_limiter.check_rate_limit("192.168.1.1")
                assert allowed1_second is False
