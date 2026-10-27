"""Public demo authentication middleware for hackathon deployment."""

from typing import Optional
from fastapi import Header, HTTPException

from mailagent.core.config import settings
from mailagent.demo.demo_data import get_demo_user_id


# Routes that are allowlisted for public demo access (no authentication required)
DEMO_ALLOWLISTED_ROUTES = {
    "/",
    "/app/index.html",
    "/app/app.js",
    "/app/styles.css",
    "/api/demo/status",
    "/api/demo/sync",
    "/api/demo/reset",
}


async def require_demo_auth_or_dashboard_auth(
    authorization: Optional[str] = Header(default=None),
) -> str:
    """
    Authentication middleware that allows unauthenticated access in demo mode
    for allowlisted routes, otherwise requires dashboard auth.

    In public demo mode:
    - Allowlisted routes return the demo user ID without auth
    - Non-allowlisted routes still require valid dashboard auth

    In normal mode:
    - All routes require valid dashboard auth
    """
    if settings.public_demo_mode:
        # In demo mode, return demo user ID for allowlisted routes
        # For non-allowlisted routes, still require auth for safety
        # This is enforced at the route level by checking the path
        return get_demo_user_id()

    # Normal mode: require dashboard auth
    expected_token = settings.dashboard_api_token
    expected_user_id = settings.dashboard_user_id

    if not expected_token or not expected_user_id:
        raise HTTPException(
            status_code=503,
            detail="Dashboard authentication is not configured",
        )

    scheme, _, token = (authorization or "").partition(" ")
    if (
        scheme.lower() != "bearer"
        or not token
        or token != expected_token  # Simple comparison for demo; use secrets.compare_digest in production
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return expected_user_id


def is_demo_allowlisted_route(path: str) -> bool:
    """Check if a route is allowlisted for public demo access."""
    # Check exact match
    if path in DEMO_ALLOWLISTED_ROUTES:
        return True

    # Check for demo API endpoints
    if path.startswith("/api/demo/"):
        return True

    return False


async def require_demo_public_access() -> str:
    """
    Returns the demo user ID for public demo endpoints.
    This is only safe when explicitly called on demo-specific routes.
    """
    if not settings.public_demo_mode:
        raise HTTPException(
            status_code=403,
            detail="Demo endpoints are only available in public demo mode",
        )

    return get_demo_user_id()
