import pytest
from fastapi import HTTPException

from mailagent.core.config import settings
from mailagent.dashboard.auth import require_dashboard_auth


@pytest.mark.asyncio
async def test_dashboard_auth_rejects_missing_configuration(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_api_token", "")
    monkeypatch.setattr(settings, "dashboard_user_id", "")
    with pytest.raises(HTTPException) as error:
        await require_dashboard_auth("Bearer token")
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_dashboard_auth_rejects_malformed_or_invalid_credentials(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_api_token", "expected")
    monkeypatch.setattr(settings, "dashboard_user_id", "user-1")
    for authorization in (None, "Basic expected", "Bearer wrong"):
        with pytest.raises(HTTPException) as error:
            await require_dashboard_auth(authorization)
        assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_auth_returns_configured_principal(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_api_token", "expected")
    monkeypatch.setattr(settings, "dashboard_user_id", "user-1")
    assert await require_dashboard_auth("Bearer expected") == "user-1"
