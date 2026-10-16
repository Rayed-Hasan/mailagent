# MailAgent - Project Summary

## Overview

MailAgent is a comprehensive intelligent email agent system that automatically classifies, prioritizes, and drafts responses to emails using Claude AI. The system is built with safety-first principles, multiple autonomy modes, and comprehensive audit logging.

## What Has Been Built

### Core Components ✅

1. **Email Providers**
   - Gmail provider with OAuth2 authentication
   - IMAP provider for Yahoo and generic IMAP accounts
   - Abstract base interface for extensibility

2. **Email Classifier**
   - Claude API integration for classification
   - 10 categories: meets_reply, FYI, newsletter, promo, received, notification, spam, personal, urgent, sensitive
   - Priority scoring (0-100)
   - Action determination with confidence scores

3. **Voice Profile Learning**
   - Analyzes last 50 sent emails
   - Extracts tone, length, greetings, sign-offs
   - Builds common phrase dictionary
   - Integrated into draft generation

4. **Draft Generation**
   - Claude API-powered drafting
   - User voice profile integration
   - Context-aware responses
   - Style matching

5. **Policy Engine**
   - Worth-sending policy (hardcoded, not AI-only)
   - Send flow with autonomy modes
   - Safety rules for sensitive topics
   - Rate limiting

6. **Safety Features**
   - 60-second delayed send with cancelable undo
   - Global kill switch
   - Comprehensive audit logging
   - Prompt injection defense

7. **Database Layer**
   - Supabase integration
   - Complete schema with relationships
   - Audit log with full decision trail
   - User voice profile storage

8. **Dashboard API**
   - FastAPI-based REST API
   - Status monitoring
   - Draft approval/rejection
   - Kill switch control
   - Audit log viewing

9. **Job Queue**
   - Celery with Redis
   - Scheduled processing (every 5 minutes)
   - Per-account tasks
   - Beat scheduler

10. **Testing**
    - Acceptance test suite with 15 sample emails
    - Unit tests for send flow
    - Unit tests for rate limiter
    - Policy validation tests

### Autonomy Modes ✅

1. **Approve** (default)
   - Agent drafts all replies
   - Human must approve every send
   - Safest mode

2. **Auto Safe**
   - Agent sends routine replies automatically
   - Non-routine replies require approval
   - Good balance of automation and safety

3. **Auto Full**
   - Agent sends all replies that pass policy
   - User is warned after each send
   - Requires explicit opt-in
   - Maximum automation

### Safety Rules ✅

Always flag for human on:
- Money/payments
- Legal contracts
- Medical information
- HR matters
- Compliance issues
- Emotional content
- First-time senders
- Ambiguous content

### Rate Limiting ✅

- Max N auto-replies per hour (configurable, default 10)
- Max one reply per thread per day
- Per-account tracking
- Automatic cleanup

### Worth-Sending Policy ✅

A reply is sent only if ALL conditions are true:
- From a real person or service expecting reply
- Asks question, requests action, or needs confirmation
- Agent can answer fully from thread + guidelines
- Confidence >= threshold (default 0.85)
- Not no-reply address
- Not newsletter/promo/automated
- No sensitive topics
- Not first-time sender
- Within rate limits

## Project Structure

```
mailagent/
├── mailagent/
│   ├── core/
│   │   ├── agent.py          # Main orchestrator
│   │   ├── config.py         # Configuration
│   │   ├── database.py       # Supabase integration
│   │   └── types.py          # Type definitions
│   ├── providers/
│   │   ├── base.py           # Abstract interface
│   │   ├── gmail_provider.py # Gmail OAuth2
│   │   └── imap_provider.py  # IMAP/SMTP
│   ├── classifier/
│   │   ├── email_classifier.py    # Classification
│   │   ├── voice_profile_learner.py # Style learning
│   │   └── draft_generator.py     # Draft generation
│   ├── policy/
│   │   ├── worth_sending_policy.py # Safety checks
│   │   ├── send_flow.py            # Autonomy modes
│   │   ├── safety_rules.py         # Safety rules
│   │   └── rate_limiter.py         # Rate limiting
│   ├── dashboard/
│   │   └── app.py              # FastAPI dashboard
│   ├── supabase/
│   │   └── migrations/
│   │       └── 001_initial_schema.sql
│   └── worker.py              # Celery tasks
├── tests/
│   ├── test_acceptance.py     # Acceptance tests
│   ├── test_send_flow.py      # Send flow tests
│   └── test_rate_limiter.py   # Rate limiter tests
├── examples/
│   └── example_config.py      # Configuration examples
├── main.py                    # Entry point
├── requirements.txt           # Dependencies
├── render.yaml                # Render deployment
├── .env.example               # Environment template
├── README.md                  # Project README
├── USAGE.md                   # Usage guide
├── DEPLOYMENT.md              # Deployment guide
└── ARCHITECTURE.md            # Architecture documentation
```

## Technology Stack

- **Language**: Python
- **AI**: Claude API (direct HTTP calls)
- **Database**: Supabase (PostgreSQL)
- **Job Queue**: Celery with Redis
- **Web Framework**: FastAPI
- **Email**: Gmail API, IMAP/SMTP
- **Deployment**: Render

## Key Features

### ✅ Implemented

1. Multi-provider email support (Gmail, Yahoo, IMAP)
2. 10-category email classification
3. Priority scoring (0-100)
4. Action determination (reply, draft, archive, flag_human)
5. User voice profile learning
6. Style-matched draft generation
7. Three autonomy modes
8. Hardcoded worth-sending policy
9. Safety rules for sensitive topics
10. Rate limiting
11. 60-second delayed send with undo
12. Global kill switch
13. Comprehensive audit logging
14. Dashboard API
15. Celery job queue
16. Acceptance test suite
17. Unit tests
18. Deployment configuration

### 📝 Next Steps (for production)

1. Add user authentication to dashboard
2. Implement React frontend for dashboard
3. Add webhook/push notifications for real-time processing
4. Implement SMTP for sending (currently placeholder)
5. Add more comprehensive testing with real email accounts
6. Set up monitoring and alerting
7. Add error recovery and retry logic
8. Implement user onboarding flow
9. Add multi-tenant support
10. Performance optimization for large inboxes

## Documentation

- **README.md**: Project overview and quick start
- **USAGE.md**: Detailed usage guide with examples
- **DEPLOYMENT.md**: Step-by-step deployment to Render
- **ARCHITECTURE.md**: System architecture and design decisions
- **PROJECT_SUMMARY.md**: This file

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment: `cp .env.example .env` and edit
3. Set up Supabase and run migration
4. Start Redis: `redis-server`
5. Start Celery: `celery -A mailagent.worker worker --loglevel=info`
6. Start dashboard: `python -m mailagent.dashboard.app`
7. Add email accounts via API
8. Let the agent process your emails!

## Testing

Run acceptance tests:
```bash
pytest tests/test_acceptance.py -v
```

Run all tests:
```bash
pytest tests/ -v
```

## Deployment

See `DEPLOYMENT.md` for complete deployment instructions to Render.

## Safety First

This system is designed with multiple layers of safety:

1. **Hardcoded Policy**: Not AI-dependent
2. **Safety Rules**: Always flag sensitive topics
3. **Rate Limiting**: Prevent reply loops
4. **Delayed Send**: 60-second undo window
5. **Autonomy Modes**: Default to safest mode
6. **Kill Switch**: Global stop capability
7. **Audit Log**: Complete decision trail

## License

This is a demonstration project. Ensure you have appropriate licenses for all dependencies and comply with email provider terms of service.

## Support

For issues or questions, refer to the documentation files or create an issue in the repository.
