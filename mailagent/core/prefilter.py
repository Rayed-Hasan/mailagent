"""Cheap, deterministic filtering before any model call."""

from dataclasses import dataclass
from typing import Iterable, List, Literal

from mailagent.mail.base import MailMessage


@dataclass(frozen=True)
class PrefilterResult:
    message_id: str
    skip_model: bool
    reason: str
    reason_code: str
    category: str
    is_important: bool = False
    requires_action: bool = False


class Prefilter:
    """Deterministic filtering before LLM classification.

    Protects important messages from broad filtering while handling
    newsletters, promotions, and automated notifications efficiently.
    """

    # Bulk/newsletter indicators
    BULK_HEADERS = {"list-id", "list-unsubscribe", "precedence", "list-post"}
    BULK_MARKERS = (
        "unsubscribe",
        "newsletter",
        "digest",
        "weekly update",
        "monthly digest",
        "subscription",
    )
    NO_REPLY_MARKERS = ("no-reply@", "noreply@", "do-not-reply@", "donotreply@")
    PROMO_MARKERS = (
        "promo",
        "promotion",
        "sale",
        "discount",
        "offer",
        "deal",
        "limited time",
        "exclusive offer",
    )

    # Important message protection
    SECURITY_KEYWORDS = (
        "security alert",
        "security warning",
        "unusual sign-in",
        "suspicious activity",
        "account compromised",
        "password reset",
        "verify your identity",
        "2fa",
        "two-factor",
        "authentication",
    )
    FINANCIAL_KEYWORDS = (
        "invoice",
        "payment",
        "receipt",
        "transaction",
        "billing",
        "credit card",
        "bank statement",
        "payment confirmation",
        "purchase",
    )
    CALENDAR_KEYWORDS = (
        "calendar invitation",
        "meeting invite",
        "calendar event",
        "accepted",
        "declined",
        "tentative",
    )
    URGENT_KEYWORDS = (
        "urgent",
        "asap",
        "immediately",
        "emergency",
        "time-sensitive",
        "deadline",
        "expires",
    )

    def inspect(self, message: MailMessage) -> PrefilterResult:
        """Inspect a message and return prefilter decision.

        Important messages (security, financial, calendar, urgent) are protected
        from skip_model filtering even if they match bulk patterns.
        """
        headers = {key.lower(): value.lower() for key, value in message.headers.items()}
        text = f"{message.sender_email} {message.subject} {message.text_body}".lower()

        # Check for important messages first (protection override)
        is_important, importance_reason = self._check_important(text, headers)
        if is_important:
            return PrefilterResult(
                message.message_id,
                skip_model=False,
                reason=f"Important message: {importance_reason}",
                reason_code="important",
                category="unclassified",
                is_important=True,
                requires_action=True,
            )

        # Check for bulk/newsletter
        is_bulk = self._check_bulk(headers, text)
        if is_bulk:
            return PrefilterResult(
                message.message_id,
                skip_model=True,
                reason="Bulk/newsletter mail is handled without model tokens",
                reason_code="bulk",
                category="newsletter",
                is_important=False,
                requires_action=False,
            )

        # Check for no-reply automated senders
        is_no_reply = any(marker in message.sender_email.lower() for marker in self.NO_REPLY_MARKERS)
        if is_no_reply:
            return PrefilterResult(
                message.message_id,
                skip_model=True,
                reason="Automated sender cannot receive a reply",
                reason_code="no_reply",
                category="notification",
                is_important=False,
                requires_action=False,
            )

        # Check for promotional content
        is_promo = any(marker in text for marker in self.PROMO_MARKERS)
        if is_promo:
            return PrefilterResult(
                message.message_id,
                skip_model=True,
                reason="Promotional content handled without model tokens",
                reason_code="promo",
                category="promo",
                is_important=False,
                requires_action=False,
            )

        # Default: needs semantic classification
        return PrefilterResult(
            message.message_id,
            skip_model=False,
            reason="Needs semantic classification",
            reason_code="needs_classification",
            category="unclassified",
            is_important=False,
            requires_action=False,
        )

    def _check_bulk(self, headers: dict, text: str) -> bool:
        """Check if message is bulk/newsletter."""
        return (
            any(key in headers for key in self.BULK_HEADERS)
            or any(marker in text for marker in self.BULK_MARKERS)
            or "bulk" in headers.get("precedence", "")
        )

    def _check_important(self, text: str, headers: dict) -> tuple[bool, str]:
        """Check if message is important and should be protected from filtering.

        Returns (is_important, reason).
        """
        # Security alerts
        if any(keyword in text for keyword in self.SECURITY_KEYWORDS):
            return True, "security alert or authentication"

        # Financial messages
        if any(keyword in text for keyword in self.FINANCIAL_KEYWORDS):
            return True, "financial or billing message"

        # Calendar invitations
        if any(keyword in text for keyword in self.CALENDAR_KEYWORDS):
            return True, "calendar invitation"

        # Urgent messages
        if any(keyword in text for keyword in self.URGENT_KEYWORDS):
            return True, "urgent or time-sensitive"

        # Direct reply indicators (In-Reply-To header)
        if "in-reply-to" in headers:
            return True, "direct reply in thread"

        return False, ""

    def inspect_all(self, messages: Iterable[MailMessage]) -> List[PrefilterResult]:
        """Inspect multiple messages."""
        return [self.inspect(message) for message in messages]
