"""Rate limiting for public demo endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from collections import defaultdict
import asyncio

from mailagent.core.config import settings


class DemoRateLimiter:
    """In-memory rate limiter for public demo API calls."""

    def __init__(self):
        self.request_history: Dict[str, list] = defaultdict(list)
        self.lock = asyncio.Lock()

    async def check_rate_limit(self, client_ip: str) -> tuple[bool, Optional[str]]:
        """
        Check if a client is within rate limits.

        Returns:
            Tuple of (allowed, error_message)
        """
        if not settings.public_demo_mode:
            return True, None

        async with self.lock:
            now = datetime.now(timezone.utc)
            one_minute_ago = now - timedelta(minutes=1)

            # Clean old requests
            self.request_history[client_ip] = [
                ts for ts in self.request_history[client_ip]
                if ts > one_minute_ago
            ]

            # Check rate limit
            if len(self.request_history[client_ip]) >= settings.demo_rate_limit_per_minute:
                return False, f"Rate limit exceeded: {settings.demo_rate_limit_per_minute} requests per minute"

            # Record this request
            self.request_history[client_ip].append(now)

            return True, None

    async def release_request(self, client_ip: str) -> None:
        """Release a request slot (no-op in simplified implementation)."""
        # Simplified: no-op since we just track per-minute request count
        pass


# Global rate limiter instance
demo_rate_limiter = DemoRateLimiter()


async def get_client_ip(request) -> str:
    """Extract client IP from request."""
    # Try X-Forwarded-For header first (for reverse proxy setups)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Fall back to direct client IP
    if hasattr(request, "client"):
        return request.client.host if request.client else "unknown"

    return "unknown"
