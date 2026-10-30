"""
Worth-sending policy engine - determines if a reply should be sent
"""

import re
from typing import List, Optional
from datetime import datetime, timedelta

from mailagent.core.types import EmailMessage, EmailCategory, EmailAction, Draft, RateLimitInfo
from mailagent.core.config import settings


class WorthSendingPolicy:
    """
    Hardcoded policy to determine if a reply is worth sending.
    A reply is sent only if ALL conditions are true.
    """

    # Sensitive topics that always require human review
    SENSITIVE_TOPICS = [
        "money", "payment", "invoice", "billing", "financial",
        "legal", "contract", "agreement", "lawsuit",
        "medical", "health", "doctor", "hospital",
        "hr", "human resources", "employment", "firing", "hiring",
        "compliance", "regulatory", "audit",
        "emotional", "upset", "angry", "frustrated"
    ]

    # First-time sender detection window (days)
    FIRST_TIME_SENDER_WINDOW = 30

    def __init__(self, confidence_threshold: float = None, allow_first_time_senders: bool = False):
        self.confidence_threshold = confidence_threshold or settings.confidence_threshold
        self.allow_first_time_senders = allow_first_time_senders

    async def should_send_reply(
        self,
        email: EmailMessage,
        classification: EmailCategory,
        confidence: float,
        sender_history: Optional[List[EmailMessage]] = None,
        rate_limit_info: Optional[RateLimitInfo] = None
    ) -> tuple[bool, str]:
        """
        Determine if a reply should be sent based on hardcoded policy.

        Returns:
            (should_send, reason)
        """

        # Check 1: Must be from a real person or service that expects a reply
        if not self._is_from_real_person(email):
            return False, "Not from a real person or service expecting reply"

        # Spam may be shown in the demo inbox for diagnosis, but must never
        # trigger an automatic response.
        gmail_labels = email.raw_headers.get("X-MailAgent-Gmail-Label-Ids", "")
        if classification == EmailCategory.SPAM or "SPAM" in gmail_labels.split():
            return False, "Spam messages are never auto-replied to"

        # Check 2: Must ask a question, request action, or need confirmation
        if not self._requires_response(email):
            return False, "No question, action request, or confirmation needed"

        # Check 3: Agent must be able to answer fully from thread + guidelines
        # This is checked during draft generation

        # Check 4: Confidence must meet threshold
        if confidence < self.confidence_threshold:
            return False, f"Confidence {confidence} below threshold {self.confidence_threshold}"

        # Check 5: Never auto-reply to no-reply addresses
        if self._is_no_reply(email.sender_email):
            return False, "No-reply address"

        # Check 6: Never auto-reply to newsletters, promos, automated notifications
        if self._is_automated(email):
            return False, "Automated email (newsletter, promo, or notification)"

        # Check 7: Check for sensitive topics
        if self._contains_sensitive_topic(email):
            return False, "Contains sensitive topic requiring human review"

        # Check 8: First-time sender check
        if not self.allow_first_time_senders and self._is_first_time_sender(email, sender_history):
            return False, "First-time sender requires human review"

        # Check 9: Rate limiting
        if rate_limit_info and not rate_limit_info.can_send:
            return False, rate_limit_info.reason or "Rate limit exceeded"

        # All checks passed
        return True, "All policy checks passed"

    def _is_from_real_person(self, email: EmailMessage) -> bool:
        """Check if email is from a real person or service expecting reply"""
        # Check headers for automated indicators
        auto_indicators = [
            "auto-submitted",
            "x-auto-generated",
            "list-id",
            "list-post"
        ]

        for key, value in email.raw_headers.items():
            if any(indicator in key.lower() for indicator in auto_indicators):
                return False

        return True

    def _requires_response(self, email: EmailMessage) -> bool:
        """Check if email asks a question, requests action, or needs confirmation"""
        body_lower = email.body.lower()
        subject_lower = email.subject.lower()

        # Question indicators
        question_indicators = ["?", "question", "ask", "wondering", "clarify"]

        # Action request indicators
        action_indicators = [
            "please", "could you", "would you", "can you",
            "need you to", "request", "confirm", "let me know",
            "get back to me", "respond"
        ]

        # Check for questions
        if "?" in body_lower or "?" in subject_lower:
            return True

        # Check for action requests
        for indicator in action_indicators:
            if indicator in body_lower or indicator in subject_lower:
                return True

        return False

    def _is_no_reply(self, email_address: str) -> bool:
        """Check if email is a no-reply address"""
        no_reply_patterns = [
            r"noreply@",
            r"no-reply@",
            r"donotreply@",
            r"do-not-reply@",
            r"notifications@",
            r"alert@",
            r"mailer@",
            r"bounce@"
        ]
        email_lower = email_address.lower()
        return any(re.search(pattern, email_lower) for pattern in no_reply_patterns)

    def _is_automated(self, email: EmailMessage) -> bool:
        """Check if email is automated (newsletter, promo, notification)"""
        # Check for unsubscribe header
        if "list-unsubscribe" in [k.lower() for k in email.raw_headers.keys()]:
            return True

        # Check for list headers
        if any(k.lower().startswith("list-") for k in email.raw_headers.keys()):
            return True

        # Check auto-submitted header
        if "auto-submitted" in [k.lower() for k in email.raw_headers.keys()]:
            return True

        return False

    def _contains_sensitive_topic(self, email: EmailMessage) -> bool:
        """Check if email contains sensitive topics"""
        text = (email.subject + " " + email.body).lower()

        for topic in self.SENSITIVE_TOPICS:
            if topic in text:
                return True

        return False

    def _is_first_time_sender(
        self,
        email: EmailMessage,
        sender_history: Optional[List[EmailMessage]] = None
    ) -> bool:
        """Check if this is a first-time sender (within 30 days)"""
        if not sender_history:
            return True

        # Check if sender has sent emails in the last 30 days
        cutoff = datetime.utcnow() - timedelta(days=self.FIRST_TIME_SENDER_WINDOW)

        recent_emails = [
            msg for msg in sender_history
            if msg.received_at > cutoff
        ]

        return len(recent_emails) == 0
