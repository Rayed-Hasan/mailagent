"""
Main email agent orchestrator
"""

import asyncio
import logging
from typing import List, Optional
from datetime import datetime

from mailagent.core.types import (
    EmailMessage, EmailCategory, EmailAction, AutonomyMode, DraftStatus,
    ClassificationResult, Draft, UserVoiceProfile, RateLimitInfo
)
from mailagent.core.database import Database
from mailagent.core.prefilter import Prefilter
from mailagent.core.label_mapper import LabelMapper
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
from mailagent.llm.registry import ProviderRegistry, ModelSlot
from mailagent.llm.claude_provider import ClaudeProvider
from mailagent.llm.groq_provider import GroqProvider

logger = logging.getLogger(__name__)


class EmailAgent:
    """Main email agent that orchestrates all components"""

    def __init__(self, user_id: str, autonomy_mode: AutonomyMode = None, storage_backend: str = None):
        self.user_id = user_id
        self.autonomy_mode = autonomy_mode or settings.default_autonomy_mode
        self._autonomy_mode_explicit = autonomy_mode is not None

        # Initialize components
        self.db = Database(storage_backend=storage_backend)
        self.provider_registry = ProviderRegistry()
        self.prefilter = Prefilter()
        self.classifier = EmailClassifier(provider_registry=self.provider_registry)
        self.voice_learner = VoiceProfileLearner()
        self.draft_generator = DraftGenerator(provider_registry=self.provider_registry)
        self.worth_sending_policy = WorthSendingPolicy()
        self.send_flow = SendFlow(self.autonomy_mode, db=self.db)
        self.safety_rules = SafetyRules()
        self.rate_limiter = RateLimiter()
        self.label_mapper = LabelMapper()

        # Cache
        self.voice_profile: Optional[UserVoiceProfile] = None
        self.providers: dict = {}

    async def initialize(self):
        """Initialize the agent"""
        # Initialize storage backend if needed
        await self.db.initialize()

        # Sending is opt-in and still requires every hard policy check to pass.
        enabled = await self.db.get_auto_reply_enabled(self.user_id)
        if not self._autonomy_mode_explicit:
            self.autonomy_mode = AutonomyMode.AUTO_FULL if enabled else AutonomyMode.APPROVE
        self.send_flow.set_autonomy_mode(self.autonomy_mode)

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

        # Load provider settings and configure registry
        await self._load_provider_settings()

        # Load email accounts
        accounts = await self.db.get_accounts_by_user(self.user_id)
        for account in accounts:
            await self._load_provider(account)

    async def _load_provider_settings(self):
        """Load LLM provider settings from database and configure registry"""
        provider_settings = await self.db.get_provider_settings_by_user(self.user_id)

        for setting in provider_settings:
            provider_name = setting["provider"]
            api_key = setting["api_key"]
            model_classification = setting.get("model_classification") or settings.model_classification
            model_drafting = setting.get("model_drafting") or settings.model_drafting

            # Register provider instance
            if provider_name == "claude":
                llm_provider = ClaudeProvider(api_key=api_key)
                self.provider_registry.register(llm_provider)

                # Configure model slots
                self.provider_registry.set_slot(
                    ModelSlot(role="classification", provider="claude", model=model_classification)
                )
                self.provider_registry.set_slot(
                    ModelSlot(role="drafting", provider="claude", model=model_drafting)
                )
            # Additional providers (openai, google, ollama) can be added here

        if settings.groq_api_key and not self.provider_registry.configured_slots():
            provider = GroqProvider(api_key=settings.groq_api_key)
            self.provider_registry.register(provider)
            self.provider_registry.set_slot(
                ModelSlot(role="classification", provider="groq", model=settings.groq_model)
            )
            self.provider_registry.set_slot(
                ModelSlot(role="drafting", provider="groq", model=settings.groq_model)
            )

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

        # Prefilter: check for bulk/newsletter/important messages
        # Convert EmailMessage to MailMessage for prefilter
        from mailagent.mail.base import MailMessage
        mail_message = MailMessage(
            message_id=email.message_id,
            thread_id=email.thread_id,
            sender=email.sender,
            sender_email=email.sender_email,
            recipients=email.recipients,
            subject=email.subject,
            text_body=email.body,
            html_body=None,
            headers=email.raw_headers,
            received_at=email.received_at,
        )
        prefilter_result = self.prefilter.inspect(mail_message)

        # Log prefilter decision
        await self.db.log_audit({
            "email_id": email_id,
            "event_type": "prefilter",
            "context": {
                "skip_model": prefilter_result.skip_model,
                "reason_code": prefilter_result.reason_code,
                "category": prefilter_result.category,
                "is_important": prefilter_result.is_important,
            },
            "reason": prefilter_result.reason,
        })

        # If prefilter marked as important, skip model but preserve for review
        # If prefilter marked as bulk, use deterministic classification
        if prefilter_result.skip_model and not prefilter_result.is_important:
            # Use deterministic classification based on prefilter category
            classification = self._deterministic_classification(
                email_id, prefilter_result.category, prefilter_result.reason
            )
        else:
            # Fetch thread and sender history for classification
            thread = await provider.fetch_thread(email.thread_id) if email.thread_id else []
            sender_history = await provider.fetch_sender_history(email.sender_email)

            # Classify email using LLM
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
            "context": {
                "prefilter_skip": prefilter_result.skip_model,
                "prefilter_reason_code": prefilter_result.reason_code,
                "priority_score": classification.priority_score,
            }
        })

        # Check safety rules
        should_flag, safety_reason = self.safety_rules.should_flag_for_human(
            email, classification.category, sender_history
        )

        if should_flag:
            classification.action = EmailAction.FLAG_HUMAN
            classification.reason = safety_reason

        # Apply labels based on classification
        labels = self.label_mapper.category_to_labels(
            classification.category, classification.priority_score
        )
        await self.db.save_email_labels(email_id, labels, source="system")

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

    def _deterministic_classification(
        self, email_id: str, prefilter_category: str, reason: str
    ) -> ClassificationResult:
        """Create deterministic classification from prefilter result."""
        category_map = {
            "newsletter": EmailCategory.NEWSLETTER,
            "notification": EmailCategory.NOTIFICATION,
            "promo": EmailCategory.PROMO,
        }
        action_map = {
            "newsletter": EmailAction.ARCHIVE,
            "notification": EmailAction.ARCHIVE,
            "promo": EmailAction.ARCHIVE,
        }

        category = category_map.get(prefilter_category, EmailCategory.FYI)
        action = action_map.get(prefilter_category, EmailAction.ARCHIVE)

        return ClassificationResult(
            email_id=email_id,
            category=category,
            priority_score=20,
            action=action,
            confidence=0.95,
            reason=reason,
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
        if draft_content is None:
            # Keep provider failures from becoming invalid Draft models or
            # entering the send flow. The email remains classified for retry.
            logger.warning("Draft generation failed; message remains classified without a draft")
            return

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
        draft_id = draft.id or await self.db.save_draft(draft)
        if status != DraftStatus.CANCELLED:
            await self.db.update_draft_status(draft_id, status)

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

        # Send only after the configured delay and a final kill-switch check.
        if status == DraftStatus.APPROVED:
            if settings.public_demo_mode or await self.db.is_kill_switch_active():
                await self.db.update_draft_status(draft_id, DraftStatus.CANCELLED)
                logger.info("Automatic reply blocked by demo mode or kill switch")
                return

            try:
                provider_draft_id = await provider.create_draft(
                    to=email.sender_email,
                    subject=f"Re: {email.subject}",
                    body=draft_content,
                    in_reply_to=email.raw_headers.get("Message-ID") or email.in_reply_to,
                    thread_id=email.thread_id,
                    references=email.references,
                )
            except Exception as exc:
                await self.db.update_draft_status(draft_id, DraftStatus.PENDING)
                logger.warning("Provider draft creation failed (%s); reply remains pending", type(exc).__name__)
                return

            if not provider_draft_id:
                await self.db.update_draft_status(draft_id, DraftStatus.PENDING)
                logger.warning("Email provider did not create a draft; reply remains pending")
                return

            try:
                sent = await provider.send_reply(provider_draft_id)
            except Exception as exc:
                sent = False
                logger.warning("Provider send failed (%s); reply remains pending", type(exc).__name__)

            if not sent:
                await self.db.update_draft_status(draft_id, DraftStatus.PENDING)
                logger.warning("Provider did not confirm the send; reply remains pending")
                return

            await self.db.update_draft_status(draft_id, DraftStatus.SENT)
            self.rate_limiter.record_reply(account_id, email.thread_id)
            self.send_flow.record_sent(email_id)
            await self.db.log_audit({
                "email_id": email_id,
                "classification_id": classification_id,
                "draft_id": draft_id,
                "event_type": "reply_sent",
                "action": classification.action,
                "reason": reason,
                "context": {
                    "autonomy_mode": self.autonomy_mode.value,
                    "confidence": classification.confidence,
                    "category": classification.category.value,
                },
            })
            logger.info("Automatic reply sent for %s", email.subject)

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
