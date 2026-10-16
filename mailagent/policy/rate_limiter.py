"""
Rate limiting for email replies
"""

from datetime import datetime, timedelta
from typing import Optional

from mailagent.core.types import RateLimitInfo
from mailagent.core.config import settings


class RateLimiter:
    """Rate limiting for auto-replies"""

    def __init__(self):
        self.max_replies_per_hour = settings.max_auto_replies_per_hour
        self.reply_history = {}  # {account_id: [(timestamp, thread_id), ...]}

    def check_rate_limit(
        self,
        account_id: str,
        thread_id: str
    ) -> RateLimitInfo:
        """
        Check if rate limit allows sending a reply.

        Returns:
            RateLimitInfo with can_send flag and reason
        """

        # Get reply history for this account
        history = self.reply_history.get(account_id, [])

        # Clean up old entries (older than 1 hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_history = [
            (ts, tid) for ts, tid in history
            if ts > one_hour_ago
        ]

        # Update history
        self.reply_history[account_id] = recent_history

        # Check hourly limit
        if len(recent_history) >= self.max_replies_per_hour:
            return RateLimitInfo(
                auto_replies_sent_this_hour=len(recent_history),
                last_reply_thread_id=recent_history[-1][1] if recent_history else None,
                can_send=False,
                reason=f"Hourly limit reached ({self.max_replies_per_hour} replies/hour)"
            )

        # Check one reply per thread per day
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        thread_replies = [
            (ts, tid) for ts, tid in recent_history
            if tid == thread_id and ts > one_day_ago
        ]

        if thread_replies:
            return RateLimitInfo(
                auto_replies_sent_this_hour=len(recent_history),
                last_reply_thread_id=thread_id,
                can_send=False,
                reason="Already replied to this thread in the last 24 hours"
        )

        # All checks passed
        return RateLimitInfo(
            auto_replies_sent_this_hour=len(recent_history),
            last_reply_thread_id=recent_history[-1][1] if recent_history else None,
            can_send=True,
            reason=None
        )

    def record_reply(self, account_id: str, thread_id: str) -> None:
        """Record that a reply was sent"""
        if account_id not in self.reply_history:
            self.reply_history[account_id] = []

        self.reply_history[account_id].append((datetime.utcnow(), thread_id))

    def get_reply_count(self, account_id: str) -> int:
        """Get number of replies sent in the last hour"""
        history = self.reply_history.get(account_id, [])
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_history = [
            ts for ts, _ in history
            if ts > one_hour_ago
        ]
        return len(recent_history)
