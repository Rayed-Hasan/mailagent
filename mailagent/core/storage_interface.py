"""
Storage abstraction interface for database backends
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from mailagent.core.types import (
    EmailMessage, ClassificationResult, Draft, AuditLogEntry,
    UserVoiceProfile, RateLimitInfo, EmailCategory, EmailAction, DraftStatus
)


class StorageInterface(ABC):
    """Abstract interface for storage backends (Supabase, SQLite, PostgreSQL)"""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage backend (create tables, etc.)"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the storage connection"""
        pass

    # Email operations
    @abstractmethod
    async def save_email(self, email: EmailMessage, account_id: str) -> str:
        """Save an email to storage, returns email ID"""
        pass

    @abstractmethod
    async def get_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get an email by ID"""
        pass

    @abstractmethod
    async def get_email_by_message_id(self, account_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Get an email by account and provider message ID for deduplication"""
        pass

    @abstractmethod
    async def get_account_for_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get the owning account for an email"""
        pass

    @abstractmethod
    async def get_emails_by_account(
        self, account_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get emails for an account with pagination"""
        pass

    @abstractmethod
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
        pass

    # Classification operations
    @abstractmethod
    async def save_classification(self, classification: ClassificationResult) -> str:
        """Save a classification result, returns classification ID"""
        pass

    @abstractmethod
    async def get_classification(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get classification for an email"""
        pass

    # Draft operations
    @abstractmethod
    async def save_draft(self, draft: Draft) -> str:
        """Save a draft, returns draft ID"""
        pass

    @abstractmethod
    async def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """Get a draft by ID"""
        pass

    @abstractmethod
    async def update_draft_status(self, draft_id: str, status: DraftStatus) -> bool:
        """Update draft status"""
        pass

    @abstractmethod
    async def get_pending_drafts(self, account_id: str) -> List[Dict[str, Any]]:
        """Get pending drafts for an account"""
        pass

    # Audit log operations
    @abstractmethod
    async def log_audit(self, entry: AuditLogEntry) -> str:
        """Log an audit entry, returns log ID"""
        pass

    @abstractmethod
    async def get_audit_log(self, email_id: str) -> List[Dict[str, Any]]:
        """Get audit log for an email"""
        pass

    # User voice profile operations
    @abstractmethod
    async def save_voice_profile(self, user_id: str, profile: UserVoiceProfile) -> str:
        """Save user voice profile, returns profile ID"""
        pass

    @abstractmethod
    async def get_voice_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user voice profile"""
        pass

    # Rate limit operations
    @abstractmethod
    async def save_rate_limit(self, account_id: str, info: RateLimitInfo) -> str:
        """Save rate limit info, returns rate limit ID"""
        pass

    @abstractmethod
    async def get_rate_limit(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get current rate limit info"""
        pass

    # Kill switch operations
    @abstractmethod
    async def is_kill_switch_active(self) -> bool:
        """Check if kill switch is active"""
        pass

    @abstractmethod
    async def activate_kill_switch(self, reason: str, activated_by: str) -> bool:
        """Activate kill switch"""
        pass

    @abstractmethod
    async def deactivate_kill_switch(self) -> bool:
        """Deactivate kill switch"""
        pass

    # Account operations
    @abstractmethod
    async def save_account(self, user_id: str, provider: str, email_address: str, credentials: Dict[str, Any], account_id: Optional[str] = None) -> str:
        """Save an email account, returns account ID"""
        pass

    @abstractmethod
    async def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get an account by ID"""
        pass

    @abstractmethod
    async def get_accounts_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all accounts for a user"""
        pass

    @abstractmethod
    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export user-owned data without credential material."""
        pass

    @abstractmethod
    async def delete_user_data(self, user_id: str) -> Dict[str, int]:
        """Delete user-owned data and return deletion counts."""
        pass

    # Provider settings operations
    @abstractmethod
    async def save_provider_setting(
        self,
        user_id: str,
        provider: str,
        api_key: str,
        model_classification: str = "",
        model_drafting: str = "",
    ) -> str:
        """Save or update a provider setting, returns setting ID"""
        pass

    @abstractmethod
    async def get_provider_setting(self, user_id: str, provider: str) -> Optional[Dict[str, Any]]:
        """Get a provider setting for a user"""
        pass

    @abstractmethod
    async def get_provider_settings_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all provider settings for a user"""
        pass

    @abstractmethod
    async def delete_provider_setting(self, user_id: str, provider: str) -> bool:
        """Delete a provider setting for a user"""
        pass

    # Email label operations
    @abstractmethod
    async def save_email_labels(self, email_id: str, labels: List[str], source: str = "system") -> bool:
        """Save labels for an email"""
        pass

    @abstractmethod
    async def get_email_labels(self, email_id: str) -> List[Dict[str, Any]]:
        """Get all labels for an email"""
        pass

    @abstractmethod
    async def delete_email_label(self, email_id: str, label_name: str) -> bool:
        """Delete a specific label from an email"""
        pass
