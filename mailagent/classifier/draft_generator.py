"""
Draft generation with user voice profile integration
"""

import httpx
import json
import logging
from typing import List, Optional

from mailagent.core.types import EmailMessage, UserVoiceProfile, Draft
from mailagent.core.config import settings
from mailagent.llm.base import LLMMessage
from mailagent.llm.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class DraftGenerator:
    """Generate email drafts using configured LLM provider with user's voice profile"""

    def __init__(self, provider_registry: Optional[ProviderRegistry] = None):
        self.provider_registry = provider_registry
        # Fallback to v1 direct Claude if no registry provided (preserves v1 behavior)
        if not provider_registry:
            self.api_key = settings.anthropic_api_key
            self.api_url = "https://api.anthropic.com/v1/messages"
        else:
            self.api_key = None
            self.api_url = None

    async def generate_draft(
        self,
        email: EmailMessage,
        thread: Optional[List[EmailMessage]] = None,
        user_guidelines: Optional[str] = None,
        voice_profile: Optional[UserVoiceProfile] = None
    ) -> Optional[str]:
        """Generate a draft reply matching user's writing style.

        Returns:
            The draft text if generation was successful, None if provider failed.
        """

        # Build context
        context = self._build_context(email, thread)

        # Create prompt with voice profile
        prompt = self._create_draft_prompt(email, context, user_guidelines, voice_profile)

        # Use provider abstraction if available, otherwise fallback to v1 direct Claude
        if self.provider_registry:
            try:
                response = await self._call_via_provider(prompt)
            except Exception as exc:
                # Provider failure - log and return None to indicate failure
                logger.error("Draft generation failed (%s)", type(exc).__name__)
                return None
        else:
            try:
                response = await self._call_claude(prompt)
            except Exception as exc:
                logger.error("Direct Claude call failed (%s)", type(exc).__name__)
                return None

        # Extract draft content
        draft = response.get("draft", "")

        # Validate draft is meaningful (not empty or obviously a fallback template)
        if not draft or not draft.strip():
            logger.warning("Generated draft was empty")
            return None

        # Check for fallback indicators
        fallback_indicators = [
            "deterministic fallback",
            "this is a fallback response",
            "configure an ai provider",
        ]
        draft_lower = draft.lower()
        if any(indicator in draft_lower for indicator in fallback_indicators):
            logger.warning("Draft output matched a fallback response")
            return None

        return draft

    async def generate_draft_batch(
        self,
        emails: List[EmailMessage],
        user_guidelines: Optional[str] = None,
        voice_profile: Optional[UserVoiceProfile] = None
    ) -> List[Optional[str]]:
        """Generate drafts for multiple emails"""
        drafts = []
        for email in emails:
            draft = await self.generate_draft(email, None, user_guidelines, voice_profile)
            drafts.append(draft)
        return drafts

    def _build_context(
        self,
        email: EmailMessage,
        thread: Optional[List[EmailMessage]] = None
    ) -> str:
        """Build context from thread"""
        if not thread:
            return ""

        context_parts = ["THREAD CONTEXT:"]
        for msg in thread:
            context_parts.append(f"From: {msg.sender}")
            context_parts.append(f"Subject: {msg.subject}")
            context_parts.append(f"Body: {msg.body[:500]}...")
            context_parts.append("---")

        return "\n".join(context_parts)

    def _create_draft_prompt(
        self,
        email: EmailMessage,
        context: str,
        user_guidelines: Optional[str],
        voice_profile: Optional[UserVoiceProfile]
    ) -> str:
        """Create draft generation prompt"""

        # Build voice profile instructions
        voice_instructions = ""
        if voice_profile:
            voice_instructions = f"""
VOICE PROFILE:
- Tone: {voice_profile.tone or 'professional'}
- Average length: {voice_profile.avg_length or 100} words
- Greeting style: {voice_profile.greeting_style or 'Hi [Name],'}
- Sign-off: {voice_profile.sign_off or 'Best regards'}
- Common phrases: {', '.join(voice_profile.common_phrases[:5]) if voice_profile.common_phrases else 'none'}
"""

        # Build user guidelines
        guidelines = ""
        if user_guidelines:
            guidelines = f"\nUSER GUIDELINES:\n{user_guidelines}\n"

        prompt = f"""You are an email drafting assistant. Write a reply to the following email.

{voice_instructions}

EMAIL TO REPLY TO:
From: {email.sender}
Email: {email.sender_email}
Subject: {email.subject}
Body:
{email.body}

{context}

{guidelines}

INSTRUCTIONS:
1. Write a professional, helpful reply
2. Match the user's voice profile as specified above
3. Keep it concise and to the point
4. Address the sender's question or request directly - if they ask for a choice between options, either pick one based on context or ask for clarification
5. Use the user's typical greeting and sign-off style
6. Include the user's common phrases where appropriate
7. DO NOT include any instructions or meta-commentary
8. DO NOT include "Here's a draft" or similar text
9. DO NOT use generic acknowledgments like "I'll look into it" - be specific and responsive
10. Output ONLY the email content

Respond in JSON format:
{{
  "draft": "the complete email draft text"
}}
"""

        return prompt

    async def _call_via_provider(self, prompt: str) -> dict:
        """Call LLM via provider registry"""
        provider, model = self.provider_registry.get("drafting")

        # Define response schema for draft generation
        response_schema = {
            "type": "object",
            "properties": {
                "draft": {"type": "string"},
            },
            "required": ["draft"],
        }

        response = await provider.complete(
            messages=[LLMMessage(role="user", content=prompt)],
            model=model,
            response_schema=response_schema,
            json_mode=True,
            max_tokens=2048,
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
            "max_tokens": 2048,
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
