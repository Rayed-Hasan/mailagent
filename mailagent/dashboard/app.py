"""
FastAPI dashboard for monitoring and controls
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from mailagent.core.database import Database
from mailagent.core.types import AutonomyMode, DraftStatus
from mailagent.core.config import settings


app = FastAPI(title="MailAgent Dashboard")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database instance
db = Database()


# Pydantic models
class KillSwitchRequest(BaseModel):
    activate: bool
    reason: Optional[str] = None
    activated_by: str


class AutonomyModeRequest(BaseModel):
    mode: AutonomyMode


class DraftApprovalRequest(BaseModel):
    draft_id: str
    approve: bool


# Dashboard endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "MailAgent Dashboard",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/api/status")
async def get_status():
    """Get overall system status"""
    kill_switch_active = await db.is_kill_switch_active()

    return {
        "status": "active" if not kill_switch_active else "stopped",
        "kill_switch_active": kill_switch_active,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/kill-switch")
async def get_kill_switch():
    """Get kill switch status"""
    active = await db.is_kill_switch_active()
    return {"active": active}


@app.post("/api/kill-switch")
async def toggle_kill_switch(request: KillSwitchRequest):
    """Toggle kill switch"""
    if request.activate:
        await db.activate_kill_switch(request.reason or "Manual activation", request.activated_by)
    else:
        await db.deactivate_kill_switch()

    return {"active": request.activate}


@app.get("/api/accounts")
async def get_accounts(user_id: str):
    """Get all email accounts for a user"""
    accounts = await db.get_accounts_by_user(user_id)
    return {"accounts": accounts}


@app.get("/api/emails")
async def get_emails(account_id: str, limit: int = 50):
    """Get emails for an account"""
    emails = await db.get_emails_by_account(account_id, limit)
    return {"emails": emails}


@app.get("/api/emails/{email_id}")
async def get_email(email_id: str):
    """Get a specific email"""
    email = await db.get_email(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return email


@app.get("/api/classifications")
async def get_classifications(account_id: str, limit: int = 50):
    """Get classifications for an account"""
    # This would need to be implemented in database
    return {"classifications": []}


@app.get("/api/drafts")
async def get_drafts(account_id: str, status: Optional[str] = None):
    """Get drafts for an account"""
    drafts = await db.get_pending_drafts(account_id)
    if status:
        drafts = [d for d in drafts if d["status"] == status]
    return {"drafts": drafts}


@app.post("/api/drafts/approve")
async def approve_draft(request: DraftApprovalRequest):
    """Approve or reject a draft"""
    new_status = DraftStatus.APPROVED if request.approve else DraftStatus.REJECTED
    success = await db.update_draft_status(request.draft_id, new_status)

    if not success:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {"draft_id": request.draft_id, "status": new_status.value}


@app.get("/api/audit-log")
async def get_audit_log(email_id: Optional[str] = None, limit: int = 100):
    """Get audit log"""
    if email_id:
        log = await db.get_audit_log(email_id)
    else:
        # Get recent audit log entries (would need to be implemented)
        log = []

    return {"audit_log": log}


@app.get("/api/voice-profile")
async def get_voice_profile(user_id: str):
    """Get user voice profile"""
    profile = await db.get_voice_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return profile


@app.get("/api/rate-limits")
async def get_rate_limits(account_id: str):
    """Get rate limit info"""
    rate_limit = await db.get_rate_limit(account_id)
    if not rate_limit:
        return {"auto_replies_sent": 0, "limit": settings.max_auto_replies_per_hour}
    return rate_limit


@app.get("/api/stats")
async def get_stats(account_id: str):
    """Get statistics for an account"""
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
