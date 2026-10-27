"""
Unit tests for rate limiter
"""

import pytest
from datetime import datetime, timedelta, timezone
from mailagent.policy.rate_limiter import RateLimiter
from mailagent.core.types import RateLimitInfo


@pytest.fixture
def rate_limiter():
    return RateLimiter()


def test_initial_rate_limit(rate_limiter):
    """Test that initial rate limit allows sending"""
    info = rate_limiter.check_rate_limit("account_123", "thread_123")
    assert info.can_send is True
    assert info.auto_replies_sent_this_hour == 0
    assert info.reason is None


def test_record_reply_increases_count(rate_limiter):
    """Test that recording a reply increases the count"""
    rate_limiter.record_reply("account_123", "thread_123")
    info = rate_limiter.check_rate_limit("account_123", "thread_456")
    assert info.auto_replies_sent_this_hour == 1


def test_hourly_limit_enforced(rate_limiter):
    """Test that hourly limit is enforced"""
    max_replies = rate_limiter.max_replies_per_hour

    # Record max replies
    for i in range(max_replies):
        rate_limiter.record_reply("account_123", f"thread_{i}")

    # Next reply should be blocked
    info = rate_limiter.check_rate_limit("account_123", "thread_new")
    assert info.can_send is False
    assert "Hourly limit reached" in info.reason


def test_one_reply_per_thread_per_day(rate_limiter):
    """Test that only one reply per thread per day is allowed"""
    # Record a reply to thread_123
    rate_limiter.record_reply("account_123", "thread_123")

    # Try to reply to same thread again
    info = rate_limiter.check_rate_limit("account_123", "thread_123")
    assert info.can_send is False
    assert "Already replied to this thread" in info.reason


def test_different_accounts_separate_limits(rate_limiter):
    """Test that different accounts have separate rate limits"""
    # Record reply for account_1
    rate_limiter.record_reply("account_1", "thread_123")

    # account_2 should still be able to send
    info = rate_limiter.check_rate_limit("account_2", "thread_456")
    assert info.can_send is True


def test_old_entries_cleaned_up(rate_limiter):
    """Test that old entries are cleaned up"""
    # Record a reply 2 hours ago
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    rate_limiter.reply_history["account_123"] = [(old_time, "thread_123")]

    # Check rate limit should clean up old entries
    info = rate_limiter.check_rate_limit("account_123", "thread_456")
    assert info.auto_replies_sent_this_hour == 0


def test_get_reply_count(rate_limiter):
    """Test getting reply count"""
    rate_limiter.record_reply("account_123", "thread_123")
    rate_limiter.record_reply("account_123", "thread_456")

    count = rate_limiter.get_reply_count("account_123")
    assert count == 2
