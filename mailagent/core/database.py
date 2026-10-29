"""
Database layer with storage abstraction
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from mailagent.core.config import settings
from mailagent.core.secret_store import SecretStore
from mailagent.core.types import (
    EmailMessage, ClassificationResult, Draft, AuditLogEntry,
    UserVoiceProfile, RateLimitInfo, EmailCategory, EmailAction, DraftStatus
)


class Database:
    """Database operations with pluggable storage backend"""

    def __init__(self, storage_backend: str = None, force_demo_mode: bool = False):
        """
        Initialize database with specified storage backend.

        Args:
            storage_backend: 'supabase' (default) or 'sqlite'
            force_demo_mode: If True, use demo-specific database path
        """
        self.storage_backend = storage_backend or settings.storage_backend
        self.storage = None
        self.client = None
        self.force_demo_mode = force_demo_mode

        if force_demo_mode or settings.public_demo_mode:
            self.storage_backend = "sqlite"

        if self.storage_backend == 'sqlite':
            from mailagent.core.sqlite_storage import SQLiteStorage
            # Use demo database if in demo mode or forced
            if force_demo_mode or settings.public_demo_mode:
                db_path = getattr(settings, 'demo_sqlite_db_path', 'mailagent-demo.db')
                self.storage = SQLiteStorage(
                    db_path,
                    secret_store=SecretStore(),
                )
            else:
                db_path = getattr(settings, 'sqlite_db_path', 'mailagent.db')
                self.storage = SQLiteStorage(db_path)
        elif self.storage_backend == "supabase":
            from supabase import create_client, Client
            self.client: Client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
        else:
            raise ValueError(f"Unsupported storage backend: {self.storage_backend}")

    async def initialize(self):
        """Initialize the storage backend"""
        if self.storage:
            await self.storage.initialize()

    async def close(self):
        """Close the storage connection"""
        if self.storage:
            await self.storage.close()

    # Email operations
    async def save_email(self, email: EmailMessage, account_id: str) -> str:
        """Save an email to the database"""
        if self.storage:
            return await self.storage.save_email(email, account_id)

        data = {
            "account_id": account_id,
            "message_id": email.message_id,
            "thread_id": email.thread_id,
            "sender": email.sender,
            "sender_email": email.sender_email,
            "subject": email.subject,
            "body": email.body,
            "received_at": email.received_at.isoformat(),
            "raw_headers": email.raw_headers
        }

        result = self.client.table("emails").insert(data).execute()
        return result.data[0]["id"]

    async def get_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get an email by ID"""
        if self.storage:
            return await self.storage.get_email(email_id)

        result = self.client.table("emails").select("*").eq("id", email_id).execute()
        return result.data[0] if result.data else None

    async def get_email_by_message_id(self, account_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Get an email by account and provider message ID"""
        if self.storage:
            return await self.storage.get_email_by_message_id(account_id, message_id)

        result = self.client.table("emails").select("*").eq("account_id", account_id).eq("message_id", message_id).execute()
        return result.data[0] if result.data else None

    async def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """Get a draft by ID"""
        if self.storage:
            return await self.storage.get_draft(draft_id)

        result = self.client.table("drafts").select("*").eq("id", draft_id).execute()
        return result.data[0] if result.data else None

    async def get_account_for_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get the owning account for an email"""
        if self.storage:
            return await self.storage.get_account_for_email(email_id)

        result = (
            self.client.table("emails")
            .select("email_accounts(*)")
            .eq("id", email_id)
            .execute()
        )
        if not result.data or not result.data[0].get("email_accounts"):
            return None
        return result.data[0]["email_accounts"]

    async def get_emails_by_account(
        self, account_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get emails for an account with pagination."""
        if self.storage:
            return await self.storage.get_emails_by_account(account_id, limit, offset)

        result = (
            self.client.table("emails")
            .select("*")
            .eq("account_id", account_id)
            .order("received_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data

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
        """Get a stable, paginated priority inbox with persisted enrichment."""
        if self.storage:
            return await self.storage.get_emails_with_classifications(
                account_id, limit, offset, category, min_priority, max_priority,
                label, needs_reply, sort_by
            )

        classification_join = "classifications!inner(*)" if (
            category or min_priority is not None or max_priority is not None or needs_reply is True
        ) else "classifications(*)"
        labels_join = "email_labels!inner(*)" if label else "email_labels(*)"
        query = self.client.table("emails").select(
            f"*, {classification_join}, {labels_join}",
            count="exact",
        ).eq("account_id", account_id)

        if category:
            query = query.eq("classifications.category", category)
        if min_priority is not None:
            query = query.gte("classifications.priority_score", min_priority)
        if max_priority is not None:
            query = query.lte("classifications.priority_score", max_priority)
        if label:
            query = query.eq("email_labels.name", label)
        if needs_reply is True:
            query = query.in_("classifications.action", ["reply", "draft_only"])
        elif needs_reply is False:
            query = query.or_(
                "action.not.in.(reply,draft_only),action.is.null",
                reference_table="classifications",
            )

        if sort_by == "priority":
            query = query.order(
                "priority_score",
                foreign_table="classifications",
                desc=True,
                nullsfirst=False,
            )
        query = (
            query.order("received_at", desc=True)
            .order("id", desc=True)
            .range(offset, offset + limit - 1)
        )
        result = query.execute()

        emails = []
        for email in result.data:
            classification = email.pop("classifications", None)
            if isinstance(classification, list):
                classification = classification[0] if classification else None
            if classification:
                email["classification"] = classification
            labels = email.pop("email_labels", []) or []
            email["labels"] = [
                item["name"] for item in labels if isinstance(item, dict) and item.get("name")
            ]
            emails.append(email)

        return {"emails": emails, "total": result.count if result.count is not None else len(emails)}

    # Classification operations
    async def save_classification(self, classification: ClassificationResult) -> str:
        """Save a classification result"""
        if self.storage:
            return await self.storage.save_classification(classification)

        data = {
            "email_id": classification.email_id,
            "category": classification.category.value,
            "priority_score": classification.priority_score,
            "action": classification.action.value,
            "confidence": classification.confidence,
            "reason": classification.reason
        }

        result = self.client.table("classifications").insert(data).execute()
        return result.data[0]["id"]

    async def get_classification(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get classification for an email"""
        if self.storage:
            return await self.storage.get_classification(email_id)

        result = self.client.table("classifications").select("*").eq("email_id", email_id).execute()
        return result.data[0] if result.data else None

    # Draft operations
    async def save_draft(self, draft: Draft) -> str:
        """Save a draft"""
        if self.storage:
            return await self.storage.save_draft(draft)

        data = {
            "email_id": draft.email_id,
            "classification_id": draft.classification_id,
            "content": draft.content,
            "status": draft.status.value,
            "scheduled_send_at": draft.scheduled_send_at.isoformat() if draft.scheduled_send_at else None,
            "sent_at": draft.sent_at.isoformat() if draft.sent_at else None
        }

        result = self.client.table("drafts").insert(data).execute()
        return result.data[0]["id"]

    async def update_draft_status(self, draft_id: str, status: DraftStatus) -> bool:
        """Update draft status"""
        if self.storage:
            return await self.storage.update_draft_status(draft_id, status)

        data = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat()
        }

        if status == DraftStatus.SENT:
            data["sent_at"] = datetime.utcnow().isoformat()

        result = self.client.table("drafts").update(data).eq("id", draft_id).execute()
        return len(result.data) > 0

    async def get_pending_drafts(self, account_id: str) -> List[Dict[str, Any]]:
        """Get pending drafts for an account"""
        if self.storage:
            return await self.storage.get_pending_drafts(account_id)

        result = (
            self.client.table("drafts")
            .select("*, emails!inner(account_id)")
            .eq("status", "pending")
            .eq("emails.account_id", account_id)
            .execute()
        )
        return [
            {key: value for key, value in draft.items() if key != "emails"}
            for draft in result.data
        ]

    # Audit log operations
    async def log_audit(self, entry: AuditLogEntry) -> str:
        """Log an audit entry"""
        if isinstance(entry, dict):
            entry = AuditLogEntry.model_validate(entry)
        if self.storage:
            return await self.storage.log_audit(entry)

        data = {
            "email_id": entry.email_id,
            "classification_id": entry.classification_id,
            "draft_id": entry.draft_id,
            "event_type": entry.event_type,
            "category": entry.category.value if entry.category else None,
            "action": entry.action.value if entry.action else None,
            "reason": entry.reason,
            "confidence": entry.confidence,
            "context": entry.context,
            "timestamp": entry.timestamp.isoformat()
        }

        result = self.client.table("audit_log").insert(data).execute()
        return result.data[0]["id"]

    async def get_audit_log(self, email_id: str) -> List[Dict[str, Any]]:
        """Get audit log for an email"""
        if self.storage:
            return await self.storage.get_audit_log(email_id)

        result = self.client.table("audit_log").select("*").eq("email_id", email_id).order("timestamp", desc=True).execute()
        return result.data

    # User voice profile operations
    async def save_voice_profile(self, user_id: str, profile: UserVoiceProfile) -> str:
        """Save user voice profile"""
        if self.storage:
            return await self.storage.save_voice_profile(user_id, profile)

        data = {
            "user_id": user_id,
            "tone": profile.tone,
            "avg_length": profile.avg_length,
            "greeting_style": profile.greeting_style,
            "sign_off": profile.sign_off,
            "common_phrases": profile.common_phrases,
            "last_updated_at": datetime.utcnow().isoformat()
        }

        # Upsert
        result = self.client.table("user_voice_profile").upsert(data).execute()
        return result.data[0]["id"]

    async def get_voice_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user voice profile"""
        if self.storage:
            return await self.storage.get_voice_profile(user_id)

        result = self.client.table("user_voice_profile").select("*").eq("user_id", user_id).execute()
        return result.data[0] if result.data else None

    # Rate limit operations
    async def save_rate_limit(self, account_id: str, info: RateLimitInfo) -> str:
        """Save rate limit info"""
        if self.storage:
            return await self.storage.save_rate_limit(account_id, info)

        data = {
            "account_id": account_id,
            "hour_window": datetime.utcnow().replace(minute=0, second=0, microsecond=0).isoformat(),
            "auto_replies_sent": info.auto_replies_sent_this_hour,
            "last_reply_thread_id": info.last_reply_thread_id
        }

        result = self.client.table("rate_limits").upsert(data).execute()
        return result.data[0]["id"]

    async def get_rate_limit(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get current rate limit info"""
        if self.storage:
            return await self.storage.get_rate_limit(account_id)

        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        result = self.client.table("rate_limits").select("*").eq("account_id", account_id).eq("hour_window", current_hour.isoformat()).execute()
        return result.data[0] if result.data else None

    # Kill switch operations
    async def is_kill_switch_active(self) -> bool:
        """Check if kill switch is active"""
        if self.storage:
            return await self.storage.is_kill_switch_active()

        result = self.client.table("kill_switch").select("*").order("updated_at", desc=True).limit(1).execute()
        if result.data:
            return result.data[0]["is_active"]
        return False

    async def activate_kill_switch(self, reason: str, activated_by: str) -> bool:
        """Activate kill switch"""
        if self.storage:
            return await self.storage.activate_kill_switch(reason, activated_by)

        data = {
            "is_active": True,
            "reason": reason,
            "activated_at": datetime.utcnow().isoformat(),
            "activated_by": activated_by,
            "updated_at": datetime.utcnow().isoformat()
        }

        result = self.client.table("kill_switch").insert(data).execute()

        # Cancel all pending drafts
        if len(result.data) > 0:
            try:
                pending_result = (
                    self.client.table("drafts")
                    .update({"status": DraftStatus.CANCELLED.value})
                    .eq("status", DraftStatus.PENDING.value)
                    .execute()
                )
                print(f"Kill switch activated: cancelled {len(pending_result.data)} pending drafts")
            except Exception as e:
                print(f"Error cancelling pending drafts on kill switch: {e}")

        return len(result.data) > 0

    async def deactivate_kill_switch(self) -> bool:
        """Deactivate kill switch"""
        if self.storage:
            return await self.storage.deactivate_kill_switch()

        data = {
            "is_active": False,
            "updated_at": datetime.utcnow().isoformat()
        }

        result = self.client.table("kill_switch").insert(data).execute()
        return len(result.data) > 0

    async def get_auto_reply_enabled(self, user_id: str) -> bool:
        if self.storage:
            return await self.storage.get_auto_reply_enabled(user_id)
        result = (
            self.client.table("automation_settings")
            .select("auto_reply_enabled")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return bool(result.data and result.data[0].get("auto_reply_enabled"))

    async def set_auto_reply_enabled(self, user_id: str, enabled: bool) -> bool:
        if self.storage:
            return await self.storage.set_auto_reply_enabled(user_id, enabled)
        result = self.client.table("automation_settings").upsert(
            {"user_id": user_id, "auto_reply_enabled": enabled}
        ).execute()
        return bool(result.data)

    # Account operations
    async def save_account(self, user_id: str, provider: str, email_address: str, credentials: Dict[str, Any], account_id: Optional[str] = None) -> str:
        """Save an email account with versioned authenticated encryption."""
        if self.storage:
            return await self.storage.save_account(user_id, provider, email_address, credentials, account_id)

        secret_store = SecretStore()
        associated_data = f"email-account:{user_id}:{provider}:{email_address}"
        encrypted_credentials = {
            "version": 1,
            "ciphertext": secret_store.encrypt(
                json.dumps(credentials, separators=(",", ":")),
                associated_data,
            ),
        }
        data = {
            "user_id": user_id,
            "provider": provider,
            "email_address": email_address,
            "credentials": encrypted_credentials
        }
        if account_id:
            data["id"] = account_id

        result = self.client.table("email_accounts").insert(data).execute()
        return result.data[0]["id"]

    async def create_oauth_state(self, state: str, expires_at: datetime) -> None:
        if not self.storage:
            raise RuntimeError("OAuth state storage requires SQLite")
        await self.storage.create_oauth_state(state, expires_at)

    async def consume_oauth_state(self, state: str) -> bool:
        if not self.storage:
            raise RuntimeError("OAuth state storage requires SQLite")
        return await self.storage.consume_oauth_state(state)

    async def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get an account by ID"""
        if self.storage:
            return await self.storage.get_account(account_id)

        result = self.client.table("email_accounts").select("*").eq("id", account_id).execute()
        return self._decrypt_account(result.data[0]) if result.data else None

    async def get_accounts_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all accounts for a user"""
        if self.storage:
            return await self.storage.get_accounts_by_user(user_id)

        result = self.client.table("email_accounts").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        return [self._decrypt_account(account) for account in result.data]

    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        if self.storage:
            return await self.storage.export_user_data(user_id)
        accounts = await self.get_accounts_by_user(user_id)
        exported_accounts = [public_account(account) for account in accounts]
        emails = []
        for account in accounts:
            emails.extend(await self.get_emails_by_account(account["id"], limit=100000))
        return {"user_id": user_id, "accounts": exported_accounts, "emails": emails}

    async def delete_user_data(self, user_id: str) -> Dict[str, int]:
        if self.storage:
            return await self.storage.delete_user_data(user_id)
        raise NotImplementedError(
            "User deletion for Supabase requires an administrator-approved retention migration"
        )

    @staticmethod
    def _decrypt_account(account: Dict[str, Any]) -> Dict[str, Any]:
        stored = account.get("credentials")
        if not isinstance(stored, dict) or stored.get("version") != 1:
            raise RuntimeError("account credentials require controlled encryption migration")

        associated_data = (
            f"email-account:{account['user_id']}:{account['provider']}:"
            f"{account['email_address']}"
        )
        plaintext = SecretStore().decrypt(stored["ciphertext"], associated_data)
        try:
            credentials = json.loads(plaintext)
        except json.JSONDecodeError as exc:
            raise RuntimeError("account credentials are invalid") from exc
        if not isinstance(credentials, dict):
            raise RuntimeError("account credentials are invalid")

        return {**account, "credentials": credentials}

    # Provider settings operations
    async def save_provider_setting(
        self,
        user_id: str,
        provider: str,
        api_key: str,
        model_classification: str = "",
        model_drafting: str = "",
    ) -> str:
        """Save or update a provider setting with encrypted API key."""
        if self.storage:
            return await self.storage.save_provider_setting(
                user_id, provider, api_key, model_classification, model_drafting
            )

        secret_store = SecretStore()
        associated_data = f"provider-setting:{user_id}:{provider}"
        encrypted_key = {
            "version": 1,
            "ciphertext": secret_store.encrypt(api_key, associated_data),
        }
        data = {
            "user_id": user_id,
            "provider": provider,
            "api_key": encrypted_key,
            "model_classification": model_classification,
            "model_drafting": model_drafting,
        }

        # Upsert
        result = self.client.table("provider_settings").upsert(data).execute()
        return result.data[0]["id"]

    async def get_provider_setting(
        self, user_id: str, provider: str
    ) -> Optional[Dict[str, Any]]:
        """Get a provider setting for a user, with decrypted API key."""
        if self.storage:
            return await self.storage.get_provider_setting(user_id, provider)

        result = (
            self.client.table("provider_settings")
            .select("*")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .execute()
        )
        if not result.data:
            return None

        setting = result.data[0]
        return self._decrypt_provider_setting(setting, user_id, provider)

    async def get_provider_settings_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all provider settings for a user, with decrypted API keys."""
        if self.storage:
            return await self.storage.get_provider_settings_by_user(user_id)

        result = (
            self.client.table("provider_settings")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return [
            self._decrypt_provider_setting(setting, user_id, setting["provider"])
            for setting in result.data
        ]

    async def delete_provider_setting(self, user_id: str, provider: str) -> bool:
        """Delete a provider setting for a user."""
        if self.storage:
            return await self.storage.delete_provider_setting(user_id, provider)

        result = (
            self.client.table("provider_settings")
            .delete()
            .eq("user_id", user_id)
            .eq("provider", provider)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def _decrypt_provider_setting(
        setting: Dict[str, Any], user_id: str, provider: str
    ) -> Dict[str, Any]:
        """Decrypt provider setting API key."""
        stored = setting.get("api_key")
        if not isinstance(stored, dict) or stored.get("version") != 1:
            raise RuntimeError("provider API key requires controlled encryption migration")

        associated_data = f"provider-setting:{user_id}:{provider}"
        plaintext = SecretStore().decrypt(stored["ciphertext"], associated_data)
        return {**setting, "api_key": plaintext}

    @staticmethod
    def public_provider_setting(setting: Dict[str, Any]) -> Dict[str, Any]:
        """Return provider setting metadata without the API key."""
        return {
            key: value
            for key, value in setting.items()
            if key != "api_key" and key != "user_id"
        }

    # Email label operations
    async def save_email_labels(
        self, email_id: str, labels: List[str], source: str = "system"
    ) -> bool:
        """Save labels for an email with deduplication."""
        if self.storage:
            return await self.storage.save_email_labels(email_id, labels, source)

        if not labels:
            return True

        # Get existing labels
        existing = await self.get_email_labels(email_id)
        existing_names = {label["name"] for label in existing}

        # Add only new labels
        new_labels = [
            {"email_id": email_id, "name": label, "source": source}
            for label in labels
            if label not in existing_names
        ]

        if not new_labels:
            return True

        result = self.client.table("email_labels").insert(new_labels).execute()
        return len(result.data) > 0

    async def get_email_labels(self, email_id: str) -> List[Dict[str, Any]]:
        """Get all labels for an email."""
        if self.storage:
            return await self.storage.get_email_labels(email_id)

        result = (
            self.client.table("email_labels")
            .select("*")
            .eq("email_id", email_id)
            .execute()
        )
        return result.data

    async def delete_email_label(self, email_id: str, label_name: str) -> bool:
        """Delete a specific label from an email."""
        if self.storage:
            return await self.storage.delete_email_label(email_id, label_name)

        result = (
            self.client.table("email_labels")
            .delete()
            .eq("email_id", email_id)
            .eq("name", label_name)
            .execute()
        )
        return len(result.data) > 0
