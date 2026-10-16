"""
Main email agent orchestrator
"""

import asyncio
from typing import List, Optional
from datetime import datetime

from mailagent.core.types import (
    EmailMessage, EmailCategory, EmailAction, AutonomyMode,
    ClassificationResult, Draft, UserVoiceProfile, RateLimitInfo
)
from mailagent.core.database import Database
from mailagent.providers.base import EmailProviderInterface
from mailagent.providers.gmail_provider import GmailProvider
from mailagent.providers.imap_provider import IMAPProvider
from mailagent.classifier.email_classifier import EmailClassifier
from mailagent.classifier.voice_profile_learner import VoiceProfileLearner
from mailagent.classifier.draft_generator import DraftGenerator
from mailagent.policy.worth_sending_policy import WorthSendingPolicy
from mailagent.policy.send_flow import SendFlow
from mailagent.policy.safety_rules import SafetyRules
from mailagent.policy.rate_limiter import RateLimiter
from mailagent.core.config import settings


class EmailAgent:
    """Main email agent that orchestrates all components"""

    def __init__(self, user_id: str, autonomy_mode: AutonomyMode = None):
        self.user_id = user_id
        self.autonomy_mode = autonomy_mode or settings.default_autonomy_mode

        # Initialize components
        self.db = Database()
        self.classifier = EmailClassifier()
        self.voice_learner = VoiceProfileLearner()
        self.draft_generator = DraftGenerator()
        self.worth_sending_policy = WorthSendingPolicy()
        self.send_flow = SendFlow(self.autonomy_mode)
        self.safety_rules = SafetyRules()
        self.rate_limiter = RateLimiter()

        # Cache
        self.voice_profile: Optional[UserVoiceProfile] = None
        self.providers: dict = {}

    async def initialize(self):
        """Initialize the agent"""
        # Load user voice profile
        profile_data = await self.db.get_voice_profile(self.user_id)
        if profile_data:
            self.voice_profile = UserVoiceProfile(
                tone=profile_data.get("tone"),
                avg_length=profile_data.get("avg_length"),
                greeting_style=profile_data.get("greeting_style"),
                sign_off=profile_data.get("sign_off"),
                common_phrases=profile_data.get("common_phrases", [])
            )

        # Load email accounts
        accounts = await self.db.get_accounts_by_user(self.user_id)
        for account in accounts:
            await self._load_provider(account)

    async def _load_provider(self, account: dict):
        """Load email provider for an account"""
        provider_type = account["provider"]
        credentials = account["credentials"]
        account_id = account["id"]

        if provider_type == "gmail":
            provider = GmailProvider(credentials)
        elif provider_type in ["yahoo", "imap"]:
            provider = IMAPProvider(credentials, provider_type)
        else:
            print(f"Unknown provider: {provider_type}")
            return

        if await provider.connect():
            self.providers[account_id] = provider
            print(f"Connected to {provider_type} account: {account['email_address']}")
        else:
            print(f"Failed to connect to {provider_type} account")

    async def process_account(self, account_id: str):
        """Process all new emails for an account"""
        # Check kill switch
        if await self.db.is_kill_switch_active():
            print("Kill switch is active, skipping processing")
            return

        provider = self.providers.get(account_id)
        if not provider:
            print(f"No provider found for account {account_id}")
            return

        # Fetch new emails
        emails = await provider.fetch_emails(limit=100)

        print(f"Found {len(emails)} new emails")

        for email in emails:
            await self.process_email(email, account_id, provider)

    async def process_email(
        self,
        email: EmailMessage,
        account_id: str,
        provider: EmailProviderInterface
    ):
        """Process a single email through the pipeline"""

        # Save email to database
        email_id = await self.db.save_email(email, account_id)

        # Fetch thread and sender history
        thread = await provider.fetch_thread(email.thread_id) if email.thread_id else []
        sender_history = await provider.fetch_sender_history(email.sender_email)

        # Classify email
        classification = await self.classifier.classify(email, thread, sender_history)
        classification_id = await self.db.save_classification(classification)

        # Log classification
        await self.db.log_audit({
            "email_id": email_id,
            "classification_id": classification_id,
            "event_type": "classification",
            "category": classification.category,
            "action": classification.action,
            "reason": classification.reason,
            "confidence": classification.confidence,
            "context": {"classifier": "claude"}
        })

        # Check safety rules
        should_flag, safety_reason = self.safety_rules.should_flag_for_human(
            email, classification.category, sender_history
        )

        if should_flag:
            classification.action = EmailAction.FLAG_HUMAN
            classification.reason = safety_reason

        # Apply label/folder based on classification
        await self._apply_label_or_folder(provider, email.message_id, classification)

        # Determine action
        if classification.action == EmailAction.ARCHIVE:
            await provider.archive(email.message_id)
            print(f"Archived: {email.subject}")
            return

        if classification.action == EmailAction.FLAG_HUMAN:
            await provider.apply_label(email.message_id, "Review Required")
            print(f"Flagged for human: {email.subject}")
            return

        # If reply or draft only, generate draft
        if classification.action in [EmailAction.REPLY, EmailAction.DRAFT_ONLY]:
            await self._generate_and_handle_draft(
                email, classification, email_id, classification_id,
                account_id, provider, thread, sender_history
            )

    async def _apply_label_or_folder(
        self,
        provider: EmailProviderInterface,
        message_id: str,
        classification: ClassificationResult
    ):
        """Apply label or folder based on classification"""
        # Map categories to labels/folders
        label_map = {
            EmailCategory.MEETS_REPLY: "Reply",
            EmailCategory.FYI: "FYI",
            EmailCategory.NEWSLETTER: "Newsletter",
            EmailCategory.PROMO: "Promo",
            EmailCategory.RECEIVED: "Receipts",
            EmailCategory.NOTIFICATION: "Notifications",
            EmailCategory.SPAM: "Spam",
            EmailCategory.PERSONAL: "Personal",
            EmailCategory.URGENT: "Urgent",
            EmailCategory.SENSITIVE: "Sensitive"
        }

        label = label_map.get(classification.category, "Inbox")
        await provider.apply_label(message_id, label)

    async def _generate_and_handle_draft(
        self,
        email: EmailMessage,
        classification: ClassificationResult,
        email_id: str,
        classification_id: str,
        account_id: str,
        provider: EmailProviderInterface,
        thread: List[EmailMessage],
        sender_history: List[EmailMessage]
    ):
        """Generate draft and handle based on autonomy mode"""

        # Get user guidelines (placeholder - would be stored in DB)
        user_guidelines = None

        # Generate draft
        draft_content = await self.draft_generator.generate_draft(
            email, thread, user_guidelines, self.voice_profile
        )

        # Create draft object
        draft = Draft(
            email_id=email_id,
            classification_id=classification_id,
            content=draft_content
        )

        # Check worth-sending policy
        should_send, policy_reason = await self.worth_sending_policy.should_send_reply(
            email, classification.category, classification.confidence, sender_history
        )

        if not should_send:
            # Don't send, just save as draft
            draft.status = DraftStatus.PENDING
            draft_id = await self.db.save_draft(draft)
            print(f"Draft saved (not sending): {email.subject} - {policy_reason}")
            return

        # Check rate limit
        rate_limit_info = self.rate_limiter.check_rate_limit(account_id, email.thread_id)
        await self.db.save_rate_limit(account_id, rate_limit_info)

        if not rate_limit_info.can_send:
            draft.status = DraftStatus.PENDING
            draft_id = await self.db.save_draft(draft)
            print(f"Draft saved (rate limited): {email.subject} - {rate_limit_info.reason}")
            return

        # Process through send flow
        status, reason = await self.send_flow.process_draft(draft, classification.action)
        draft.status = status
        draft_id = await self.db.save_draft(draft)

        # Log draft creation
        await self.db.log_audit({
            "email_id": email_id,
            "classification_id": classification_id,
            "draft_id": draft_id,
            "event_type": "draft_created",
            "action": classification.action,
            "reason": reason,
            "context": {"autonomy_mode": self.autonomy_mode.value}
        })

        # If approved, send
        if status == DraftStatus.APPROVED:
            # Create actual draft in email provider
            provider_draft_id = await provider.create_draft(
                to=email.sender_email,
                subject=f"Re: {email.subject}",
                body=draft_content,
                in_reply_to=email.message_id,
                thread_id=email.thread_id
            )

            # Send the draft
            if await provider.send_reply(provider_draft_id):
                await self.db.update_draft_status(draft_id, DraftStatus.SENT)
                self.rate_limiter.record_reply(account_id, email.thread_id)
                print(f"Sent reply: {email.subject}")
            else:
                print(f"Failed to send reply: {email.subject}")

    async def learn_voice_profile(self, account_id: str):
        """Learn user's voice profile from sent emails"""
        provider = self.providers.get(account_id)
        if not provider:
            return

        # Fetch last 50 sent emails (this would need to be implemented in provider)
        # For now, placeholder
        sent_emails = []

        if sent_emails:
            self.voice_profile = await self.voice_learner.learn_from_history(sent_emails)
            await self.db.save_voice_profile(self.user_id, self.voice_profile)
            print("Voice profile updated")

    async def shutdown(self):
        """Shutdown the agent"""
        for provider in self.providers.values():
            await provider.disconnect()
