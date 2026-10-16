"""Normalized mail contract.

Adapters for Gmail, Microsoft Graph, IMAP/SMTP, Yahoo, iCloud, and custom
domains implement these operations. The agent never branches on mailbox type.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MailMessage:
    message_id: str
    thread_id: str
    sender: str
    sender_email: str
    recipients: List[str]
    subject: str
    text_body: str
    html_body: Optional[str]
    received_at: datetime
    headers: Dict[str, str] = field(default_factory=dict)
    content_hash: str = ""
    is_read: bool = False


class MailProvider(ABC):
    @abstractmethod
    async def list_new(self, since: Optional[datetime] = None) -> List[MailMessage]:
        raise NotImplementedError

    @abstractmethod
    async def get_thread(self, thread_id: str) -> List[MailMessage]:
        raise NotImplementedError

    @abstractmethod
    async def send(
        self,
        *,
        to: List[str],
        subject: str,
        text_body: str,
        in_reply_to: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def label(self, message_id: str, label: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def archive(self, message_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def smooth(self, message_id: str) -> None:
        """Provider-specific sync/cleanup hook; safe no-op when unsupported."""
        raise NotImplementedError
