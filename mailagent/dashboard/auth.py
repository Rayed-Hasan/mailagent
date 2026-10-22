"""Dashboard authentication for the single-principal deployment profile."""

import secrets
from typing import Optional

from fastapi import Header, HTTPException

from mailagent.core.config import settings


async def require_dashboard_auth(
    authorization: Optional[str] = Header(default=None),
) -> str:
    """Authenticate the configured dashboard principal without fallbacks."""
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
        or not secrets.compare_digest(token, expected_token)
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return expected_user_id
