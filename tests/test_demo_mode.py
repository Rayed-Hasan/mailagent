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
        """Test that demo status endpoint includes clear disclaimer."""
        with patch.object(settings, "public_demo_mode", True):
            with patch.object(settings, "openrouter_api_key", ""):
                with patch.object(dashboard, "db", MagicMock()):
                    with patch.object(dashboard.demo_rate_limiter, "check_rate_limit", AsyncMock(return_value=(True, None))):
                        with patch.object(dashboard.demo_rate_limiter, "release_request", AsyncMock()):
                            response = await dashboard.get_demo_status(
                                request=MagicMock(),
                                user_id="demo-user",
                            )
                            assert response["demo_mode"] is True
                            assert "synthetic data" in response["note"]
                            assert "real emails are sent" in response["note"].lower()

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
