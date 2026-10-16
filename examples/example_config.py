"""
Example configuration for MailAgent
This file shows how to configure the agent programmatically
"""

from mailagent.core.agent import EmailAgent
from mailagent.core.types import AutonomyMode
from mailagent.core.config import settings


# Example 1: Basic agent setup
async def basic_setup():
    """Basic agent setup with default settings"""
    agent = EmailAgent(user_id="user_123")
    await agent.initialize()
    await agent.process_account("account_456")
    await agent.shutdown()


# Example 2: Custom autonomy mode
async def custom_autonomy_mode():
    """Agent with auto_safe autonomy mode"""
    agent = EmailAgent(
        user_id="user_123",
        autonomy_mode=AutonomyMode.AUTO_SAFE
    )
    await agent.initialize()
    await agent.process_account("account_456")
    await agent.shutdown()


# Example 3: Custom confidence threshold
async def custom_confidence():
    """Agent with custom confidence threshold"""
    # Modify settings before creating agent
    settings.confidence_threshold = 0.90  # Higher threshold

    agent = EmailAgent(user_id="user_123")
    await agent.initialize()
    await agent.process_account("account_456")
    await agent.shutdown()


# Example 4: Custom rate limits
async def custom_rate_limits():
    """Agent with custom rate limits"""
    settings.max_auto_replies_per_hour = 20  # Allow more replies per hour

    agent = EmailAgent(user_id="user_123")
    await agent.initialize()
    await agent.process_account("account_456")
    await agent.shutdown()


# Example 5: Adding a Gmail account
async def add_gmail_account():
    """Example of adding a Gmail account"""
    from mailagent.core.database import Database

    db = Database()

    # OAuth token from Gmail OAuth flow
    credentials = {
        "token": {
            "token": "access_token",
            "refresh_token": "refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "scopes": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/gmail.send"
            ]
        }
    }

    account_id = await db.save_account(
        user_id="user_123",
        provider="gmail",
        email_address="your@gmail.com",
        credentials=credentials
    )

    print(f"Account added with ID: {account_id}")


# Example 6: Adding an IMAP account
async def add_imap_account():
    """Example of adding an IMAP account (Yahoo, generic)"""
    from mailagent.core.database import Database

    db = Database()

    credentials = {
        "email_address": "your@yahoo.com",
        "password": "your_app_password",  # Use app password, not regular password
        "imap_server": "imap.mail.yahoo.com",
        "imap_port": 993,
        "smtp_server": "smtp.mail.yahoo.com",
        "smtp_port": 587
    }

    account_id = await db.save_account(
        user_id="user_123",
        provider="imap",
        email_address="your@yahoo.com",
        credentials=credentials
    )

    print(f"Account added with ID: {account_id}")


# Example 7: Processing a single email
async def process_single_email():
    """Process a single email for testing"""
    from mailagent.core.types import EmailMessage
    from datetime import datetime

    email = EmailMessage(
        message_id="test_msg_123",
        thread_id="test_thread_123",
        sender="Test Sender",
        sender_email="test@example.com",
        subject="Test Subject",
        body="This is a test email body.",
        received_at=datetime.utcnow(),
        raw_headers={}
    )

    agent = EmailAgent(user_id="user_123")
    await agent.initialize()

    # This would require a provider to be loaded
    # await agent.process_email(email, account_id, provider)

    await agent.shutdown()


# Example 8: Viewing audit logs
async def view_audit_logs():
    """View audit logs for an email"""
    from mailagent.core.database import Database

    db = Database()
    logs = await db.get_audit_log("email_123")

    for log in logs:
        print(f"{log['timestamp']}: {log['event_type']} - {log['reason']}")


# Example 9: Activating kill switch
async def activate_kill_switch():
    """Activate the kill switch"""
    from mailagent.core.database import Database

    db = Database()
    await db.activate_kill_switch(
        reason="Emergency stop - testing",
        activated_by="admin"
    )

    print("Kill switch activated")


# Example 10: Checking kill switch status
async def check_kill_switch():
    """Check if kill switch is active"""
    from mailagent.core.database import Database

    db = Database()
    is_active = await db.is_kill_switch_active()

    if is_active:
        print("Kill switch is ACTIVE - agent will not process emails")
    else:
        print("Kill switch is INACTIVE - agent is running")


# Example 11: Getting user voice profile
async def get_voice_profile():
    """Get user's voice profile"""
    from mailagent.core.database import Database

    db = Database()
    profile = await db.get_voice_profile("user_123")

    if profile:
        print(f"Tone: {profile['tone']}")
        print(f"Average length: {profile['avg_length']} words")
        print(f"Greeting: {profile['greeting_style']}")
        print(f"Sign-off: {profile['sign_off']}")
    else:
        print("No voice profile found")


# Example 12: Learning voice profile
async def learn_voice_profile():
    """Learn user's voice profile from sent emails"""
    agent = EmailAgent(user_id="user_123")
    await agent.initialize()
    await agent.learn_voice_profile("account_456")
    await agent.shutdown()

    print("Voice profile updated")


if __name__ == "__main__":
    import asyncio

    # Run any example
    asyncio.run(basic_setup())
