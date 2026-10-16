"""
Base email provider interface
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from mailagent.core.types import EmailMessage, EmailProvider


class EmailProviderInterface(ABC):
    """Abstract base class for email providers"""

    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials
        self.provider: EmailProvider

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the email provider"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the email provider"""
        pass

    @abstractmethod
    async def fetch_emails(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
        folder: str = "INBOX"
    ) -> List[EmailMessage]:
        """Fetch emails from the provider"""
        pass

    @abstractmethod
    async def fetch_thread(self, thread_id: str) -> List[EmailMessage]:
        """Fetch all messages in a thread"""
        pass

    @abstractmethod
    async def fetch_sender_history(
        self,
        sender_email: str,
        limit: int = 50
    ) -> List[EmailMessage]:
        """Fetch historical emails from a specific sender"""
        pass

    @abstractmethod
    async def apply_label(
        self,
        message_id: str,
        label: str
    ) -> bool:
        """Apply a label to an email"""
        pass

    @abstractmethod
    async def move_to_folder(
        self,
        message_id: str,
        folder: str
    ) -> bool:
        """Move an email to a folder"""
        pass

    @abstractmethod
    async def archive(self, message_id: str) -> bool:
        """Archive an email"""
        pass

    @abstractmethod
    async def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        in_reply_to: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> str:
        """Create a draft email, returns draft ID"""
        pass

    @abstractmethod
    async def send_reply(
        self,
        draft_id: str
    ) -> bool:
        """Send a draft reply"""
        pass

    @abstractmethod
    async def delete_draft(self, draft_id: str) -> bool:
        """Delete a draft"""
        pass

    @abstractmethod
    def is_no_reply_address(self, email: str) -> bool:
        """Check if email is a no-reply address"""
        pass

    @abstractmethod
    def has_unsubscribe_header(self, headers: Dict[str, Any]) -> bool:
        """Check if email has unsubscribe header"""
        pass

    @abstractmethod
    def is_automated(self, headers: Dict[str, Any]) -> bool:
        """Check if email is automated"""
        pass
