"""
FastAPI dashboard for monitoring and controls
"""

from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from mailagent.core.database import Database
from mailagent.core.types import AutonomyMode, DraftStatus
from mailagent.core.config import settings
from mailagent.dashboard.auth import require_dashboard_auth


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

# Database instance
db = Database()


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


async def require_account_owner(account_id: str, user_id: str) -> Dict:
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
    """Root endpoint"""
    return {
        "service": "MailAgent Dashboard",
        "version": "0.1.0",
        "status": "running"
    }


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
async def get_accounts(user_id: str = Depends(require_dashboard_auth)):
    """Get all email accounts for a user"""
    accounts = await db.get_accounts_by_user(user_id)
    return {"accounts": [public_account(account) for account in accounts]}


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
    user_id: str = Depends(require_dashboard_auth),
):
    """Get priority inbox data with server-side filtering and pagination."""
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


@app.get("/api/emails/{email_id}")
async def get_email(email_id: str, user_id: str = Depends(require_dashboard_auth)):
    """Get a specific email with classification and labels"""
    email = await db.get_email(email_id)
    account = await db.get_account_for_email(email_id)
    if not email or not account or account.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Add classification
    classification = await db.get_classification(email_id)
    if classification:
        email["classification"] = classification

    # Add labels
    labels = await db.get_email_labels(email_id)
    email["labels"] = [label["name"] for label in labels]

    return email


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
    account_id: str,
    status: Optional[str] = None,
    user_id: str = Depends(require_dashboard_auth),
):
    """Get drafts for an account"""
    await require_account_owner(account_id, user_id)
    drafts = await db.get_pending_drafts(account_id)
    if status:
        drafts = [d for d in drafts if d["status"] == status]
    return {"drafts": drafts}


@app.post("/api/drafts/approve")
async def approve_draft(
    request: DraftApprovalRequest,
    user_id: str = Depends(require_dashboard_auth),
):
    """Approve or reject a draft"""
    draft = await db.get_draft(request.draft_id)
    account = (
        await db.get_account_for_email(draft["email_id"])
        if draft
        else None
    )
    if not draft or not account or account.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Resource not found")

    new_status = DraftStatus.APPROVED if request.approve else DraftStatus.REJECTED
    success = await db.update_draft_status(request.draft_id, new_status)

    if not success:
        raise HTTPException(status_code=404, detail="Resource not found")

    return {"draft_id": request.draft_id, "status": new_status.value}


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.dashboard_host,
        port=settings.dashboard_port
    )
