"""
FastAPI dashboard for monitoring and controls
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone

logger = logging.getLogger("mailagent.dashboard")

from mailagent.core.database import Database
from mailagent.core.types import AutonomyMode, Draft, DraftStatus
from mailagent.core.config import settings
from mailagent.dashboard.auth import require_dashboard_auth
from mailagent.dashboard.rate_limiter import demo_rate_limiter, get_client_ip
from mailagent.demo.demo_seeder import DemoSeeder
from mailagent.demo.demo_data import (
    get_demo_user_id,
    get_demo_account_id,
    get_demo_account_email,
)
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


# Real Gmail Provider instance for demo if connected
demo_gmail_provider: Optional[Any] = None
demo_sync_service: Optional[Any] = None
demo_mailbox_status: Dict[str, Any] = {
    "connected": False,
    "email_address": None,
    "last_sync": None,
    "last_error": None,
    "message_count": 0,
}


@app.on_event("startup")
async def initialize_database() -> None:
    global demo_gmail_provider, demo_sync_service, demo_mailbox_status
    await db.initialize()

    # In public demo mode, check for owner-configured real Gmail mailbox
    if settings.public_demo_mode:
        from mailagent.mail.sync_service import GmailSyncService
        from mailagent.providers.gmail_provider import GmailProvider
        from mailagent.demo.demo_data import get_demo_account_id, get_demo_account_email, get_demo_user_id

        demo_sync_service = GmailSyncService(db)

        # 1. Check if owner provided persistent Gmail refresh token via environment
        if settings.demo_gmail_refresh_token:
            client_id = settings.demo_gmail_client_id or settings.google_client_id
            client_secret = settings.demo_gmail_client_secret or settings.google_client_secret
            token_dict = {
                "refresh_token": settings.demo_gmail_refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            demo_gmail_provider = GmailProvider(token_dict)
            connected = await demo_gmail_provider.connect()
            if connected:
                profile = await demo_gmail_provider.get_user_profile()
                email_addr = (profile.get("emailAddress") if profile else None) or settings.demo_gmail_email or get_demo_account_email()
                demo_mailbox_status["connected"] = True
                demo_mailbox_status["email_address"] = email_addr
                account_id = get_demo_account_id()

                # Ensure account exists in storage
                existing_acc = await db.get_account(account_id)
                if not existing_acc:
                    await db.save_account(
                        user_id=get_demo_user_id(),
                        provider="gmail",
                        email_address=email_addr,
                        credentials=token_dict,
                    )

                # Sync real messages
                sync_stats = await demo_sync_service.sync_mailbox(
                    account_id=account_id,
                    provider=demo_gmail_provider,
                    limit=50,
                )
                demo_mailbox_status["last_sync"] = sync_stats.get("synced_at")
            else:
                demo_mailbox_status["connected"] = False
                demo_mailbox_status["last_error"] = "Failed to connect to Gmail with provided credentials"
        else:
            # Check if account was previously saved in SQLite
            account_id = get_demo_account_id()
            acc = await db.get_account(account_id)
            if acc and acc.get("credentials") and acc.get("provider") == "gmail":
                demo_gmail_provider = GmailProvider(acc["credentials"])
                if await demo_gmail_provider.connect():
                    demo_mailbox_status["connected"] = True
                    demo_mailbox_status["email_address"] = acc.get("email_address")
                    # Sync
                    sync_stats = await demo_sync_service.sync_mailbox(
                        account_id=account_id,
                        provider=demo_gmail_provider,
                        limit=50,
                    )
                    demo_mailbox_status["last_sync"] = sync_stats.get("synced_at")


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
    # In demo mode, bypass account owner check for configured demo account
    if settings.public_demo_mode and account_id == get_demo_account_id() and user_id == get_demo_user_id():
        # Return the demo account representation
        email_addr = demo_mailbox_status.get("email_address") or get_demo_account_email()
        provider_name = "gmail" if demo_mailbox_status.get("connected") else "demo"
        return {
            "id": get_demo_account_id(),
            "user_id": get_demo_user_id(),
            "provider": provider_name,
            "email_address": email_addr,
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
        # In demo mode, return the single configured demo mailbox
        if settings.public_demo_mode:
            email_addr = demo_mailbox_status.get("email_address") or get_demo_account_email()
            provider_name = "gmail" if demo_mailbox_status.get("connected") else "demo"
            return {
                "accounts": [
                    {
                        "id": get_demo_account_id(),
                        "user_id": get_demo_user_id(),
                        "provider": provider_name,
                        "email_address": email_addr,
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

        try:
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
        except Exception:
            logger.exception(
                "Failed to load classified emails for account_id=%s",
                account_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Unable to load classified emails",
            ) from None
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

        # Send only the minimum email content necessary for inference
        prompt_content = (
            "You are a professional email assistant. Draft a concise, helpful, and professional reply "
            "to the following message. Be polite and address any direct questions.\n\n"
            f"Subject: {email.get('subject', '')}\n\n"
            f"{email.get('body', '')[:1500]}"
        )

        response, used_fallback = await complete_demo(
            [
                LLMMessage(
                    role="user",
                    content=prompt_content,
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
            "note": "Draft generated. Sending requires owner approval.",
        }
    finally:
        await demo_rate_limiter.release_request(client_ip)


@app.post("/api/demo/send")
async def simulate_demo_send(
    http_request: Request,
    send_request: DemoSendRequest,
    user_id: str = Depends(demo_mode_auth_dependency),
):
    """
    Handle send requests in public demo mode.
    Anonymous sending through owner's real Gmail is disabled by default to protect the account.
    """
    if not settings.public_demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is not enabled")

    # In public demo mode with real Gmail, prevent anonymous users from sending arbitrary emails
    if not settings.demo_allow_public_send:
        raise HTTPException(
            status_code=403,
            detail="Public email sending is disabled to protect the demo mailbox. Judges can review and generate drafts.",
        )

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
                detail="Approve the demo draft before sending",
            )
        if not await db.update_draft_status(send_request.draft_id, DraftStatus.SENT):
            raise HTTPException(status_code=404, detail="Demo draft not found")
        return {
            "draft_id": send_request.draft_id,
            "status": DraftStatus.SENT.value,
            "simulated": True,
            "note": "Draft status updated to sent.",
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
    """Get public demo status and configuration with real mailbox status"""
    if not settings.public_demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is not enabled")

    try:
        from mailagent.demo.demo_data import get_demo_account_id, get_demo_account_email

        account_id = get_demo_account_id()
        is_connected = demo_mailbox_status.get("connected", False)
        email_addr = demo_mailbox_status.get("email_address") or get_demo_account_email()

        # Count emails in demo mailbox
        emails = await db.get_emails_by_account(account_id, limit=1000)
        email_count = len(emails)

        return {
            "demo_mode": True,
            "demo_account_id": account_id,
            "demo_account_email": email_addr,
            "gmail_connected": is_connected,
            "connection_status": "connected" if is_connected else "disconnected",
            "message_count": email_count,
            "last_sync": demo_mailbox_status.get("last_sync"),
            "last_error": demo_mailbox_status.get("last_error"),
            "ai_provider": "openrouter" if settings.openrouter_api_key else "fallback",
            "ai_model": settings.openrouter_model,
            "can_public_send": settings.demo_allow_public_send,
            "note": "Messages in the public demo are retrieved from the dedicated demo mailbox."
        }
    finally:
        pass  # Rate limiting is handled by demo_mode_auth_dependency


@app.post("/api/demo/sync")
async def trigger_demo_sync(
    request: Request,
    user_id: str = Depends(demo_mode_auth_dependency),
):
    """Trigger a synchronization of the dedicated Gmail account (safe for judges to refresh)"""
    global demo_gmail_provider, demo_sync_service, demo_mailbox_status
    if not settings.public_demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is not enabled")

    client_ip = await get_client_ip(request)
    try:
        from mailagent.demo.demo_data import get_demo_account_id
        account_id = get_demo_account_id()

        if not demo_gmail_provider or not demo_mailbox_status.get("connected"):
            return {
                "synced": False,
                "message": "Real Gmail mailbox is not yet connected by owner. Run owner OAuth setup or set DEMO_GMAIL_REFRESH_TOKEN.",
                "account_id": account_id,
                "fetched": 0,
                "new": 0,
            }

        if not demo_sync_service:
            from mailagent.mail.sync_service import GmailSyncService
            demo_sync_service = GmailSyncService(db)

        stats = await demo_sync_service.sync_mailbox(
            account_id=account_id,
            provider=demo_gmail_provider,
            limit=50,
        )
        demo_mailbox_status["last_sync"] = stats.get("synced_at")
        return {
            "synced": True,
            "stats": stats,
            "account_id": account_id,
        }
    finally:
        await demo_rate_limiter.release_request(client_ip)


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


# =========================================================================
# Protected Owner-Only Mailbox Setup Endpoints (Require DASHBOARD_API_TOKEN)
# Anonymous visitors/judges CANNOT access these endpoints.
# =========================================================================

# In-memory OAuth state storage with timestamps to prevent CSRF
_oauth_states: Dict[str, datetime] = {}


@app.get("/api/owner/gmail/auth-url", dependencies=[Depends(require_dashboard_auth)])
async def get_owner_gmail_auth_url():
    """
    Owner-only endpoint: generate Google OAuth authorization URL for the dedicated demo mailbox.
    Never accessible to anonymous judges.
    """
    import secrets
    from mailagent.providers.gmail_provider import GmailOAuthFlow, DEFAULT_SCOPES

    client_id = settings.demo_gmail_client_id or settings.google_client_id
    client_secret = settings.demo_gmail_client_secret or settings.google_client_secret
    redirect_uri = settings.demo_gmail_redirect_uri or settings.google_redirect_uri

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail="Google Client ID and Secret must be configured in environment (GOOGLE_CLIENT_ID or DEMO_GMAIL_CLIENT_ID)",
        )

    # Generate cryptographic state token
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = datetime.now(timezone.utc)

    # Purge old states (> 15 min)
    now = datetime.now(timezone.utc)
    for k in list(_oauth_states.keys()):
        if (now - _oauth_states[k]).total_seconds() > 900:
            _oauth_states.pop(k, None)

    try:
        auth_url = GmailOAuthFlow.get_authorization_url(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=DEFAULT_SCOPES,
            state=state,
        )
    except Exception:
        logger.exception(
            "Failed to generate Gmail OAuth authorization URL for redirect_uri=%s",
            redirect_uri,
        )
        _oauth_states.pop(state, None)
        raise HTTPException(
            status_code=502,
            detail="Unable to initialize Gmail OAuth",
        ) from None

    return {
        "auth_url": auth_url,
        "redirect_uri": redirect_uri,
        "scopes": DEFAULT_SCOPES,
        "state": state,
    }


class OwnerCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


@app.get("/auth/gmail/callback")
async def receive_gmail_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """
    Receive Google's browser redirect and return the code for the authenticated
    owner API to exchange. The state remains stored until that API call.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth failed: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth authorization code")
    if not state or state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    return {
        "message": "Authorization received. Submit this code to POST /api/owner/gmail/callback with the owner token.",
        "code": code,
        "state": state,
    }


