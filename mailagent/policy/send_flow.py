"""
Send flow with autonomy modes and delayed send
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

from mailagent.core.types import EmailAction, AutonomyMode, DraftStatus, Draft
from mailagent.core.config import settings

logger = logging.getLogger(__name__)


class SendFlow:
    """Handle send flow with autonomy modes and delayed send"""

    def __init__(self, autonomy_mode: AutonomyMode = None, db=None):
        self.autonomy_mode = autonomy_mode or settings.default_autonomy_mode
        self.delay_seconds = settings.delay_send_seconds
        self.db = db
        self.cancelled_drafts = set()
        self.sent_email_ids = set()  # Track emails that have been replied to

    async def process_draft(
        self,
        draft: Draft,
        action: EmailAction
    ) -> tuple[DraftStatus, str]:
        """
        Process a draft based on autonomy mode and action.

        Returns:
            (status, reason)
        """

        # Check for duplicate send (idempotency)
        if action == EmailAction.REPLY and self.check_already_sent(draft.email_id):
            return DraftStatus.REJECTED, "Reply already sent for this email"

        # If action is flag_human, always flag for human
        if action == EmailAction.FLAG_HUMAN:
            return DraftStatus.PENDING, "Flagged for human review (sensitive topic)"

        # If action is archive, no draft needed
        if action == EmailAction.ARCHIVE:
            return DraftStatus.PENDING, "Email archived, no draft needed"

        # If action is draft_only, create draft only
        if action == EmailAction.DRAFT_ONLY:
            return DraftStatus.PENDING, "Draft created, awaiting approval"

        # If action is reply, handle based on autonomy mode
        if action == EmailAction.REPLY:
            return await self._handle_reply(draft)

        return DraftStatus.PENDING, "Unknown action"

    async def _handle_reply(self, draft: Draft) -> tuple[DraftStatus, str]:
        """Handle reply based on autonomy mode"""

        if self.autonomy_mode == AutonomyMode.APPROVE:
            # Approve mode: always require human approval
            return DraftStatus.PENDING, "Draft created, awaiting human approval"

        elif self.autonomy_mode == AutonomyMode.AUTO_SAFE:
            # Auto-safe mode: send only routine replies
            is_routine = self._is_routine_reply(draft)
            if is_routine:
                return await self._schedule_delayed_send(draft)
            else:
                return DraftStatus.PENDING, "Non-routine reply, requires human approval"

        elif self.autonomy_mode == AutonomyMode.AUTO_FULL:
            # Auto-full mode: send everything that passes policy
            return await self._schedule_delayed_send(draft)

        return DraftStatus.PENDING, "Unknown autonomy mode"

    def _is_routine_reply(self, draft: Draft) -> bool:
        """
        Determine if a reply is routine (can be auto-sent in auto_safe mode).

        Routine replies include:
        - Acknowledgments
        - Simple confirmations
        - Scheduling responses
        - Basic information requests
        """

        # Simple heuristic: check draft content
        content_lower = draft.content.lower()

        routine_indicators = [
            "thanks", "thank you", "acknowledged", "received",
            "confirmed", "sure", "okay", "sounds good",
            "let me check", "i'll get back to you", "appreciate"
        ]

        # Check if draft is short and contains routine indicators
        word_count = len(draft.content.split())
        has_routine_indicator = any(indicator in content_lower for indicator in routine_indicators)

        return word_count < 100 and has_routine_indicator

    async def _schedule_delayed_send(self, draft: Draft) -> tuple[DraftStatus, str]:
        """
        Schedule a delayed send with cancelable window.

        Returns:
            (scheduled, reason)
        """

        # Calculate send time
        send_time = datetime.now(timezone.utc) + timedelta(seconds=self.delay_seconds)

        # Update draft with scheduled send time
        draft.scheduled_send_at = send_time

        # If database is available, save the draft with scheduled time
        if self.db:
            draft_id = await self.db.save_draft(draft)
            draft.id = draft_id
            logger.info("Scheduling send for email %s at %s (draft=%s)", draft.email_id, send_time, draft_id)
        else:
            logger.info("Scheduling send for email %s at %s (no db)", draft.email_id, send_time)

        # Check if cancelled during delay window (in-memory check)
        if draft.email_id in self.cancelled_drafts:
            return DraftStatus.CANCELLED, "Send cancelled by user"

        # Check database for cancellation status if available
        if self.db and hasattr(draft, 'id'):
            try:
                draft_data = await self.db.get_draft(draft.id)
                if draft_data and draft_data.get('status') == DraftStatus.CANCELLED.value:
                    return DraftStatus.CANCELLED, "Send cancelled by user"
            except Exception:
                logger.exception("Error checking draft status for email %s", draft.email_id)

        await asyncio.sleep(self.delay_seconds)

        # Check again if cancelled
        if draft.email_id in self.cancelled_drafts:
            return DraftStatus.CANCELLED, "Send cancelled by user"

        # Check database again for cancellation status
        if self.db and hasattr(draft, 'id'):
            try:
                draft_data = await self.db.get_draft(draft.id)
                if draft_data and draft_data.get('status') == DraftStatus.CANCELLED.value:
                    return DraftStatus.CANCELLED, "Send cancelled by user"
            except Exception as e:
                print(f"Error checking draft status: {e}")

        return DraftStatus.APPROVED, f"Scheduled for send at {send_time}"

    def cancel_draft(self, draft_id: str) -> bool:
        """Cancel a pending draft (in-memory)"""
        self.cancelled_drafts.add(draft_id)
        return True

    async def cancel_draft_with_db(self, draft_id: str) -> bool:
        """Cancel a pending draft with database persistence"""
        # Add to in-memory set for immediate effect
        self.cancelled_drafts.add(draft_id)

        # Update database if available
        if self.db:
            try:
                await self.db.update_draft_status(draft_id, DraftStatus.CANCELLED)
                return True
            except Exception:
                logger.exception("Error cancelling draft %s in database", draft_id)
                return False

        return True

    def check_already_sent(self, email_id: str) -> bool:
        """Check if a reply has already been sent for this email"""
        return email_id in self.sent_email_ids

    def record_sent(self, email_id: str) -> None:
        """Record that a reply was sent for this email"""
        self.sent_email_ids.add(email_id)

    def set_autonomy_mode(self, mode: AutonomyMode) -> None:
        """Update autonomy mode"""
        self.autonomy_mode = mode
