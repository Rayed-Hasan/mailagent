from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


# Patch the Database class to avoid Supabase dependency
with patch("mailagent.core.database.Database.__init__", return_value=None):
    from mailagent.dashboard import app as dashboard


@pytest.mark.asyncio
async def test_account_owner_guard_hides_other_accounts(monkeypatch):
    monkeypatch.setattr(
        dashboard.db,
        "get_account",
        AsyncMock(return_value={"id": "account-1", "user_id": "owner-1"}),
    )

    with pytest.raises(HTTPException) as error:
        await dashboard.require_account_owner("account-1", "owner-2")

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_priority_endpoint_passes_filters_and_pagination_to_database(monkeypatch):
    get_priority = AsyncMock(
        return_value={
            "emails": [{"id": "email-1", "classification": {"priority_score": 95}}],
            "total": 11,
        }
    )
    monkeypatch.setattr(
        dashboard,
        "require_account_owner",
        AsyncMock(return_value={"id": "account-1", "user_id": "owner-1"}),
    )
    monkeypatch.setattr(dashboard.db, "get_emails_with_classifications", get_priority)

    response = await dashboard.get_emails_with_classifications(
        account_id="account-1",
        limit=5,
        offset=10,
        category="urgent",
        min_priority=70,
        max_priority=100,
        label="Important",
        needs_reply=True,
        sort_by="priority",
        user_id="owner-1",
    )

    assert response["total"] == 11
    assert response["offset"] == 10
    get_priority.assert_awaited_once_with(
        account_id="account-1",
        limit=5,
        offset=10,
        category="urgent",
        min_priority=70,
        max_priority=100,
        label="Important",
        needs_reply=True,
        sort_by="priority",
    )


@pytest.mark.asyncio
async def test_priority_endpoint_rejects_invalid_priority_range(monkeypatch):
    get_priority = AsyncMock()
    monkeypatch.setattr(
        dashboard,
        "require_account_owner",
        AsyncMock(return_value={"id": "account-1", "user_id": "owner-1"}),
    )
    monkeypatch.setattr(dashboard.db, "get_emails_with_classifications", get_priority)

    with pytest.raises(HTTPException) as error:
        await dashboard.get_emails_with_classifications(
            account_id="account-1",
            limit=50,
            offset=0,
            category=None,
            min_priority=90,
            max_priority=70,
            label=None,
            needs_reply=None,
            sort_by="priority",
            user_id="owner-1",
        )

    assert error.value.status_code == 422
    get_priority.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_classification_is_returned_as_unclassified(monkeypatch):
    get_priority = AsyncMock(
        return_value={"emails": [{"id": "email-1", "labels": []}], "total": 1}
    )
    monkeypatch.setattr(
        dashboard,
        "require_account_owner",
        AsyncMock(return_value={"id": "account-1", "user_id": "owner-1"}),
    )
    monkeypatch.setattr(dashboard.db, "get_emails_with_classifications", get_priority)

    response = await dashboard.get_emails_with_classifications(
        account_id="account-1",
        limit=50,
        offset=0,
        category=None,
        min_priority=None,
        max_priority=None,
        label=None,
        needs_reply=None,
        sort_by="priority",
        user_id="owner-1",
    )

    assert "classification" not in response["emails"][0]
    assert response["emails"][0]["labels"] == []