@app.post("/api/owner/gmail/callback", dependencies=[Depends(require_dashboard_auth)])
async def handle_owner_gmail_callback(payload: OwnerCallbackRequest):
    """
    Owner-only endpoint: exchange authorization code for refresh token, save credentials,
    and initialize real Gmail synchronization.
    Never accessible to anonymous judges.
    """
    global demo_gmail_provider, demo_sync_service, demo_mailbox_status
    from mailagent.providers.gmail_provider import GmailOAuthFlow, GmailProvider, DEFAULT_SCOPES
    from mailagent.demo.demo_data import get_demo_account_id, get_demo_user_id
    from mailagent.mail.sync_service import GmailSyncService

    # Validate state if passed
    if payload.state:
        if payload.state not in _oauth_states:
            raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
        _oauth_states.pop(payload.state, None)

    client_id = settings.demo_gmail_client_id or settings.google_client_id
    client_secret = settings.demo_gmail_client_secret or settings.google_client_secret
    redirect_uri = settings.demo_gmail_redirect_uri or settings.google_redirect_uri

    try:
        tokens = GmailOAuthFlow.exchange_code_for_token(
            code=payload.code,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=DEFAULT_SCOPES,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to exchange OAuth code: {str(e)}")

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        # Warning: if user already authorized without prompt=consent, refresh_token might not be returned
        logger.warning("No refresh_token returned by Google OAuth. Re-run with prompt=consent.")

    # Initialize provider and get actual email address
    provider = GmailProvider(tokens, scopes=DEFAULT_SCOPES)
    if not await provider.connect():
        raise HTTPException(status_code=400, detail="Failed to connect to Gmail with returned tokens")

    profile = await provider.get_user_profile()
    email_address = profile.get("emailAddress", "dedicated-demo@gmail.com") if profile else "dedicated-demo@gmail.com"

    # Save to database
    account_id = get_demo_account_id()
    user_id = get_demo_user_id()

    await db.save_account(
        user_id=user_id,
        provider="gmail",
        email_address=email_address,
        credentials=tokens,
    )

    demo_gmail_provider = provider
    demo_mailbox_status["connected"] = True
    demo_mailbox_status["email_address"] = email_address

    # Initial sync
    demo_sync_service = GmailSyncService(db)
    sync_stats = await demo_sync_service.sync_mailbox(
        account_id=account_id,
        provider=provider,
        limit=50,
    )
    demo_mailbox_status["last_sync"] = sync_stats.get("synced_at")

    return {
        "status": "connected",
        "email_address": email_address,
        "account_id": account_id,
        "sync_stats": sync_stats,
        "has_refresh_token": bool(refresh_token),
        # Do NOT expose the secret tokens in the response!
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.dashboard_host,
        port=settings.dashboard_port
    )
