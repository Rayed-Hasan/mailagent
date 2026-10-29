"""
Real Gmail Ingestion & Synchronization Engine
Fetches genuine messages, deduplicates, classifies with OpenRouter or deterministic fallback,
and updates SQLite storage without fake seeds.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from mailagent.core.types import EmailMessage, ClassificationResult, EmailCategory
from mailagent.core.database import Database
from mailagent.providers.gmail_provider import GmailProvider
from mailagent.classifier.email_classifier import EmailClassifier
from mailagent.core.label_mapper import LabelMapper
from mailagent.demo.demo_provider import get_demo_provider_registry

logger = logging.getLogger("mailagent.sync")


class GmailSyncService:
    """Service for synchronizing a real Gmail account with local storage."""

    def __init__(self, db: Database):
        self.db = db
        self.label_mapper = LabelMapper()
        # Initialize classifier using OpenRouter or fallback provider registry
        registry = get_demo_provider_registry()
        self.classifier = EmailClassifier(provider_registry=registry)

    async def sync_mailbox(
        self,
        account_id: str,
        provider: GmailProvider,
        limit: int = 50,
        folder: str = "INBOX",
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Fetch actual emails from Gmail, deduplicate, classify with AI, and persist.

        Returns:
            Dictionary with sync statistics:
            {
                "fetched": count,
                "new": count,
                "duplicates": count,
                "errors": count,
                "synced_at": iso_timestamp
            }
        """
        stats = {
            "fetched": 0,
            "new": 0,
            "duplicates": 0,
            "errors": 0,
            "unclassified": 0,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Fetch real messages from Gmail
        try:
            messages: List[EmailMessage] = await provider.fetch_emails(
                since=since,
                limit=limit,
                folder=folder,
            )
            stats["fetched"] = len(messages)
        except Exception as e:
            logger.error("Gmail fetch failed (%s)", type(e).__name__)
            stats["error_message"] = "Unable to fetch messages from Gmail"
            return stats

        # 2. Process each real message
        for email in messages:
            try:
                # Check for existing email to avoid duplicate processing
                existing = await self.db.get_email_by_message_id(account_id, email.message_id)
                if existing:
                    stats["duplicates"] += 1
                    continue

                # Save email to database
                email_id = await self.db.save_email(email, account_id)
                stats["new"] += 1

                # Classify email using AI (OpenRouter or labelled fallback)
                classification = await self.classifier.classify(email)
                classification.email_id = email_id
                if classification.is_fallback:
                    stats["unclassified"] += 1
                    logger.warning("Deterministic fallback left a synced message unclassified")
                    continue
                classification_id = await self.db.save_classification(classification)

                # Assign labels
                labels = self.label_mapper.category_to_labels(
                    classification.category,
                    classification.priority_score,
                )
                if labels:
                    await self.db.save_email_labels(email_id, labels, source="system")

            except Exception as e:
                logger.error("Gmail message processing failed (%s)", type(e).__name__)
                stats["errors"] += 1

        return stats
