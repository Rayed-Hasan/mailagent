"""Focused tests for the personal Days 6-8 infrastructure."""

import sqlite3
from pathlib import Path

import pytest

from mailagent.core.keychain_storage import KeychainStorage
from mailagent.core.local_queue import LocalTaskQueue
from mailagent.core.secret_store import SecretStore
from mailagent.core.sqlite_storage import SQLiteStorage


@pytest.mark.asyncio
async def test_sqlite_persists_encrypted_credentials_and_isolates_users(tmp_path: Path):
    storage = SQLiteStorage(str(tmp_path / "mailagent.db"))
    storage.secret_store = SecretStore(key=b"0" * 32)
    await storage.initialize()

    account_id = await storage.save_account(
        "user-a", "imap", "a@example.com", {"password": "not-for-sqlite"}
    )
    await storage.save_provider_setting("user-a", "claude", "sk-user-a")
    await storage.save_provider_setting("user-b", "claude", "sk-user-b")

    account = await storage.get_account(account_id)
    assert account["credentials"]["password"] == "not-for-sqlite"
    setting = await storage.get_provider_setting("user-a", "claude")
    assert setting["api_key"] == "sk-user-a"
    assert await storage.get_provider_settings_by_user("user-b")
    raw = sqlite3.connect(tmp_path / "mailagent.db").execute(
        "SELECT credentials FROM email_accounts"
    ).fetchone()[0]
    assert "not-for-sqlite" not in raw
    exported = await storage.export_user_data("user-a")
    assert exported["accounts"][0]["email_address"] == "a@example.com"
    assert "credentials" not in exported["accounts"][0]
    counts = await storage.delete_user_data("user-a")
    assert counts["email_accounts"] == 1
    assert await storage.get_accounts_by_user("user-a") == []
    assert await storage.get_provider_setting("user-a", "claude") is None

    assert await storage.get_provider_settings_by_user("user-a") == []
    assert not await storage.get_provider_setting("user-a", "does-not-exist")
    await storage.close()


async def queue_probe():
    return "ran"


@pytest.mark.asyncio
async def test_local_queue_persists_and_cancels_jobs(tmp_path: Path):
    queue_db = str(tmp_path / "queue.db")
    first = LocalTaskQueue(queue_db)
    await first.start()
    assert first.schedule_task("probe", queue_probe, interval_seconds=60)
    await first.stop()

    second = LocalTaskQueue(queue_db)
    await second.start()
    assert "probe" in second.get_scheduled_tasks()
    assert second.cancel_task("probe")
    assert "probe" not in second.get_scheduled_tasks()
    await second.stop()


def test_local_queue_refuses_new_jobs_when_kill_switch_is_active(tmp_path: Path):
    queue = LocalTaskQueue(str(tmp_path / "queue.db"), kill_switch_checker=lambda: True)
    assert not queue.schedule_task("blocked", queue_probe, interval_seconds=60)


def test_keychain_scoping_and_secure_failure(monkeypatch):
    assert KeychainStorage.scoped_key("user-a", "oauth", "gmail") != (
        KeychainStorage.scoped_key("user-b", "oauth", "gmail")
    )
    monkeypatch.setattr(KeychainStorage, "get_credential", staticmethod(lambda _: None))
    monkeypatch.setattr(KeychainStorage, "set_credential", staticmethod(lambda *_: False))
    monkeypatch.delenv("MAILAGENT_ENCRYPTION_KEY", raising=False)
    with pytest.raises(ValueError, match="keychain is unavailable"):
        SecretStore()
