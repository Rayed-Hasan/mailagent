"""Cheap, deterministic filtering before any model call."""

from dataclasses import dataclass
from typing import Iterable, List

from mailagent.mail.base import MailMessage


@dataclass(frozen=True)
class PrefilterResult:
    message_id: str
    skip_model: bool
    reason: str
    category: str


class Prefilter:
    """Keep newsletters and bulk automation at zero model tokens."""

    BULK_HEADERS = {"list-id", "list-unsubscribe", "precedence"}
    BULK_MARKERS = ("unsubscribe", "newsletter", "digest", "weekly update")
    NO_REPLY_MARKERS = ("no-reply@", "noreply@", "do-not-reply@")

    def inspect(self, message: MailMessage) -> PrefilterResult:
        headers = {key.lower(): value.lower() for key, value in message.headers.items()}
        text = f"{message.sender_email} {message.subject} {message.text_body}".lower()
        is_bulk = (
            any(key in headers for key in self.BULK_HEADERS)
            or any(marker in text for marker in self.BULK_MARKERS)
            or "bulk" in headers.get("precedence", "")
        )
        if is_bulk:
            return PrefilterResult(
                message.message_id,
                skip_model=True,
                reason="Bulk/newsletter mail is handled without model tokens",
                category="newsletter",
            )
        if any(marker in message.sender_email.lower() for marker in self.NO_REPLY_MARKERS):
            return PrefilterResult(
                message.message_id,
                skip_model=True,
                reason="Automated sender cannot receive a reply",
                category="notification",
            )
        return PrefilterResult(
            message.message_id,
            skip_model=False,
            reason="Needs semantic classification",
            category="unclassified",
        )

    def inspect_all(self, messages: Iterable[MailMessage]) -> List[PrefilterResult]:
        return [self.inspect(message) for message in messages]
