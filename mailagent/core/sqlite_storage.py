"""
SQLite storage backend for local-first deployments
"""

import json
import sqlite3
import aiosqlite
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path

from mailagent.core.storage_interface import StorageInterface
from mailagent.core.types import (
    EmailMessage, ClassificationResult, Draft, AuditLogEntry,
    UserVoiceProfile, RateLimitInfo, EmailCategory, EmailAction, DraftStatus
)
from mailagent.core.secret_store import SecretStore


class SQLiteStorage(StorageInterface):
    """SQLite storage backend for local deployments"""

    def __init__(self, db_path: str = "mailagent.db", secret_store: Optional[SecretStore] = None):
        self.db_path = db_path
        self.connection = None
        self.secret_store = secret_store or SecretStore()

    async def initialize(self) -> None:
        """Initialize SQLite database and create tables"""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await self._create_tables(db)
            await db.commit()

    async def close(self) -> None:
        """Close the storage connection"""
        if self.connection:
            await self.connection.close()
            self.connection = None

    async def _create_tables(self, db: aiosqlite.Connection):
        """Create all required tables"""

        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Email accounts table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS email_accounts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                email_address TEXT NOT NULL,
                credentials TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Emails table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                thread_id TEXT,
                sender TEXT NOT NULL,
                sender_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                received_at TEXT NOT NULL,
                raw_headers TEXT,
                FOREIGN KEY (account_id) REFERENCES email_accounts(id)
            )
        """)

        # Classifications table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS classifications (
                id TEXT PRIMARY KEY,
                email_id TEXT NOT NULL,
                category TEXT NOT NULL,
                priority_score INTEGER NOT NULL,
                action TEXT NOT NULL,
                confidence REAL NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            )
        """)

        # Drafts table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                email_id TEXT NOT NULL,
                classification_id TEXT,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                scheduled_send_at TEXT,
                sent_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails(id),
                FOREIGN KEY (classification_id) REFERENCES classifications(id)
            )
        """)

        # Audit log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                email_id TEXT NOT NULL,
                classification_id TEXT,
                draft_id TEXT,
                event_type TEXT NOT NULL,
                category TEXT,
                action TEXT,
                reason TEXT NOT NULL,
                confidence REAL,
                context TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (email_id) REFERENCES emails(id),
                FOREIGN KEY (classification_id) REFERENCES classifications(id),
                FOREIGN KEY (draft_id) REFERENCES drafts(id)
            )
        """)

        # User voice profile table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_voice_profile (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                tone TEXT,
                avg_length INTEGER,
                greeting_style TEXT,
                sign_off TEXT,
                common_phrases TEXT,
                last_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Rate limits table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                hour_window TEXT NOT NULL,
                auto_replies_sent INTEGER DEFAULT 0,
                last_reply_thread_id TEXT,
                FOREIGN KEY (account_id) REFERENCES email_accounts(id)
            )
        """)

        # Kill switch table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kill_switch (
                id TEXT PRIMARY KEY,
                is_active INTEGER NOT NULL DEFAULT 0,
                reason TEXT,
                activated_at TEXT,
                activated_by TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Provider settings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS provider_settings (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                api_key TEXT NOT NULL,
                model_classification TEXT,
                model_drafting TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, provider)
            )
        """)

        # Email labels table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS email_labels (
                id TEXT PRIMARY KEY,
                email_id TEXT NOT NULL,
                name TEXT NOT NULL,
                source TEXT DEFAULT 'system',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            )
        """)

        # Create indexes for performance
        await db.execute("CREATE INDEX IF NOT EXISTS idx_emails_account ON emails(account_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_emails_message ON emails(message_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_classifications_email ON classifications(email_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_drafts_email ON drafts(email_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_email ON audit_log(email_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_labels_email ON email_labels(email_id)")

    # Email operations
    async def save_email(self, email: EmailMessage, account_id: str) -> str:
        """Save an email to storage. Returns existing email ID if message_id already exists for this account."""
        import uuid

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            db.row_factory = aiosqlite.Row

            # Duplicate prevention check
            cursor = await db.execute(
                "SELECT id FROM emails WHERE account_id = ? AND message_id = ?",
                (account_id, email.message_id)
            )
            existing = await cursor.fetchone()
            if existing:
                return existing["id"]

            email_id = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO emails (id, account_id, message_id, thread_id, sender, sender_email,
                                    subject, body, received_at, raw_headers)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email_id, account_id, email.message_id, email.thread_id,
                email.sender, email.sender_email, email.subject, email.body,
                email.received_at.isoformat(), json.dumps(email.raw_headers)
            ))
            await db.commit()

        return email_id

    async def get_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get an email by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None

    async def get_email_by_message_id(self, account_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Get an email by account and provider message ID for deduplication"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM emails WHERE account_id = ? AND message_id = ?",
                (account_id, message_id)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None

    async def get_account_for_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get the owning account for an email"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT ea.* FROM email_accounts ea
                JOIN emails e ON e.account_id = ea.id
                WHERE e.id = ?
            """, (email_id,))
            row = await cursor.fetchone()
            if row:
                account = dict(row)
                # Decrypt credentials
                if account.get('credentials'):
                    associated_data = f"email-account:{account['user_id']}:{account['provider']}:{account['email_address']}"
                    try:
                        credentials_json = self.secret_store.decrypt(account['credentials'], associated_data)
                        account['credentials'] = json.loads(credentials_json)
                    except (ValueError, json.JSONDecodeError) as exc:
                        raise RuntimeError("account credentials cannot be decrypted") from exc
                return account
        return None

    async def get_emails_by_account(
        self, account_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get emails for an account with pagination"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM emails
                WHERE account_id = ?
                ORDER BY received_at DESC
                LIMIT ? OFFSET ?
            """, (account_id, limit, offset))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_emails_with_classifications(
        self,
        account_id: str,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        min_priority: Optional[int] = None,
        max_priority: Optional[int] = None,
        label: Optional[str] = None,
        needs_reply: Optional[bool] = None,
        sort_by: str = "priority",
    ) -> Dict[str, Any]:
        """Get a priority inbox with persisted enrichment"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Build query
            query = """
                SELECT e.*,
                       c.id as classification_id, c.category, c.priority_score,
                       c.action, c.confidence, c.reason as classification_reason
                FROM emails e
                LEFT JOIN classifications c ON e.id = c.email_id
                WHERE e.account_id = ?
            """
            params = [account_id]

            if category:
                query += " AND c.category = ?"
                params.append(category)
            if min_priority is not None:
                query += " AND c.priority_score >= ?"
                params.append(min_priority)
            if max_priority is not None:
                query += " AND c.priority_score <= ?"
                params.append(max_priority)
            if label:
                query += " AND EXISTS (SELECT 1 FROM email_labels el WHERE el.email_id = e.id AND el.name = ?)"
                params.append(label)
            if needs_reply is True:
                query += " AND c.action IN ('reply', 'draft_only')"
            elif needs_reply is False:
                query += " AND (c.action NOT IN ('reply', 'draft_only') OR c.action IS NULL)"

            # Count total
            count_query = "SELECT COUNT(*) as count FROM emails" + query.split(
                "FROM emails", 1
            )[1]
            cursor = await db.execute(count_query, params)
            total_row = await cursor.fetchone()
            total = total_row['count'] if total_row else 0

            # Sort
            if sort_by == "priority":
                query += " ORDER BY c.priority_score DESC NULLS LAST"
            query += ", e.received_at DESC, e.id DESC"

            # Paginate
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            emails = []
            for row in rows:
                email = dict(row)
                # Extract classification
                if email.get('classification_id'):
                    email['classification'] = {
                        'id': email['classification_id'],
                        'category': email['category'],
                        'priority_score': email['priority_score'],
                        'action': email['action'],
                        'confidence': email['confidence'],
                        'reason': email['classification_reason']
                    }
                    # Remove classification fields from email
                    for key in ['classification_id', 'category', 'priority_score', 'action', 'confidence', 'classification_reason']:
                        email.pop(key, None)

                # Get labels
                cursor2 = await db.execute("SELECT name FROM email_labels WHERE email_id = ?", (email['id'],))
                label_rows = await cursor2.fetchall()
                email['labels'] = [row['name'] for row in label_rows]

                emails.append(email)

            return {"emails": emails, "total": total}

    # Classification operations
    async def save_classification(self, classification: ClassificationResult) -> str:
        """Save a classification result"""
        import uuid
        classification_id = str(uuid.uuid4())

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO classifications (id, email_id, category, priority_score, action, confidence, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                classification_id, classification.email_id, classification.category.value,
                classification.priority_score, classification.action.value,
                classification.confidence, classification.reason
            ))
            await db.commit()

        return classification_id

    async def get_classification(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get classification for an email"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM classifications WHERE email_id = ?", (email_id,))
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None

    # Draft operations
    async def save_draft(self, draft: Draft) -> str:
        """Save a draft"""
        import uuid
        draft_id = str(uuid.uuid4())

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO drafts (id, email_id, classification_id, content, status, scheduled_send_at, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                draft_id, draft.email_id, draft.classification_id, draft.content,
                draft.status.value,
                draft.scheduled_send_at.isoformat() if draft.scheduled_send_at else None,
                draft.sent_at.isoformat() if draft.sent_at else None
            ))
            await db.commit()

        return draft_id

    async def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """Get a draft by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None

    async def update_draft_status(self, draft_id: str, status: DraftStatus) -> bool:
        """Update draft status"""
        async with aiosqlite.connect(self.db_path) as db:
            data = {
                "status": status.value,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            if status == DraftStatus.SENT:
                data["sent_at"] = datetime.now(timezone.utc).isoformat()

            await db.execute("""
                UPDATE drafts SET status = ?, updated_at = ?, sent_at = COALESCE(?, sent_at)
                WHERE id = ?
            """, (data["status"], data["updated_at"], data.get("sent_at"), draft_id))
            await db.commit()

            return True

    async def get_pending_drafts(self, account_id: str) -> List[Dict[str, Any]]:
        """Get pending drafts for an account"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT d.* FROM drafts d
                JOIN emails e ON d.email_id = e.id
                WHERE d.status = 'pending' AND e.account_id = ?
            """, (account_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Audit log operations
    async def log_audit(self, entry: AuditLogEntry) -> str:
        """Log an audit entry"""
        import uuid
        log_id = str(uuid.uuid4())

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO audit_log (id, email_id, classification_id, draft_id, event_type,
                                      category, action, reason, confidence, context, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id, entry.email_id, entry.classification_id, entry.draft_id,
                entry.event_type,
                entry.category.value if entry.category else None,
                entry.action.value if entry.action else None,
                entry.reason, entry.confidence,
                json.dumps(entry.context) if entry.context else None,
                entry.timestamp.isoformat()
            ))
            await db.commit()

        return log_id

    async def get_audit_log(self, email_id: str) -> List[Dict[str, Any]]:
        """Get audit log for an email"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM audit_log WHERE email_id = ? ORDER BY timestamp DESC
            """, (email_id,))
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                entry = dict(row)
                if entry.get('context'):
                    entry['context'] = json.loads(entry['context'])
                result.append(entry)
            return result

    # User voice profile operations
    async def save_voice_profile(self, user_id: str, profile: UserVoiceProfile) -> str:
        """Save user voice profile"""
        import uuid
        profile_id = str(uuid.uuid4())

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
            await db.execute("""
                INSERT OR REPLACE INTO user_voice_profile
                (id, user_id, tone, avg_length, greeting_style, sign_off, common_phrases, last_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_id, user_id, profile.tone, profile.avg_length,
                profile.greeting_style, profile.sign_off,
                json.dumps(profile.common_phrases) if profile.common_phrases else None,
                datetime.now(timezone.utc).isoformat()
            ))
            await db.commit()

        return profile_id

    async def get_voice_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user voice profile"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM user_voice_profile WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                profile = dict(row)
                if profile.get('common_phrases'):
                    profile['common_phrases'] = json.loads(profile['common_phrases'])
                return profile
        return None

    # Rate limit operations
    async def save_rate_limit(self, account_id: str, info: RateLimitInfo) -> str:
        """Save rate limit info"""
        import uuid
        rate_limit_id = str(uuid.uuid4())
        hour_window = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO rate_limits
                (id, account_id, hour_window, auto_replies_sent, last_reply_thread_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                rate_limit_id, account_id, hour_window,
                info.auto_replies_sent_this_hour, info.last_reply_thread_id
            ))
            await db.commit()

        return rate_limit_id

    async def get_rate_limit(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get current rate limit info"""
        current_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM rate_limits
                WHERE account_id = ? AND hour_window = ?
            """, (account_id, current_hour))
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None

    # Kill switch operations
    async def is_kill_switch_active(self) -> bool:
        """Check if kill switch is active"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT is_active FROM kill_switch ORDER BY updated_at DESC LIMIT 1
            """)
            row = await cursor.fetchone()
            if row:
                return bool(row['is_active'])
        return False

    async def activate_kill_switch(self, reason: str, activated_by: str) -> bool:
        """Activate kill switch and cancel all pending drafts"""
        import uuid
        kill_switch_id = str(uuid.uuid4())

        async with aiosqlite.connect(self.db_path) as db:
            # Activate kill switch
            await db.execute("""
                INSERT INTO kill_switch (id, is_active, reason, activated_at, activated_by, updated_at)
                VALUES (?, 1, ?, ?, ?, ?)
            """, (
                kill_switch_id, reason,
                datetime.now(timezone.utc).isoformat(), activated_by,
                datetime.now(timezone.utc).isoformat()
            ))

            # Cancel all pending drafts
            await db.execute("""
                UPDATE drafts SET status = 'cancelled', updated_at = ?
                WHERE status = 'pending'
            """, (datetime.now(timezone.utc).isoformat(),))

            await db.commit()

        return True

    async def deactivate_kill_switch(self) -> bool:
        """Deactivate kill switch"""
        import uuid
        kill_switch_id = str(uuid.uuid4())

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO kill_switch (id, is_active, updated_at)
                VALUES (?, 0, ?)
            """, (kill_switch_id, datetime.now(timezone.utc).isoformat()))
            await db.commit()

        return True

    # Account operations
    async def save_account(self, user_id: str, provider: str, email_address: str, credentials: Dict[str, Any]) -> str:
        """Save an email account with encrypted credentials"""
        import uuid
        account_id = str(uuid.uuid4())

        # Encrypt credentials
        associated_data = f"email-account:{user_id}:{provider}:{email_address}"
        encrypted_credentials = {
            "version": 1,
            "ciphertext": self.secret_store.encrypt(
                json.dumps(credentials, separators=(",", ":")),
                associated_data,
            ),
        }

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
            await db.execute("""
                INSERT INTO email_accounts (id, user_id, provider, email_address, credentials)
                VALUES (?, ?, ?, ?, ?)
            """, (
                account_id, user_id, provider, email_address,
                json.dumps(encrypted_credentials)
            ))
            await db.commit()

        return account_id

    async def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get an account by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM email_accounts WHERE id = ?", (account_id,))
            row = await cursor.fetchone()
            if row:
                account = dict(row)
                # Decrypt credentials
                stored = json.loads(account['credentials'])
                if isinstance(stored, dict) and stored.get('version') == 1:
                    associated_data = f"email-account:{account['user_id']}:{account['provider']}:{account['email_address']}"
                    try:
                        plaintext = self.secret_store.decrypt(stored['ciphertext'], associated_data)
                        account['credentials'] = json.loads(plaintext)
                    except (ValueError, json.JSONDecodeError) as exc:
                        raise RuntimeError("account credentials cannot be decrypted") from exc
                return account
        return None

    async def get_accounts_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all accounts for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM email_accounts WHERE user_id = ? AND is_active = 1
            """, (user_id,))
            rows = await cursor.fetchall()
            accounts = []
            for row in rows:
                account = dict(row)
                # Decrypt credentials
                stored = json.loads(account['credentials'])
                if isinstance(stored, dict) and stored.get('version') == 1:
                    associated_data = f"email-account:{account['user_id']}:{account['provider']}:{account['email_address']}"
                    try:
                        plaintext = self.secret_store.decrypt(stored['ciphertext'], associated_data)
                        account['credentials'] = json.loads(plaintext)
                    except (ValueError, json.JSONDecodeError) as exc:
                        raise RuntimeError("account credentials cannot be decrypted") from exc
                accounts.append(account)
            return accounts

    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export user-owned records without encrypted credential fields."""
        accounts = await self.get_accounts_by_user(user_id)
        exported_accounts = [
            {key: value for key, value in account.items() if key != "credentials"}
            for account in accounts
        ]
        emails = []
        for account in accounts:
            emails.extend(await self.get_emails_by_account(account["id"], limit=100000))
        return {"user_id": user_id, "accounts": exported_accounts, "emails": emails}

    async def delete_user_data(self, user_id: str) -> Dict[str, int]:
        """Delete all records owned by a user in one SQLite transaction."""
        counts: Dict[str, int] = {}
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            account_rows = await db.execute_fetchall(
                "SELECT id FROM email_accounts WHERE user_id = ?", (user_id,)
            )
            account_ids = [row[0] for row in account_rows]
            email_ids = []
            if account_ids:
                placeholders = ",".join("?" for _ in account_ids)
                email_rows = await db.execute_fetchall(
                    f"SELECT id FROM emails WHERE account_id IN ({placeholders})",
                    account_ids,
                )
                email_ids = [row[0] for row in email_rows]

            for table, column, values in (
                ("email_labels", "email_id", email_ids),
                ("audit_log", "email_id", email_ids),
                ("drafts", "email_id", email_ids),
                ("classifications", "email_id", email_ids),
                ("emails", "account_id", account_ids),
                ("rate_limits", "account_id", account_ids),
                ("email_accounts", "user_id", [user_id]),
                ("provider_settings", "user_id", [user_id]),
                ("user_voice_profile", "user_id", [user_id]),
                ("users", "id", [user_id]),
            ):
                if not values:
                    counts[table] = 0
                    continue
                placeholders = ",".join("?" for _ in values)
                cursor = await db.execute(
                    f"DELETE FROM {table} WHERE {column} IN ({placeholders})",
                    values,
                )
                counts[table] = cursor.rowcount
            await db.commit()
        return counts

    # Provider settings operations
    async def save_provider_setting(
        self,
        user_id: str,
        provider: str,
        api_key: str,
        model_classification: str = "",
        model_drafting: str = "",
    ) -> str:
        """Save or update a provider setting with encrypted API key"""
        import uuid
        setting_id = str(uuid.uuid4())

        # Encrypt API key
        associated_data = f"provider-setting:{user_id}:{provider}"
        encrypted_key = {
            "version": 1,
            "ciphertext": self.secret_store.encrypt(api_key, associated_data),
        }

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
            await db.execute("""
                INSERT OR REPLACE INTO provider_settings
                (id, user_id, provider, api_key, model_classification, model_drafting, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                setting_id, user_id, provider, json.dumps(encrypted_key),
                model_classification, model_drafting, datetime.now(timezone.utc).isoformat()
            ))
            await db.commit()

        return setting_id

    async def get_provider_setting(self, user_id: str, provider: str) -> Optional[Dict[str, Any]]:
        """Get a provider setting for a user with decrypted API key"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM provider_settings WHERE user_id = ? AND provider = ?
            """, (user_id, provider))
            row = await cursor.fetchone()
            if row:
                setting = dict(row)
                # Decrypt API key
                stored = json.loads(setting['api_key'])
                if isinstance(stored, dict) and stored.get('version') == 1:
                    associated_data = f"provider-setting:{user_id}:{provider}"
                    try:
                        plaintext = self.secret_store.decrypt(stored['ciphertext'], associated_data)
                        setting['api_key'] = plaintext
                    except (ValueError, json.JSONDecodeError) as exc:
                        raise RuntimeError("provider API key cannot be decrypted") from exc
                return setting
        return None

    async def get_provider_settings_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all provider settings for a user with decrypted API keys"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM provider_settings WHERE user_id = ?
            """, (user_id,))
            rows = await cursor.fetchall()
            settings = []
            for row in rows:
                setting = dict(row)
                # Decrypt API key
                stored = json.loads(setting['api_key'])
                if isinstance(stored, dict) and stored.get('version') == 1:
                    associated_data = f"provider-setting:{user_id}:{setting['provider']}"
                    try:
                        plaintext = self.secret_store.decrypt(stored['ciphertext'], associated_data)
                        setting['api_key'] = plaintext
                    except (ValueError, json.JSONDecodeError) as exc:
                        raise RuntimeError("provider API key cannot be decrypted") from exc
                settings.append(setting)
            return settings

    async def delete_provider_setting(self, user_id: str, provider: str) -> bool:
        """Delete a provider setting for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM provider_settings WHERE user_id = ? AND provider = ?
            """, (user_id, provider))
            await db.commit()
            return cursor.rowcount > 0

    # Email label operations
    async def save_email_labels(self, email_id: str, labels: List[str], source: str = "system") -> bool:
        """Save labels for an email with deduplication"""
        if not labels:
            return True

        async with aiosqlite.connect(self.db_path) as db:
            # Get existing labels
            cursor = await db.execute("SELECT name FROM email_labels WHERE email_id = ?", (email_id,))
            existing_rows = await cursor.fetchall()
            existing_names = {row[0] for row in existing_rows}

            # Add only new labels
            import uuid
            for label in labels:
                if label not in existing_names:
                    label_id = str(uuid.uuid4())
                    await db.execute("""
                        INSERT INTO email_labels (id, email_id, name, source)
                        VALUES (?, ?, ?, ?)
                    """, (label_id, email_id, label, source))

            await db.commit()
            return True

    async def get_email_labels(self, email_id: str) -> List[Dict[str, Any]]:
        """Get all labels for an email"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM email_labels WHERE email_id = ?", (email_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_email_label(self, email_id: str, label_name: str) -> bool:
        """Delete a specific label from an email"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM email_labels WHERE email_id = ? AND name = ?",
                (email_id, label_name),
            )
            await db.commit()
            return cursor.rowcount > 0
