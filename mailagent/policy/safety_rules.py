"""
Safety rules - always flag for human for sensitive topics
"""

import re
from typing import List

from mailagent.core.types import EmailMessage, EmailAction, EmailCategory


class SafetyRules:
    """
    Safety rules that always require human review.
    These rules override other policies.
    """

    # Topics that always require human review
    ALWAYS_FLAG_TOPICS = [
        "money", "payment", "invoice", "billing", "financial", "bank",
        "legal", "contract", "agreement", "lawsuit", "attorney", "lawyer",
        "medical", "health", "doctor", "hospital", "prescription", "diagnosis",
        "hr", "human resources", "employment", "firing", "hiring", "resignation",
        "compliance", "regulatory", "audit", "investigation",
        "emotional", "upset", "angry", "frustrated", "complaint", "harassment"
    ]

    # First-time sender threshold (days)
    FIRST_TIME_SENDER_DAYS = 30

    def __init__(self):
        pass

    def should_flag_for_human(
        self,
        email: EmailMessage,
        classification: EmailCategory,
        sender_history: List[EmailMessage] = None
    ) -> tuple[bool, str]:
        """
        Determine if email should be flagged for human review.

        Returns:
            (should_flag, reason)
        """

        # Check 1: Sensitive topics
        if self._contains_sensitive_topic(email):
            return True, "Contains sensitive topic requiring human review"

        # Check 2: First-time sender
        if self._is_first_time_sender(email, sender_history):
            return True, "First-time sender requires human review"

        # Check 3: Already classified as sensitive
        if classification == EmailCategory.SENSITIVE:
            return True, "Classified as sensitive"

        # Check 4: Emotional content
        if self._contains_emotional_content(email):
            return True, "Contains emotional content requiring human review"

        # Check 5: Ambiguous or unclear
        if self._is_ambiguous(email):
            return True, "Ambiguous content requires human review"

        return False, "No safety rule triggered"

    def _contains_sensitive_topic(self, email: EmailMessage) -> bool:
        """Check if email contains sensitive topics"""
        text = (email.subject + " " + email.body).lower()

        for topic in self.ALWAYS_FLAG_TOPICS:
            if topic in text:
                return True

        return False

    def _is_first_time_sender(
        self,
        email: EmailMessage,
        sender_history: List[EmailMessage] = None
    ) -> bool:
        """Check if this is a first-time sender"""
        if not sender_history:
            return True

        # Check if sender has sent emails
        sender_emails = [msg for msg in sender_history if msg.sender_email == email.sender_email]

        return len(sender_emails) == 0

    def _contains_emotional_content(self, email: EmailMessage) -> bool:
        """Check if email contains emotional content"""
        emotional_indicators = [
            "upset", "angry", "frustrated", "disappointed", "worried",
            "concerned", "complaint", "harassment", "threat", "urgent",
            "emergency", "please help", "asap", "immediately"
        ]

        text = (email.subject + " " + email.body).lower()

        return any(indicator in text for indicator in emotional_indicators)

    def _is_ambiguous(self, email: EmailMessage) -> bool:
        """Check if email content is ambiguous or unclear"""
        # Check for vague language
        vague_indicators = [
            "maybe", "perhaps", "not sure", "unclear", "confusing",
            "what do you think", "your thoughts", "any ideas"
        ]

        text = (email.subject + " " + email.body).lower()

        # Also check if email is very short and unclear
        word_count = len(email.body.split())

        return word_count < 10 and any(indicator in text for indicator in vague_indicators)

    def override_action(self, email: EmailMessage, classification: EmailCategory) -> EmailAction:
        """
        Override action to FLAG_HUMAN if safety rules are triggered.
        """
        should_flag, _ = self.should_flag_for_human(email, classification)

        if should_flag:
            return EmailAction.FLAG_HUMAN

        return None  # No override
