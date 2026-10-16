"""
Email classifier using Claude API
"""

import httpx
import json
from typing import List, Optional
from datetime import datetime

from mailagent.core.types import EmailMessage, EmailCategory, ClassificationResult
from mailagent.core.config import settings


class EmailClassifier:
    """Classify emails using Claude API"""

    def __init__(self):
        self.api_key = settings.anthropic_api_key
        self.api_url = "https://api.anthropic.com/v1/messages"

    async def classify(
        self,
        email: EmailMessage,
        thread: Optional[List[EmailMessage]] = None,
        sender_history: Optional[List[EmailMessage]] = None
    ) -> ClassificationResult:
        """Classify a single email"""

        # Build context
        context = self._build_context(email, thread, sender_history)

        # Create prompt
        prompt = self._create_classification_prompt(email, context)

        # Call Claude API
        try:
            response = await self._call_claude(prompt)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError):
            # A missing/failed BYOK provider must not block sorting. This
            # deterministic fallback also keeps bulk test and local demo runs
            # offline; no credential or email body is logged.
            return self._fallback_classification(email)

        # Parse response
        return self._parse_classification_response(email.message_id, response)

    def _fallback_classification(self, email: EmailMessage) -> ClassificationResult:
        text = f"{email.subject} {email.body}".lower()
        sender = email.sender_email.lower()
        if "list-unsubscribe" in {key.lower() for key in email.raw_headers} or "newsletter" in text or "digest" in text:
            category = EmailCategory.NEWSLETTER
            action = "archive"
            priority = 15
        elif any(word in text for word in ("payment", "invoice", "legal", "medical", "contract", "hr", "complaint")):
            category = EmailCategory.SENSITIVE
            action = "flag_human"
            priority = 95
        elif any(word in text for word in ("urgent", "asap", "immediately", "emergency")):
            category = EmailCategory.URGENT
            action = "flag_human"
            priority = 90
        elif any(marker in sender for marker in ("noreply@", "no-reply@", "notification@")):
            category = EmailCategory.NOTIFICATION
            action = "archive"
            priority = 25
        elif "?" in text or any(word in text for word in ("please", "can you", "could you", "confirm")):
            category = EmailCategory.MEETS_REPLY
            action = "draft_only"
            priority = 75
        else:
            category = EmailCategory.FYI
            action = "archive"
            priority = 35
        return ClassificationResult(
            email_id=email.message_id,
            category=category,
            priority_score=priority,
            action=action,
            confidence=0.75,
            reason="Deterministic offline fallback; provider unavailable",
        )

    async def classify_batch(
        self,
        emails: List[EmailMessage]
    ) -> List[ClassificationResult]:
        """Classify multiple emails in batch"""
        results = []
        for email in emails:
            result = await self.classify(email)
            results.append(result)
        return results

    def _build_context(
        self,
        email: EmailMessage,
        thread: Optional[List[EmailMessage]] = None,
        sender_history: Optional[List[EmailMessage]] = None
    ) -> str:
        """Build context string from thread and sender history"""
        context_parts = []

        if thread:
            context_parts.append("THREAD CONTEXT:")
            for msg in thread:
                context_parts.append(f"From: {msg.sender}")
                context_parts.append(f"Subject: {msg.subject}")
                context_parts.append(f"Body: {msg.body[:500]}...")
                context_parts.append("---")

        if sender_history:
            context_parts.append("\nSENDER HISTORY:")
            for msg in sender_history[-5:]:  # Last 5 messages
                context_parts.append(f"Subject: {msg.subject}")
                context_parts.append(f"Body: {msg.body[:200]}...")
                context_parts.append("---")

        return "\n".join(context_parts)

    def _create_classification_prompt(self, email: EmailMessage, context: str) -> str:
        """Create classification prompt for Claude"""

        prompt = f"""You are an email classification assistant. Classify the following email into one of these categories:

Categories:
- meets_reply: The email is a direct reply to a previous message, continuing a conversation
- FYI: Informational, no action required
- newsletter: Subscription newsletter or digest
- promo: Promotional or marketing content
- received: Automated confirmation or receipt
- notification: System notification or alert
- spam: Unsolicited or suspicious content
- personal: Personal correspondence
- urgent: Requires immediate attention
- sensitive: Contains sensitive information (money, legal, medical, HR, compliance)

Email Details:
From: {email.sender}
Email: {email.sender_email}
Subject: {email.subject}
Body:
{email.body}

{context}

Task:
1. Classify the email into ONE category
2. Assign a priority score (0-100, where 100 is highest priority)
3. Determine the best action: reply, draft_only, archive, or flag_human
4. Provide a brief reason for your decision
5. Provide your confidence (0.0 to 1.0)

Respond in JSON format only:
{{
  "category": "category_name",
  "priority_score": 0-100,
  "action": "action_name",
  "reason": "brief explanation",
  "confidence": 0.0-1.0
}}
"""

        return prompt

    async def _call_claude(self, prompt: str) -> dict:
        """Call Claude API directly via HTTP"""

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        # Extract content from response
        content = data["content"][0]["text"]
        return json.loads(content)

    def _parse_classification_response(self, email_id: str, response: dict) -> ClassificationResult:
        """Parse Claude's response into ClassificationResult"""

        return ClassificationResult(
            email_id=email_id,
            category=EmailCategory(response["category"]),
            priority_score=response["priority_score"],
            action=response["action"],
            confidence=response["confidence"],
            reason=response["reason"]
        )
