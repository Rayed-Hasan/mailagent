"""Demo data seeder for public demo mode."""

import json
import uuid
import aiosqlite
from datetime import datetime, timezone
from typing import Dict, Any

from mailagent.core.types import (
    EmailMessage,
    ClassificationResult,
    DraftStatus,
)
from mailagent.demo.demo_data import (
    get_demo_emails,
    get_demo_user_id,
    get_demo_account_id,
    get_demo_account_email,
)


class DemoSeeder:
    """Seeds the database with synthetic demo data."""

    def __init__(self, db):
        self.db = db
        self.demo_user_id = get_demo_user_id()
        self.demo_account_id = get_demo_account_id()
        self.demo_account_email = get_demo_account_email()

    async def seed_demo_data(self) -> Dict[str, int]:
        """Seed the database with demo emails, classifications, and labels.

        Returns:
            Dictionary with counts of seeded records.
        """
        counts = {"emails": 0, "classifications": 0, "labels": 0, "drafts": 0}

        # Create demo user
        await self._ensure_demo_user()

        # Create demo account
        await self._ensure_demo_account()

        # Seed emails with classifications and labels
        demo_emails = get_demo_emails()
        for email_data in demo_emails:
            email_id = await self._seed_email(email_data)
            counts["emails"] += 1

            classification_id = await self._seed_classification(email_id, email_data)
            counts["classifications"] += 1

            await self._seed_labels(email_id, email_data.get("labels", []))
            counts["labels"] += len(email_data.get("labels", []))

        return counts

    async def reset_demo_data(self) -> Dict[str, int]:
        """Reset demo data by deleting and re-seeding.

        Returns:
            Dictionary with counts of seeded records.
        """
        # Delete existing demo data
        await self._clear_demo_data()

        # Re-seed
        return await self.seed_demo_data()

    async def _ensure_demo_user(self) -> None:
        """Ensure the demo user exists."""
        if self.db.storage:
            db_path = self.db.storage.db_path
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO users (id, created_at) VALUES (?, ?)",
                    (self.demo_user_id, datetime.now(timezone.utc).isoformat()),
                )
                await db.commit()

    async def _ensure_demo_account(self) -> None:
        """Ensure the demo account exists."""
        # For demo mode, we create a minimal account without real credentials
        fake_credentials = json.dumps({"demo": True, "credentials": None})

        if self.db.storage:
            db_path = self.db.storage.db_path
            encrypted = self.db.storage.secret_store.encrypt(
                str(fake_credentials),
                f"email-account:{self.demo_user_id}:demo:{self.demo_account_email}",
            )

            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    """INSERT OR IGNORE INTO email_accounts
                    (id, user_id, provider, email_address, credentials, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        self.demo_account_id,
                        self.demo_user_id,
                        "demo",
                        self.demo_account_email,
                        encrypted,
                        1,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                await db.commit()

    async def _seed_email(self, email_data: Dict[str, Any]) -> str:
        """Seed a single email."""
        email_id = str(uuid.uuid4())

        email = EmailMessage(
            message_id=email_data["message_id"],
            thread_id=email_data["thread_id"],
            sender=email_data["sender"],
            sender_email=email_data["sender_email"],
            subject=email_data["subject"],
            body=email_data["body"],
            received_at=email_data["received_at"],
            raw_headers={},
        )

        return await self.db.save_email(email, self.demo_account_id)

    async def _seed_classification(self, email_id: str, email_data: Dict[str, Any]) -> str:
        """Seed a classification for an email."""
        classification = ClassificationResult(
            email_id=email_id,
            category=email_data["category"],
            priority_score=email_data["priority_score"],
            action=email_data["action"],
            confidence=email_data["confidence"],
            reason=email_data["reason"],
        )

        return await self.db.save_classification(classification)

    async def _seed_labels(self, email_id: str, labels: list) -> None:
        """Seed labels for an email."""
        if labels:
            await self.db.save_email_labels(email_id, labels, source="system")

    async def _clear_demo_data(self) -> None:
        """Clear all demo data from the database."""
        if self.db.storage:
            db_path = self.db.storage.db_path
            async with aiosqlite.connect(db_path) as db:
                await db.execute("PRAGMA foreign_keys = ON")

                # Delete in order respecting foreign keys
                await db.execute("DELETE FROM email_labels WHERE email_id IN (SELECT id FROM emails WHERE account_id = ?)", (self.demo_account_id,))
                await db.execute("DELETE FROM audit_log WHERE email_id IN (SELECT id FROM emails WHERE account_id = ?)", (self.demo_account_id,))
                await db.execute("DELETE FROM drafts WHERE email_id IN (SELECT id FROM emails WHERE account_id = ?)", (self.demo_account_id,))
                await db.execute("DELETE FROM classifications WHERE email_id IN (SELECT id FROM emails WHERE account_id = ?)", (self.demo_account_id,))
                await db.execute("DELETE FROM emails WHERE account_id = ?", (self.demo_account_id,))
                await db.execute("DELETE FROM rate_limits WHERE account_id = ?", (self.demo_account_id,))
                await db.execute("DELETE FROM email_accounts WHERE id = ?", (self.demo_account_id,))
                await db.execute("DELETE FROM user_voice_profile WHERE user_id = ?", (self.demo_user_id,))
                await db.execute("DELETE FROM provider_settings WHERE user_id = ?", (self.demo_user_id,))
                await db.execute("DELETE FROM users WHERE id = ?", (self.demo_user_id,))

                await db.commit()
