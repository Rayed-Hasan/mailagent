"""
Database layer using Supabase
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from supabase import create_client, Client

from mailagent.core.config import settings
from mailagent.core.types import (
    EmailMessage, ClassificationResult, Draft, AuditLogEntry,
    UserVoiceProfile, RateLimitInfo, EmailCategory, EmailAction, DraftStatus
)


class Database:
    """Database operations using Supabase"""

    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key
        )

    # Email operations
    async def save_email(self, email: EmailMessage, account_id: str) -> str:
        """Save an email to the database"""
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
        result = self.client.table("emails").select("*").eq("id", email_id).execute()
        return result.data[0] if result.data else None

    async def get_emails_by_account(self, account_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get emails for an account"""
        result = self.client.table("emails").select("*").eq("account_id", account_id).limit(limit).execute()
        return result.data

    # Classification operations
    async def save_classification(self, classification: ClassificationResult) -> str:
        """Save a classification result"""
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
        result = self.client.table("classifications").select("*").eq("email_id", email_id).execute()
        return result.data[0] if result.data else None

    # Draft operations
    async def save_draft(self, draft: Draft) -> str:
        """Save a draft"""
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
        result = self.client.table("drafts").select("*").eq("status", "pending").execute()
        return result.data

    # Audit log operations
    async def log_audit(self, entry: AuditLogEntry) -> str:
        """Log an audit entry"""
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
        result = self.client.table("audit_log").select("*").eq("email_id", email_id).order("timestamp", desc=True).execute()
        return result.data

    # User voice profile operations
    async def save_voice_profile(self, user_id: str, profile: UserVoiceProfile) -> str:
        """Save user voice profile"""
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
        result = self.client.table("user_voice_profile").select("*").eq("user_id", user_id).execute()
        return result.data[0] if result.data else None

    # Rate limit operations
    async def save_rate_limit(self, account_id: str, info: RateLimitInfo) -> str:
        """Save rate limit info"""
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
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        result = self.client.table("rate_limits").select("*").eq("account_id", account_id).eq("hour_window", current_hour.isoformat()).execute()
        return result.data[0] if result.data else None

    # Kill switch operations
    async def is_kill_switch_active(self) -> bool:
        """Check if kill switch is active"""
        result = self.client.table("kill_switch").select("*").order("updated_at", desc=True).limit(1).execute()
        if result.data:
            return result.data[0]["is_active"]
        return False

    async def activate_kill_switch(self, reason: str, activated_by: str) -> bool:
        """Activate kill switch"""
        data = {
            "is_active": True,
            "reason": reason,
            "activated_at": datetime.utcnow().isoformat(),
            "activated_by": activated_by,
            "updated_at": datetime.utcnow().isoformat()
        }

        result = self.client.table("kill_switch").insert(data).execute()
        return len(result.data) > 0

    async def deactivate_kill_switch(self) -> bool:
        """Deactivate kill switch"""
        data = {
            "is_active": False,
            "updated_at": datetime.utcnow().isoformat()
        }

        result = self.client.table("kill_switch").insert(data).execute()
        return len(result.data) > 0

    # Account operations
    async def save_account(self, user_id: str, provider: str, email_address: str, credentials: Dict[str, Any]) -> str:
        """Save an email account"""
        data = {
            "user_id": user_id,
            "provider": provider,
            "email_address": email_address,
            "credentials": credentials
        }

        result = self.client.table("email_accounts").insert(data).execute()
        return result.data[0]["id"]

    async def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get an account by ID"""
        result = self.client.table("email_accounts").select("*").eq("id", account_id).execute()
        return result.data[0] if result.data else None

    async def get_accounts_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all accounts for a user"""
        result = self.client.table("email_accounts").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        return result.data
