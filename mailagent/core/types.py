"""
Core type definitions for MailAgent
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class EmailCategory(str, Enum):
    MEETS_REPLY = "meets_reply"
    FYI = "FYI"
    NEWSLETTER = "newsletter"
    PROMO = "promo"
    RECEIVED = "received"
    NOTIFICATION = "notification"
    SPAM = "spam"
    PERSONAL = "personal"
    URGENT = "urgent"
    SENSITIVE = "sensitive"


class EmailAction(str, Enum):
    REPLY = "reply"
    DRAFT_ONLY = "draft_only"
    ARCHIVE = "archive"
    FLAG_HUMAN = "flag_human"


class AutonomyMode(str, Enum):
    APPROVE = "approve"
    AUTO_SAFE = "auto_safe"
    AUTO_FULL = "auto_full"


class EmailProvider(str, Enum):
    GMAIL = "gmail"
    YAHOO = "yahoo"
    IMAP = "imap"


class DraftStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    CANCELLED = "cancelled"


class EmailMessage(BaseModel):
    """Raw email message from provider"""
    message_id: str
    thread_id: Optional[str] = None
    sender: str
    sender_email: str
    subject: str
    body: str
    received_at: datetime
    raw_headers: Dict[str, Any] = Field(default_factory=dict)
    recipients: List[str] = Field(default_factory=list)
    cc: List[str] = Field(default_factory=list)
    in_reply_to: Optional[str] = None
    references: List[str] = Field(default_factory=list)


class ClassificationResult(BaseModel):
    """Result of email classification"""
    email_id: str
    category: EmailCategory
    priority_score: int = Field(ge=0, le=100)
    action: EmailAction
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class Draft(BaseModel):
    """Email draft"""
    email_id: str
    classification_id: str
    content: str
    status: DraftStatus = DraftStatus.PENDING
    scheduled_send_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None


class UserVoiceProfile(BaseModel):
    """User's writing style profile"""
    tone: Optional[str] = None
    avg_length: Optional[int] = None
    greeting_style: Optional[str] = None
    sign_off: Optional[str] = None
    common_phrases: List[str] = Field(default_factory=list)


class AuditLogEntry(BaseModel):
    """Audit log entry"""
    email_id: str
    classification_id: Optional[str] = None
    draft_id: Optional[str] = None
    event_type: str
    category: Optional[EmailCategory] = None
    action: Optional[EmailAction] = None
    reason: str
    confidence: Optional[float] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RateLimitInfo(BaseModel):
    """Rate limiting information"""
    auto_replies_sent_this_hour: int
    last_reply_thread_id: Optional[str] = None
    can_send: bool
    reason: Optional[str] = None
