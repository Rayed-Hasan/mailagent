"""
Send flow with autonomy modes and delayed send
"""

import asyncio
from typing import Optional
from datetime import datetime, timedelta

from mailagent.core.types import EmailAction, AutonomyMode, DraftStatus, Draft
from mailagent.core.config import settings


class SendFlow:
    """Handle send flow with autonomy modes and delayed send"""

    def __init__(self, autonomy_mode: AutonomyMode = None):
        self.autonomy_mode = autonomy_mode or settings.default_autonomy_mode
        self.delay_seconds = settings.delay_send_seconds
        self.cancelled_drafts = set()

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
        send_time = datetime.utcnow() + timedelta(seconds=self.delay_seconds)

        # In a real implementation, this would schedule a background task
        # For now, we'll simulate the delay
        print(f"Scheduling send for {draft.email_id} at {send_time}")

        # Check if cancelled during delay window
        if draft.email_id in self.cancelled_drafts:
            return DraftStatus.CANCELLED, "Send cancelled by user"

        # Simulate delay
        await asyncio.sleep(min(self.delay_seconds, 1))  # Cap at 1 second for testing

        # Check again if cancelled
        if draft.email_id in self.cancelled_drafts:
            return DraftStatus.CANCELLED, "Send cancelled by user"

        return DraftStatus.APPROVED, f"Scheduled for send at {send_time}"

    def cancel_draft(self, draft_id: str) -> bool:
        """Cancel a pending draft"""
        self.cancelled_drafts.add(draft_id)
        return True

    def set_autonomy_mode(self, mode: AutonomyMode) -> None:
        """Update autonomy mode"""
        self.autonomy_mode = mode
