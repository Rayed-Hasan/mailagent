"""Synthetic email data seeder for public demo mode."""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from mailagent.core.types import EmailMessage, EmailCategory, EmailAction


DEMO_USER_ID = "demo-user-judge"
DEMO_ACCOUNT_ID = "demo-account-001"
DEMO_ACCOUNT_EMAIL = "judge@example.com"


DEMO_EMAILS = [
    {
        "message_id": "msg-001",
        "thread_id": "thread-001",
        "sender": "Sarah Chen",
        "sender_email": "sarah.chen@techcorp.com",
        "subject": "URGENT: Production incident requires immediate attention",
        "body": """Hi,

We're experiencing a critical issue with the payment processing service. Transaction failures have increased by 400% in the last hour.

The error logs indicate a timeout when communicating with the external payment gateway. We've already escalated to the vendor, but we need engineering to investigate the fallback mechanism.

Can you please review the logs and provide guidance on whether we should trigger the emergency fallback or continue retrying?

This is blocking customer transactions and revenue.

Best,
Sarah Chen
VP of Engineering""",
        "received_at": datetime.now(timezone.utc) - timedelta(minutes=15),
        "category": EmailCategory.URGENT,
        "priority_score": 95,
        "action": EmailAction.REPLY,
        "confidence": 0.92,
        "reason": "Critical production incident affecting revenue with explicit urgency indicator",
        "labels": ["Security", "Production", "High Priority"],
    },
    {
        "message_id": "msg-002",
        "thread_id": "thread-002",
        "sender": "Marcus Johnson",
        "sender_email": "marcus.j@lawfirm.com",
        "subject": "Contract review needed - NDA for new partnership",
        "body": """Dear Jordan,

Please find attached the Non-Disclosure Agreement for our proposed partnership with Acme Innovations. Our legal team has reviewed it and marked a few clauses that require your attention:

1. Section 4.2 - Indemnification terms appear asymmetric
2. Section 7.1 - Intellectual property ownership needs clarification
3. Exhibit A - Jurisdiction clause may conflict with our standard policy

We need your review and approval by Friday to keep the partnership timeline on track. Let me know if you have questions.

Regards,
Marcus Johnson
General Counsel""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=2),
        "category": EmailCategory.URGENT,
        "priority_score": 88,
        "action": EmailAction.REPLY,
        "confidence": 0.89,
        "reason": "Legal document with deadline requiring review, high business impact",
        "labels": ["Legal", "Review Required", "Deadline"],
    },
    {
        "message_id": "msg-003",
        "thread_id": "thread-003",
        "sender": "Emily Rodriguez",
        "sender_email": "emily.r@design.co",
        "subject": "Q4 marketing campaign assets ready for approval",
        "body": """Hi Jordan,

The Q4 marketing campaign assets are ready for your final approval. We've completed all requested revisions from the last round:

- Updated hero imagery with new product shots
- Revised copy based on brand guidelines
- Optimized all assets for mobile display
- Added accessibility alt text

Please review the attached deck and let us know if we have your sign-off to proceed with production. We're on track to launch on November 1st.

Thanks,
Emily""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=4),
        "category": EmailCategory.MEETS_REPLY,
        "priority_score": 75,
        "action": EmailAction.REPLY,
        "confidence": 0.85,
        "reason": "Approval request with clear deadline, business-critical campaign",
        "labels": ["Marketing", "Approval", "Q4"],
    },
    {
        "message_id": "msg-004",
        "thread_id": "thread-004",
        "sender": "Security Team",
        "sender_email": "security@company.com",
        "subject": "Security Alert: Unusual sign-in detected from new location",
        "body": """Hello,

We detected a sign-in to your account from a new location:

Location: Tokyo, Japan
IP Address: 203.0.113.45
Device: Chrome on Windows
Time: October 26, 2026 at 2:34 AM UTC

If this was you, you can ignore this message. If you did not sign in from this location, please:

1. Change your password immediately
2. Review your recent activity log
3. Enable two-factor authentication if not already active

Stay secure,
The Security Team""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=6),
        "category": EmailCategory.SENSITIVE,
        "priority_score": 92,
        "action": EmailAction.REPLY,
        "confidence": 0.95,
        "reason": "Security alert requiring immediate attention, potential account compromise",
        "labels": ["Security", "Urgent", "Account"],
    },
    {
        "message_id": "msg-005",
        "thread_id": "thread-005",
        "sender": "Netflix",
        "sender_email": "info@netflix.com",
        "subject": "Your membership payment was successful",
        "body": """Hi Jordan,

This email confirms that your payment of $15.99 for your Netflix Standard subscription was successful.

Payment details:
- Amount: $15.99
- Date: October 26, 2026
- Payment method: Visa ending in 4242
- Next billing date: November 26, 2026

Your membership is active and you can continue enjoying all your favorite shows and movies.

Thanks,
The Netflix Team""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=8),
        "category": EmailCategory.FYI,
        "priority_score": 20,
        "action": EmailAction.ARCHIVE,
        "confidence": 0.96,
        "reason": "Automated payment confirmation, no action required",
        "labels": ["Receipt", "Finance", "Low Priority"],
    },
    {
        "message_id": "msg-006",
        "thread_id": "thread-006",
        "sender": "Amazon",
        "sender_email": "ship-confirm@amazon.com",
        "subject": "Your Amazon order has shipped!",
        "body": """Great news!

Your order #112-3456789-0123456 has shipped and is on its way.

Order details:
- Wireless Noise-Canceling Headphones - $299.99
- USB-C Charging Cable - $12.99

Estimated delivery: October 28 - October 30

Track your package: https://amazon.com/track/112-3456789-0123456

Thanks for shopping with us!""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=10),
        "category": EmailCategory.FYI,
        "priority_score": 30,
        "action": EmailAction.ARCHIVE,
        "confidence": 0.94,
        "reason": "Shipping confirmation, informational only",
        "labels": ["Receipt", "Shopping", "Low Priority"],
    },
    {
        "message_id": "msg-007",
        "thread_id": "thread-007",
        "sender": "Tech Weekly Newsletter",
        "sender_email": "newsletter@techweekly.com",
        "subject": "This Week in Tech: AI breakthroughs and startup funding",
        "body": """THE WEEKLY ROUNDUP

Top Stories This Week:

🤖 OpenAI announces GPT-5 with enhanced reasoning capabilities
💰 Three AI startups raise $500M in Series B funding
🔒 New cybersecurity regulations proposed for EU markets
📱 Apple previews next-generation AR glasses
☁️ Cloud computing costs hit record highs

Read the full stories on our website.

Unsubscribe | Manage Preferences | View in Browser""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=12),
        "category": EmailCategory.NEWSLETTER,
        "priority_score": 10,
        "action": EmailAction.ARCHIVE,
        "confidence": 0.98,
        "reason": "Newsletter with bulk content, low priority",
        "labels": ["Newsletter", "Read Later", "Low Priority"],
    },
    {
        "message_id": "msg-008",
        "thread_id": "thread-008",
        "sender": "David Park",
        "sender_email": "david.park@startup.io",
        "subject": "Coffee chat next week?",
        "body": """Hey Jordan,

Hope you're doing well! It's been a while since we caught up. I'd love to grab coffee and hear about what you're working on these days.

I have some interesting updates from my side too - we just closed our seed round and are scaling the team.

Are you free sometime next week? Tuesday or Thursday afternoon would work best for me.

Best,
David""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=14),
        "category": EmailCategory.MEETS_REPLY,
        "priority_score": 55,
        "action": EmailAction.REPLY,
        "confidence": 0.82,
        "reason": "Personal networking request, flexible timeline",
        "labels": ["Personal", "Networking", "Optional"],
    },
    {
        "message_id": "msg-009",
        "thread_id": "thread-009",
        "sender": "HR Department",
        "sender_email": "hr@company.com",
        "subject": "Open enrollment period ends Friday",
        "body": """Dear Team,

This is a reminder that the annual benefits open enrollment period ends this Friday, October 30th.

Please ensure you have:
- Reviewed your current coverage
- Made any necessary changes to health insurance
- Updated your beneficiary information
- Selected your 401(k) contribution percentage

Failure to complete enrollment by the deadline will result in your current elections rolling over to next year.

If you have questions, please contact HR at benefits@company.com or attend the Q&A session tomorrow at 2 PM.

Thank you,
Human Resources""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=16),
        "category": EmailCategory.URGENT,
        "priority_score": 80,
        "action": EmailAction.REPLY,
        "confidence": 0.88,
        "reason": "HR deadline with potential consequences if missed",
        "labels": ["HR", "Deadline", "Benefits"],
    },
    {
        "message_id": "msg-010",
        "thread_id": "thread-010",
        "sender": "Promo Deals",
        "sender_email": "deals@promo.com",
        "subject": "🔥 FLASH SALE: 70% OFF everything!",
        "body": """DON'T MISS OUT!

Limited time offer: 70% OFF all items!

Shop now and save big on:
- Electronics
- Fashion
- Home goods
- And more!

Use code: FLASH70 at checkout

Offer expires in 24 hours. Terms and conditions apply.

Unsubscribe | View in browser""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=18),
        "category": EmailCategory.PROMO,
        "priority_score": 5,
        "action": EmailAction.ARCHIVE,
        "confidence": 0.99,
        "reason": "Promotional content with urgency tactics, low value",
        "labels": ["Promo", "Low Priority", "Archive"],
    },
    {
        "message_id": "msg-011",
        "thread_id": "thread-011",
        "sender": "IT Support",
        "sender_email": "support@company.com",
        "subject": "Scheduled maintenance: This weekend",
        "body": """Hello,

This is a notification of scheduled IT maintenance:

Date: Saturday, October 31, 2026
Time: 2:00 AM - 6:00 AM UTC
Impact: Email services will be intermittently unavailable

During this window, you may experience:
- Delays in email delivery
- Temporary inability to send/receive messages
- Brief outages of the webmail interface

All services will be restored by 6:00 AM UTC. No action is required on your part.

Thank you for your patience,
IT Support Team""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=20),
        "category": EmailCategory.FYI,
        "priority_score": 35,
        "action": EmailAction.ARCHIVE,
        "confidence": 0.91,
        "reason": "Planned maintenance notification, informational",
        "labels": ["IT", "Maintenance", "FYI"],
    },
    {
        "message_id": "msg-012",
        "thread_id": "thread-012",
        "sender": "Lisa Wang",
        "sender_email": "lisa.wang@finance.co",
        "subject": "Invoice #INV-2026-1042 for September services",
        "body": """Dear Jordan,

Please find attached Invoice #INV-2026-1042 for consulting services provided in September 2026.

Invoice Summary:
- Consulting Services: $5,000.00
- Expense Reimbursement: $450.00
- Total Due: $5,450.00

Payment Terms: Net 30
Due Date: November 25, 2026

Payment instructions:
- Bank transfer to account ending in 7890
- Reference invoice number in memo
- EFT details on page 2

Please let me know if you have any questions.

Best regards,
Lisa Wang
Finance Department""",
        "received_at": datetime.now(timezone.utc) - timedelta(hours=22),
        "category": EmailCategory.MEETS_REPLY,
        "priority_score": 65,
        "action": EmailAction.REPLY,
        "confidence": 0.87,
        "reason": "Invoice with payment deadline, financial importance",
        "labels": ["Finance", "Invoice", "Payment"],
    },
]


def get_demo_emails() -> List[Dict[str, Any]]:
    """Return the synthetic demo email data."""
    return DEMO_EMAILS


def get_demo_user_id() -> str:
    """Return the demo user ID."""
    return DEMO_USER_ID


def get_demo_account_id() -> str:
    """Return the demo account ID."""
    return DEMO_ACCOUNT_ID


def get_demo_account_email() -> str:
    """Return the demo account email address."""
    return DEMO_ACCOUNT_EMAIL
