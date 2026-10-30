"""
Email classifier using provider abstraction
"""

import httpx
import json
from typing import List, Optional
from datetime import datetime

from mailagent.core.types import EmailMessage, EmailCategory, ClassificationResult
from mailagent.core.config import settings
from mailagent.llm.base import LLMMessage, LLMProvider
from mailagent.llm.registry import ProviderRegistry


class EmailClassifier:
    """Classify emails using configured LLM provider"""

    def __init__(self, provider_registry: Optional[ProviderRegistry] = None):
        self.provider_registry = provider_registry
        # Fallback to v1 direct Claude if no registry provided (preserves v1 behavior)
        if not provider_registry:
            self.api_key = settings.anthropic_api_key
            self.api_url = "https://api.anthropic.com/v1/messages"
        else:
            self.api_key = None
            self.api_url = None

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

        # Use provider abstraction if available, otherwise fallback to v1 direct Claude
        if self.provider_registry:
            try:
                response = await self._call_via_provider(prompt)
            except Exception:
                # Provider failure should not block sorting
                return self._fallback_classification(email)
        else:
            try:
                response = await self._call_claude(prompt)
            except (httpx.HTTPError, KeyError, json.JSONDecodeError):
                # A missing/failed BYOK provider must not block sorting. This
                # deterministic fallback also keeps bulk test and local demo runs
                # offline; no credential or email body is logged.
                return self._fallback_classification(email)

        # Validate response
        is_valid, error = self._validate_classification_response(response)
        if not is_valid:
            # Malformed response - use fallback
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
        elif any(word in text for word in ("offer", "promo", "discount", "deal", "save ", "coupon", "% off", "sale")):
            category = EmailCategory.PROMO
            action = "archive"
            priority = 20
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
- FYI: Informational content that may be useful but requires no immediate action
- newsletter: Subscription newsletter, digest, or recurring marketing communication
- promo: Promotional or marketing content with sales, discounts, or offers
- received: Automated confirmation, receipt, or transaction notification
- notification: System notification, alert, or automated status update
- spam: Unsolicited, suspicious, or clearly malicious content
- personal: Personal correspondence from known contacts
- urgent: Requires immediate attention or has a time-sensitive deadline
- sensitive: Contains sensitive information (money, legal, medical, HR, compliance, security)

Classification Guidelines:
1. If the email contains security alerts, password resets, financial transactions, or calendar invitations, use 'urgent' or 'sensitive'
2. If the email is clearly promotional with sales/discounts, use 'promo'
3. If the email is a newsletter or digest with unsubscribe links, use 'newsletter'
4. If the email is a direct reply in a thread, use 'meets_reply'
5. If the email is an automated confirmation or receipt, use 'received'
6. If the email is a system notification that cannot receive replies, use 'notification'
7. If the email asks a question or requests action, consider 'meets_reply' or 'urgent'
8. If the email is clearly spam or suspicious, use 'spam'
9. If the email is personal correspondence, use 'personal'
10. If the email is informational but not actionable, use 'FYI'

Priority Scoring (0-100):
- 90-100: Urgent or sensitive requiring immediate attention
- 70-89: Important action needed soon
- 50-69: Action needed but not urgent
- 30-49: Informational, may be useful
- 10-29: Low priority, likely promotional or automated
- 0-9: Spam or ignore

Action Determination:
- reply: Email asks a question or requests a response
- draft_only: Email may warrant a reply but should be reviewed first
- archive: No action needed, can be archived
- flag_human: Requires human review (sensitive, emergency, or ambiguous). Do not choose this action only because the sender says the message is urgent; routine urgent requests can be auto-replied when policy checks pass.

Email Details:
From: {email.sender}
Email: {email.sender_email}
Subject: {email.subject}
Body:
{email.body}

{context}

Task:
1. Classify the email into ONE category from the list above
2. Assign a priority score (0-100) based on importance and urgency
3. Determine the best action: reply, draft_only, archive, or flag_human
4. Provide a brief reason for your decision (1-2 sentences)
5. Provide your confidence (0.0 to 1.0) based on how clear the classification is

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

    async def _call_via_provider(self, prompt: str) -> dict:
        """Call LLM via provider registry"""
        provider, model = self.provider_registry.get("classification")

        # Define response schema for classification
        response_schema = {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "meets_reply",
                        "FYI",
                        "newsletter",
                        "promo",
                        "received",
                        "notification",
                        "spam",
                        "personal",
                        "urgent",
                        "sensitive",
                    ],
                },
                "priority_score": {"type": "integer", "minimum": 0, "maximum": 100},
                "action": {
                    "type": "string",
                    "enum": ["reply", "draft_only", "archive", "flag_human"],
                },
                "reason": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["category", "priority_score", "action", "reason", "confidence"],
        }

        response = await provider.complete(
            messages=[LLMMessage(role="user", content=prompt)],
            model=model,
            response_schema=response_schema,
            json_mode=True,
            max_tokens=1024,
            timeout_seconds=30,
        )

        # Parse tool call result (JSON mode returns it in tool_calls)
        if response.tool_calls:
            return json.loads(response.tool_calls[0].get("arguments", "{}"))
        else:
            # Fallback to parsing text if tool_calls not populated
            return json.loads(response.text)

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

    def _validate_classification_response(self, response: dict) -> tuple[bool, str]:
        """Validate classification response structure and values.

        Returns (is_valid, error_message).
        """
        required_fields = {"category", "priority_score", "action", "reason", "confidence"}
        if not all(field in response for field in required_fields):
            return False, f"Missing required fields: {required_fields - set(response.keys())}"

        # Validate category
        valid_categories = {
            "meets_reply",
            "FYI",
            "newsletter",
            "promo",
            "received",
            "notification",
            "spam",
            "personal",
            "urgent",
            "sensitive",
        }
        if response["category"] not in valid_categories:
            return False, f"Invalid category: {response['category']}"

        # Validate priority_score
        try:
            priority = int(response["priority_score"])
            if not (0 <= priority <= 100):
                return False, f"Priority score out of range: {priority}"
        except (ValueError, TypeError):
            return False, f"Invalid priority score: {response['priority_score']}"

        # Validate action
        valid_actions = {"reply", "draft_only", "archive", "flag_human"}
        if response["action"] not in valid_actions:
            return False, f"Invalid action: {response['action']}"

        # Validate confidence
        try:
            confidence = float(response["confidence"])
            if not (0.0 <= confidence <= 1.0):
                return False, f"Confidence out of range: {confidence}"
        except (ValueError, TypeError):
            return False, f"Invalid confidence: {response['confidence']}"

        return True, ""

    def _parse_classification_response(self, email_id: str, response: dict) -> ClassificationResult:
        """Parse Claude's response into ClassificationResult"""

        return ClassificationResult(
            email_id=email_id,
            category=EmailCategory(response["category"]),
            priority_score=response["priority_score"],
            action=response["action"],
            confidence=response["confidence"],
            reason=response["reason"],
            raw=response  # Store raw response for fallback detection
        )
