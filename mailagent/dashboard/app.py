"""
FastAPI dashboard for monitoring and controls
"""

from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from mailagent.core.database import Database
from mailagent.core.types import AutonomyMode, Draft, DraftStatus
from mailagent.core.config import settings
from mailagent.dashboard.auth import require_dashboard_auth
from mailagent.dashboard.rate_limiter import demo_rate_limiter, get_client_ip
from mailagent.demo.demo_seeder import DemoSeeder
from mailagent.demo.demo_data import get_demo_user_id, get_demo_account_id
from fastapi import Request


app = FastAPI(title="MailAgent Dashboard")

allowed_origins = [
    origin.strip()
    for origin in settings.dashboard_allowed_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

frontend_dir = Path(__file__).resolve().parents[2]


@app.get("/app/{asset}")
async def frontend_asset(asset: str):
    """Serve only the known frontend assets; never expose the repository."""
    allowed_assets = {"index.html", "app.js", "styles.css"}
    if asset not in allowed_assets:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(frontend_dir / asset)


@app.get("/landing.css")
async def landing_styles():
    """Serve the public landing page stylesheet."""
    return FileResponse(frontend_dir / "landing.css")


# Database instance
db = Database(force_demo_mode=settings.public_demo_mode)


@app.on_event("startup")
async def initialize_database() -> None:
    await db.initialize()

    # Seed demo data if in public demo mode
    if settings.public_demo_mode:
        seeder = DemoSeeder(db)
        await seeder.seed_demo_data()


@app.on_event("shutdown")
async def close_database() -> None:
    await db.close()


# Pydantic models
class KillSwitchRequest(BaseModel):
    activate: bool
    reason: Optional[str] = None


class AutonomyModeRequest(BaseModel):
    mode: AutonomyMode


class DraftApprovalRequest(BaseModel):
    draft_id: str
    approve: bool


class ProviderSettingRequest(BaseModel):
    provider: str
    api_key: str
    model_classification: str = ""
    model_drafting: str = ""


class DemoDraftRequest(BaseModel):
    email_id: str


class DemoSendRequest(BaseModel):
    draft_id: str


async def require_account_owner(account_id: str, user_id: str) -> Dict:
    # In demo mode, bypass account owner check for demo account
    if settings.public_demo_mode and account_id == get_demo_account_id() and user_id == get_demo_user_id():
        # Return a minimal demo account object
        return {
            "id": get_demo_account_id(),
            "user_id": get_demo_user_id(),
            "provider": "demo",
            "email_address": "judge@example.com",
            "is_active": True
        }

    account = await db.get_account(account_id)
    if not account or account.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Resource not found")
    return account


def public_account(account: Dict) -> Dict:
    """Return account metadata without decryptable credentials."""
    return {key: value for key, value in account.items() if key != "credentials"}


# Dashboard endpoints
@app.get("/")
async def root():
    """Serve the public product landing page."""
    return FileResponse(frontend_dir / "landing.html")


@app.get("/health")
async def health():
    """Unauthenticated process health check for the hosting platform."""
    return {"status": "ok", "demo_mode": settings.public_demo_mode}


# Demo mode dependency override for public access
async def demo_mode_auth_dependency(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> str:
    """
    In demo mode, return demo user ID without auth (with rate limiting).
    In normal mode, require dashboard auth.
    """
    if settings.public_demo_mode:
        # Apply rate limiting in demo mode
        client_ip = await get_client_ip(request)
        allowed, error = await demo_rate_limiter.check_rate_limit(client_ip)
        if not allowed:
            raise HTTPException(status_code=429, detail=error)

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
        or token != expected_token
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return expected_user_id


@app.get("/api/status", dependencies=[Depends(require_dashboard_auth)])
async def get_status():
    """Get overall system status"""
    kill_switch_active = await db.is_kill_switch_active()

    return {
        "status": "active" if not kill_switch_active else "stopped",
        "kill_switch_active": kill_switch_active,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/privacy", dependencies=[Depends(require_dashboard_auth)])
async def get_privacy():
    """Describe actual data flows; this endpoint performs no network calls."""
    return {
        "storage_backend": settings.storage_backend,
        "task_queue_backend": settings.task_queue_backend,
        "telemetry": False,
        "cloud_inference_requires_explicit_provider_key": True,
        "email_sync_requires_external_provider_network": True,
        "mailagent_hosted_services_used": False,
        "external_destinations": {
            "email_provider": "Configured Gmail/IMAP provider for synchronization and sending",
            "ai_provider": "Only the explicitly configured BYOK or local provider",
        },
    }


@app.get("/api/privacy/export")
async def export_privacy_data(user_id: str = Depends(require_dashboard_auth)):
    """Export local user data without returning credential material."""
    payload = await db.export_user_data(user_id)
    return payload


@app.delete("/api/privacy/data")
async def delete_privacy_data(user_id: str = Depends(require_dashboard_auth)):
    """Delete local user data, including related messages and encrypted settings."""
    try:
        counts = await db.delete_user_data(user_id)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return {"deleted": True, "counts": counts}


@app.get("/api/kill-switch", dependencies=[Depends(require_dashboard_auth)])
async def get_kill_switch():
    """Get kill switch status"""
    active = await db.is_kill_switch_active()
    return {"active": active}


@app.post("/api/kill-switch")
async def toggle_kill_switch(
    request: KillSwitchRequest,
    user_id: str = Depends(require_dashboard_auth),
):
    """Toggle kill switch"""
    if request.activate:
        await db.activate_kill_switch(request.reason or "Manual activation", user_id)
    else:
        await db.deactivate_kill_switch()

    return {"active": request.activate}


@app.get("/api/accounts")
async def get_accounts(
    request: Request,
    user_id: str = Depends(demo_mode_auth_dependency),
):
    """Get all email accounts for a user"""
    client_ip = await get_client_ip(request) if settings.public_demo_mode else None

    try:
        # In demo mode, return demo account
        if settings.public_demo_mode:
            return {
                "accounts": [
                    {
                        "id": get_demo_account_id(),
                        "user_id": get_demo_user_id(),
                        "provider": "demo",
                        "email_address": "judge@example.com",
                        "is_active": True
                    }
                ]
            }

        accounts = await db.get_accounts_by_user(user_id)
        return {"accounts": [public_account(account) for account in accounts]}
    finally:
        if client_ip:
            await demo_rate_limiter.release_request(client_ip)


@app.get("/api/emails")
async def get_emails(
    account_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(require_dashboard_auth),
):
    """Get raw emails for an account with stable pagination."""
    await require_account_owner(account_id, user_id)
    emails = await db.get_emails_by_account(account_id, min(limit, 100), offset)
    return {"emails": emails, "total": len(emails), "limit": limit, "offset": offset}


@app.get("/api/emails/with-classifications")
async def get_emails_with_classifications(
    account_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category: Optional[str] = None,
    min_priority: Optional[int] = Query(default=None, ge=0, le=100),
    max_priority: Optional[int] = Query(default=None, ge=0, le=100),
    label: Optional[str] = None,
    needs_reply: Optional[bool] = None,
    sort_by: str = Query(default="priority", pattern="^(priority|received_at)$"),
    user_id: str = Depends(demo_mode_auth_dependency),
    request: Request = None,
):
    """Get priority inbox data with server-side filtering and pagination."""
    client_ip = await get_client_ip(request) if settings.public_demo_mode else None

    try:
        await require_account_owner(account_id, user_id)
        if (
            min_priority is not None
            and max_priority is not None
            and min_priority > max_priority
        ):
            raise HTTPException(status_code=422, detail="min_priority cannot exceed max_priority")

        result = await db.get_emails_with_classifications(
            account_id=account_id,
            limit=limit,
            offset=offset,
            category=category,
            min_priority=min_priority,
            max_priority=max_priority,
            label=label,
            needs_reply=needs_reply,
            sort_by=sort_by,
        )
        return {**result, "limit": limit, "offset": offset, "sort_by": sort_by}
    finally:
        if client_ip:
            await demo_rate_limiter.release_request(client_ip)


@app.get("/api/emails/{email_id}")
async def get_email(
    request: Request,
    email_id: str,
    user_id: str = Depends(demo_mode_auth_dependency),
):
    """Get a specific email with classification and labels"""
    client_ip = await get_client_ip(request) if settings.public_demo_mode else None

    try:
        email = await db.get_email(email_id)
        account = await db.get_account_for_email(email_id)

        # In demo mode, skip account ownership check
        if not settings.public_demo_mode:
            if not email or not account or account.get("user_id") != user_id:
                raise HTTPException(status_code=404, detail="Resource not found")
        elif not email:
            raise HTTPException(status_code=404, detail="Resource not found")

        # Add classification
        classification = await db.get_classification(email_id)
        if classification:
            email["classification"] = classification

        # Add labels
        labels = await db.get_email_labels(email_id)
        email["labels"] = [label["name"] for label in labels]

        return email
    finally:
        if client_ip:
            await demo_rate_limiter.release_request(client_ip)


@app.get("/api/classifications")
async def get_classifications(
    account_id: str,
    limit: int = 50,
    user_id: str = Depends(require_dashboard_auth),
):
    """Get classifications for an account"""
    await require_account_owner(account_id, user_id)
    return {"classifications": []}


@app.get("/api/drafts")
async def get_drafts(
    request: Request,
    account_id: str,
    status: Optional[str] = None,
    user_id: str = Depends(demo_mode_auth_dependency),
):
    """Get drafts for an account"""
    client_ip = await get_client_ip(request) if settings.public_demo_mode else None

    try:
        await require_account_owner(account_id, user_id)
        drafts = await db.get_pending_drafts(account_id)
        if status:
            drafts = [d for d in drafts if d["status"] == status]
        return {"drafts": drafts}
    finally:
        if client_ip:
            await demo_rate_limiter.release_request(client_ip)


@app.post("/api/drafts/approve")
async def approve_draft(
    http_request: Request,
    approval_request: DraftApprovalRequest,
    user_id: str = Depends(demo_mode_auth_dependency),
):
    """Approve or reject a draft"""
    client_ip = await get_client_ip(http_request) if settings.public_demo_mode else None

    try:
        draft = await db.get_draft(approval_request.draft_id)
        account = (
            await db.get_account_for_email(draft["email_id"])
            if draft
            else None
        )

        # In demo mode, skip account ownership check
        if not settings.public_demo_mode:
            if not draft or not account or account.get("user_id") != user_id:
                raise HTTPException(status_code=404, detail="Resource not found")
        elif not draft:
            raise HTTPException(status_code=404, detail="Resource not found")

        new_status = DraftStatus.APPROVED if approval_request.approve else DraftStatus.REJECTED
        success = await db.update_draft_status(approval_request.draft_id, new_status)

        if not success:
            raise HTTPException(status_code=404, detail="Resource not found")

        # In demo mode, add a note that this is simulated
        response = {"draft_id": approval_request.draft_id, "status": new_status.value}
        if settings.public_demo_mode:
            response["demo_note"] = "This is a simulated action - no email was actually sent"

        return response
    finally:
        if client_ip:
            await demo_rate_limiter.release_request(client_ip)


@app.post("/api/demo/drafts/generate")
async def generate_demo_draft(
    http_request: Request,
    draft_request: DemoDraftRequest,
    user_id: str = Depends(demo_mode_auth_dependency),
):
    """Generate a draft for synthetic mail using optional OpenRouter inference."""
    if not settings.public_demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is not enabled")

    client_ip = await get_client_ip(http_request)
    try:
        email = await db.get_email(draft_request.email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Demo email not found")
        account = await db.get_account_for_email(draft_request.email_id)
        if not account or account.get("id") != get_demo_account_id():
            raise HTTPException(status_code=404, detail="Demo email not found")

        classification = await db.get_classification(draft_request.email_id)
        if not classification:
            raise HTTPException(status_code=409, detail="Email is not classified")

        from mailagent.demo.demo_provider import complete_demo
        from mailagent.llm.base import LLMMessage

        response, used_fallback = await complete_demo(
            [
                LLMMessage(
                    role="user",
                    content=(
                        "Draft a concise professional reply to this synthetic email. "
                        "Mention that this is a demo only if needed.\n\n"
                        f"Subject: {email['subject']}\n\n{email['body']}"
                    ),
                )
            ],
            role="drafting",
            max_tokens=300,
        )
        draft = Draft(
            email_id=draft_request.email_id,
            classification_id=classification["id"],
            content=response.text,
        )
        draft_id = await db.save_draft(draft)
        return {
            "draft_id": draft_id,
            "content": response.text,
            "provider": response.provider,
            "model": response.model,
            "fallback": used_fallback,
            "demo_note": "Synthetic draft only; no external email is sent.",
        }
    finally:
        await demo_rate_limiter.release_request(client_ip)


@app.post("/api/demo/send")
async def simulate_demo_send(
    http_request: Request,
    send_request: DemoSendRequest,
    user_id: str = Depends(demo_mode_auth_dependency),
):
    """Mark a demo draft as sent without contacting SMTP or a mailbox."""
    if not settings.public_demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is not enabled")

    client_ip = await get_client_ip(http_request)
    try:
        draft = await db.get_draft(send_request.draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail="Demo draft not found")
        account = await db.get_account_for_email(draft["email_id"])
        if not account or account.get("id") != get_demo_account_id():
            raise HTTPException(status_code=404, detail="Demo draft not found")
        if draft["status"] != DraftStatus.APPROVED.value:
            raise HTTPException(
                status_code=409,
                detail="Approve the demo draft before simulating a send",
            )
        if not await db.update_draft_status(send_request.draft_id, DraftStatus.SENT):
            raise HTTPException(status_code=404, detail="Demo draft not found")
        return {
            "draft_id": send_request.draft_id,
            "status": DraftStatus.SENT.value,
            "simulated": True,
            "demo_note": "Simulated send only; no email was sent.",
        }
    finally:
        await demo_rate_limiter.release_request(client_ip)


@app.get("/api/audit-log")
async def get_audit_log(
    email_id: Optional[str] = None,
    limit: int = 100,
    user_id: str = Depends(require_dashboard_auth),
):
    """Get audit log"""
    if email_id:
        account = await db.get_account_for_email(email_id)
        if not account or account.get("user_id") != user_id:
            raise HTTPException(status_code=404, detail="Resource not found")
        log = await db.get_audit_log(email_id)
    else:
        # Get recent audit log entries (would need to be implemented)
        log = []

    return {"audit_log": log}


@app.get("/api/voice-profile")
async def get_voice_profile(user_id: str = Depends(require_dashboard_auth)):
    """Get user voice profile"""
    profile = await db.get_voice_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return profile


@app.get("/api/provider-settings")
async def get_provider_settings(user_id: str = Depends(require_dashboard_auth)):
    """Get all provider settings for a user (without API keys)"""
    settings_list = await db.get_provider_settings_by_user(user_id)
    return {"provider_settings": [db.public_provider_setting(s) for s in settings_list]}


@app.get("/api/provider-settings/{provider}")
async def get_provider_setting(
    provider: str, user_id: str = Depends(require_dashboard_auth)
):
    """Get a specific provider setting (without API key)"""
    setting = await db.get_provider_setting(user_id, provider)
    if not setting:
        raise HTTPException(status_code=404, detail="Provider setting not found")
    return db.public_provider_setting(setting)


@app.post("/api/provider-settings")
async def upsert_provider_setting(
    request: ProviderSettingRequest,
    user_id: str = Depends(require_dashboard_auth),
):
    """Save or update a provider setting with encrypted API key"""
    if request.provider not in {"claude", "openai", "google", "ollama"}:
        raise HTTPException(status_code=400, detail="Invalid provider")

    setting_id = await db.save_provider_setting(
        user_id=user_id,
        provider=request.provider,
        api_key=request.api_key,
        model_classification=request.model_classification,
        model_drafting=request.model_drafting,
    )
    return {"id": setting_id, "provider": request.provider}


@app.delete("/api/provider-settings/{provider}")
async def delete_provider_setting(
    provider: str, user_id: str = Depends(require_dashboard_auth)
):
    """Delete a provider setting"""
    success = await db.delete_provider_setting(user_id, provider)
    if not success:
        raise HTTPException(status_code=404, detail="Provider setting not found")
    return {"provider": provider, "deleted": True}


@app.post("/api/provider-settings/{provider}/test")
async def test_provider_setting(
    provider: str, user_id: str = Depends(require_dashboard_auth)
):
    """Test a provider setting by making a simple API call"""
    setting = await db.get_provider_setting(user_id, provider)
    if not setting:
        raise HTTPException(status_code=404, detail="Provider setting not found")

    # Import here to avoid circular dependency
    from mailagent.llm.claude_provider import ClaudeProvider
    from mailagent.llm.base import LLMMessage

    try:
        if provider == "claude":
            llm_provider = ClaudeProvider(api_key=setting["api_key"])
            model = setting.get("model_classification") or "claude-3-5-haiku-latest"
            response = await llm_provider.complete(
                messages=[LLMMessage(role="user", content="Say 'OK'")],
                model=model,
                max_tokens=10,
                timeout_seconds=10,
            )
            return {
                "provider": provider,
                "status": "success",
                "model": model,
                "response": response.text.strip(),
                "tokens": response.total_tokens,
            }
        else:
            raise HTTPException(
                status_code=501, detail=f"Provider {provider} not yet implemented"
            )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Provider test failed: {str(e)}"
        )


@app.get("/api/rate-limits")
async def get_rate_limits(
    account_id: str,
    user_id: str = Depends(require_dashboard_auth),
):
    """Get rate limit info"""
    await require_account_owner(account_id, user_id)
    rate_limit = await db.get_rate_limit(account_id)
    if not rate_limit:
        return {"auto_replies_sent": 0, "limit": settings.max_auto_replies_per_hour}
    return rate_limit


@app.get("/api/stats")
async def get_stats(
    account_id: str,
    user_id: str = Depends(require_dashboard_auth),
):
    """Get statistics for an account"""
    await require_account_owner(account_id, user_id)
    emails = await db.get_emails_by_account(account_id, limit=1000)
    drafts = await db.get_pending_drafts(account_id)

    return {
        "total_emails": len(emails),
        "pending_drafts": len(drafts),
        "account_id": account_id
    }


# Public Demo Endpoints
@app.get("/api/demo/status")
async def get_demo_status(
    request: Request,
    user_id: str = Depends(demo_mode_auth_dependency),
):
    """Get public demo status and configuration"""
    if not settings.public_demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is not enabled")

    try:
        from mailagent.demo.demo_data import get_demo_account_id, get_demo_account_email

        return {
            "demo_mode": True,
            "demo_account_id": get_demo_account_id(),
            "demo_account_email": get_demo_account_email(),
            "ai_provider": "openrouter" if settings.openrouter_api_key else "fallback",
            "ai_model": settings.openrouter_model,
            "note": "This is a public demo with synthetic data. No real emails are sent."
        }
    finally:
        pass  # Rate limiting is handled by demo_mode_auth_dependency


@app.post("/api/demo/reset")
async def reset_demo_data(
    request: Request,
    user_id: str = Depends(demo_mode_auth_dependency),
):
    """Reset demo data to initial state"""
    if not settings.public_demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is not enabled")

    if not settings.demo_reset_endpoint_enabled:
        raise HTTPException(status_code=403, detail="Demo reset is disabled")

    try:
        seeder = DemoSeeder(db)
        counts = await seeder.reset_demo_data()

        return {
            "reset": True,
            "counts": counts,
            "message": "Demo data has been reset to initial state"
        }
    finally:
        pass  # Rate limiting is handled by demo_mode_auth_dependency


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.dashboard_host,
        port=settings.dashboard_port
    )
