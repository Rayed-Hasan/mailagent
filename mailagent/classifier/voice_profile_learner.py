"""
Learn user's writing style from sent emails
"""

import httpx
import json
from typing import List, Optional
from collections import Counter
import re

from mailagent.core.types import EmailMessage, UserVoiceProfile
from mailagent.core.config import settings


class VoiceProfileLearner:
    """Learn user's writing style from sent emails"""

    def __init__(self):
        self.api_key = settings.anthropic_api_key
        self.api_url = "https://api.anthropic.com/v1/messages"

    async def learn_from_history(
        self,
        sent_emails: List[EmailMessage]
    ) -> UserVoiceProfile:
        """Analyze last 50 sent emails to build style profile"""

        if not sent_emails:
            return UserVoiceProfile()

        # Take last 50 emails
        recent_emails = sent_emails[-50:]

        # Extract features
        tone = self._analyze_tone(recent_emails)
        avg_length = self._calculate_avg_length(recent_emails)
        greeting_style = self._extract_greeting_style(recent_emails)
        sign_off = self._extract_sign_off(recent_emails)
        common_phrases = self._extract_common_phrases(recent_emails)

        return UserVoiceProfile(
            tone=tone,
            avg_length=avg_length,
            greeting_style=greeting_style,
            sign_off=sign_off,
            common_phrases=common_phrases
        )

    def _analyze_tone(self, emails: List[EmailMessage]) -> str:
        """Analyze the overall tone of user's emails"""
        # This is a simplified version - in production, use Claude to analyze
        tone_keywords = {
            "formal": ["sincerely", "regards", "respectfully", "dear"],
            "casual": ["hey", "hi", "thanks", "cheers"],
            "professional": ["regarding", "concerning", "please", "thank you"],
            "friendly": ["great", "awesome", "love", "happy"]
        }

        all_text = " ".join([email.body.lower() for email in emails])
        tone_scores = {}

        for tone, keywords in tone_keywords.items():
            score = sum(1 for keyword in keywords if keyword in all_text)
            tone_scores[tone] = score

        # Return tone with highest score
        return max(tone_scores, key=tone_scores.get) if tone_scores else "professional"

    def _calculate_avg_length(self, emails: List[EmailMessage]) -> int:
        """Calculate average email length in words"""
        if not emails:
            return 0

        total_words = sum(len(email.body.split()) for email in emails)
        return total_words // len(emails)

    def _extract_greeting_style(self, emails: List[EmailMessage]) -> Optional[str]:
        """Extract common greeting patterns"""
        greetings = []

        for email in emails:
            lines = email.body.split('\n')
            if lines:
                first_line = lines[0].strip()
                if len(first_line) < 50 and any(greeting in first_line.lower() for greeting in ["hi", "hello", "hey", "dear"]):
                    greetings.append(first_line)

        if not greetings:
            return None

        # Return most common greeting
        counter = Counter(greetings)
        return counter.most_common(1)[0][0]

    def _extract_sign_off(self, emails: List[EmailMessage]) -> Optional[str]:
        """Extract common sign-off patterns"""
        sign_offs = []

        for email in emails:
            lines = email.body.split('\n')
            if lines:
                last_line = lines[-1].strip()
                if len(last_line) < 50 and any(sign in last_line.lower() for sign in ["regards", "thanks", "sincerely", "best"]):
                    sign_offs.append(last_line)

        if not sign_offs:
            return None

        # Return most common sign-off
        counter = Counter(sign_offs)
        return counter.most_common(1)[0][0]

    def _extract_common_phrases(self, emails: List[EmailMessage]) -> List[str]:
        """Extract common phrases used by user"""
        # Simplified version - extract common 2-3 word phrases
        all_text = " ".join([email.body.lower() for email in emails])

        # Remove punctuation and split into words
        words = re.findall(r'\b\w+\b', all_text)

        # Extract 2-word phrases
        phrases = []
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            phrases.append(phrase)

        # Return top 10 most common phrases
        counter = Counter(phrases)
        return [phrase for phrase, count in counter.most_common(10)]
