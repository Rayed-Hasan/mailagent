# Mail Agent Architecture

## Overview

Mail Agent is a privacy-first, open-source AI email management system. Users bring their own AI keys and choose model slots: a fast classification model and a stronger drafting model. The application never depends on a Mail Agent-paid inference API and is designed to run entirely on user-controlled infrastructure.

## Privacy-First Design Principles

1. **No mandatory Mail Agent infrastructure**: The system can operate without any Mail Agent-hosted services
2. **Local-first by default**: Personal installations should run with local storage and local credential management
3. **Storage abstraction**: Application logic is separated from persistence to support multiple backends
4. **Network transparency**: All external connections are documented and opt-in
5. **Verifiable privacy**: Data flows are documented and tested to ensure no unexpected transmissions

## v2 folder structure

```
mailagent/
  core/       configuration, typed domain models, prefilter, prompt guard, secrets
  llm/        provider-neutral LLM contract and two-slot registry
  mail/       provider-neutral mailbox contract
  providers/  Gmail, Graph, IMAP/SMTP adapters
  classifier/ classification, drafting, voice matching
  policy/     hard safety rules, autonomy, rate limits, send queue
  dashboard/  FastAPI control plane
  worker.py   queued background jobs
tests/        unit, integration, and acceptance tests
```

## v2 architecture summary

`mail.list_new` feeds a deterministic prefilter. Bulk/newsletter and no-reply
messages are labeled without an LLM call. Remaining messages pass through one
normalized LLM interface, then hard-coded safety rules run before drafting or
sending. Every decision is written to an audit stream with reason and
confidence. BYOK credentials are encrypted with AES-256-GCM using an
environment/KMS-provided key; secrets are never sent back to the browser or
written to logs. The worker retries transient provider failures with backoff,
then queues and notifies rather than silently failing.

## System Components

### 1. Email Providers (`mailagent/providers/`)

**Base Interface** (`base.py`)
- Abstract interface for all email providers
- Defines standard methods: fetch, send, archive, apply labels

**Gmail Provider** (`gmail_provider.py`)
- OAuth2 authentication with Google
- Full Gmail API integration
- Support for threads, labels, drafts

**IMAP Provider** (`imap_provider.py`)
- Generic IMAP/SMTP implementation
- Supports Yahoo and any IMAP-compatible provider
- Fallback for non-Gmail accounts

### 2. Classifier (`mailagent/classifier/`)

**Email Classifier** (`email_classifier.py`)
- Uses Claude API to classify emails into 10 categories
- Assigns priority scores (0-100)
- Determines appropriate action (reply, draft, archive, flag_human)
- Provides confidence scores and reasoning

**Voice Profile Learner** (`voice_profile_learner.py`)
- Analyzes last 50 sent emails
- Extracts writing style: tone, length, greetings, sign-offs
- Builds common phrase dictionary

**Draft Generator** (`draft_generator.py`)
- Generates email drafts using Claude API
- Incorporates user's voice profile
- Matches writing style and tone
- Includes user guidelines and standard answers

### 3. Policy Engine (`mailagent/policy/`)

**Worth-Sending Policy** (`worth_sending_policy.py`)
- Hardcoded safety checks (not just AI-based)
- Validates all conditions before sending:
  - Real person or service expecting reply
  - Asks question or requests action
  - Agent can answer fully
  - Confidence meets threshold
  - Not no-reply address
  - Not newsletter/promo/automated
  - No sensitive topics
  - Not first-time sender
  - Within rate limits

**Send Flow** (`send_flow.py`)
- Implements autonomy modes:
  - **Approve**: All drafts require human approval
  - **Auto Safe**: Only routine replies auto-sent
  - **Auto Full**: All qualifying replies auto-sent
- 60-second delayed send with cancelable undo window
- Routine reply detection

**Safety Rules** (`safety_rules.py`)
- Always flag for human on:
  - Money/payments
  - Legal contracts
  - Medical information
  - HR matters
  - Compliance issues
  - Emotional content
  - First-time senders
  - Ambiguous content

**Rate Limiter** (`rate_limiter.py`)
- Max N auto-replies per hour (configurable, default 10)
- Max one reply per thread per day
- Per-account tracking
- Automatic cleanup of old entries

### 4. Core (`mailagent/core/`)

**Agent** (`agent.py`)
- Main orchestrator
- Coordinates all components
- Processes emails through pipeline
- Manages provider connections

**Database** (`database.py`)
- Storage interface with local SQLite and Supabase/PostgreSQL backends
- Stores emails, classifications, drafts
- Audit log with full decision trail
- User voice profiles
- Rate limit tracking
- Kill switch state

**Types** (`types.py`)
- Pydantic models for type safety
- Enums for categories, actions, modes
- Validation for all data structures

**Config** (`config.py`)
- Environment-based configuration
- Pydantic Settings for validation
- Centralized settings management

### 5. Dashboard (`mailagent/dashboard/`)

**FastAPI App** (`app.py`)
- REST API for monitoring and control
- Endpoints for:
  - Status and health checks
  - Kill switch control
  - Draft approval/rejection
  - Audit log viewing
  - Statistics and metrics
  - Account management

### 6. Worker (`mailagent/worker.py`)

**Celery Tasks (enterprise option)**
- Scheduled email processing (every 5 minutes)
- Voice profile learning (daily)
- Per-account processing
- Beat scheduler for periodic tasks

**Local queue (personal option)**
- APScheduler uses a SQLite job store, so schedules survive process restarts.
- Jobs can be cancelled individually or cleared by the kill-switch integration.
- Personal mode does not require Redis or Celery.

## Data Flow

```
1. Email Received
   ↓
2. Fetch from Provider (Gmail/IMAP)
   ↓
3. Save to Database
   ↓
4. Fetch Thread + Sender History
   ↓
5. Classify with Claude
   - Category (10 types)
   - Priority (0-100)
   - Action (reply/draft/archive/flag)
   - Confidence score
   ↓
6. Check Safety Rules
   - Sensitive topics?
   - First-time sender?
   - Emotional content?
   ↓
7. Apply Label/Folder
   ↓
8. If Reply/Draft:
   - Generate draft with Claude
   - Incorporate voice profile
   - Check worth-sending policy
   - Check rate limits
   ↓
9. Process through Send Flow
   - Apply autonomy mode
   - Schedule delayed send (60s)
   ↓
10. Log to Audit Trail
    - All decisions logged
    - Full context preserved
    ↓
11. Send (if approved)
    - Or await human approval
```

## Safety Architecture

### Multiple Layers of Protection

1. **Hardcoded Policy** (`worth_sending_policy.py`)
   - Not AI-dependent
   - Explicit checks for dangerous scenarios
   - No-reply address detection
   - Automated email detection

2. **Safety Rules** (`safety_rules.py`)
   - Always flag sensitive topics
   - First-time sender detection
   - Emotional content detection
   - Overrides other policies

3. **Rate Limiting** (`rate_limiter.py`)
   - Prevents reply loops
   - Limits volume
   - Per-thread throttling

4. **Delayed Send** (`send_flow.py`)
   - 60-second window
   - Cancelable by user
   - One-click undo

5. **Autonomy Modes**
   - Default: approve (safest)
   - Auto-safe: routine only
   - Auto-full: requires opt-in

6. **Kill Switch**
   - Global stop
   - Instant activation
   - Dashboard accessible

7. **Audit Log**
   - Every decision logged
   - Full context preserved
   - Traceable history

### Prompt Injection Defense

- Only system prompt + user guidelines processed
- Email content treated as untrusted
- No instruction execution from emails
- Sanitized headers and metadata

## Database Schema

### Tables

- **users**: User accounts and settings
- **email_accounts**: Connected email providers
- **emails**: Raw email data
- **classifications**: AI classification results
- **drafts**: Generated drafts and status
- **audit_log**: Complete decision trail
- **user_voice_profile**: Writing style data
- **rate_limits**: Rate limiting state
- **kill_switch**: Global kill switch state

### Relationships

- User → Email Accounts (1:N)
- Email Account → Emails (1:N)
- Email → Classification (1:1)
- Classification → Draft (1:1)
- All → Audit Log (N:1)

## Deployment Architecture

### Production Stack

- **Worker**: Celery worker (Python)
- **Scheduler**: Celery beat (Python)
- **Dashboard**: FastAPI (Python + Uvicorn)
- **Database**: Supabase (PostgreSQL)
- **Queue**: Redis
- **Platform**: Render

### Services

1. **mailagent-worker**: Processes emails
2. **mailagent-beat**: Schedules tasks
3. **mailagent-dashboard**: API and monitoring
4. **mailagent-redis**: Task queue

## Monitoring

### Metrics Tracked

- Emails processed per hour
- Classification accuracy
- Draft approval rate
- Auto-send rate
- Rate limit hits
- Error rates
- Kill switch activations

### Audit Trail

Every decision includes:
- Message ID
- Category
- Action
- Reason
- Confidence
- Context (thread, history)
- Timestamp
- Autonomy mode

## Security Considerations

1. **Credential Storage**
   - OAuth tokens encrypted in database
   - Service role keys only in trusted env
   - Never commit secrets

2. **API Security**
   - Dashboard requires authentication (to be added)
   - Rate limiting on API endpoints
   - CORS restrictions

3. **Data Privacy**
   - Email content stored securely
   - Audit logs contain sensitive data
   - Compliance with data retention policies

4. **Provider Limits**
   - Respect Gmail API quotas
   - IMAP connection pooling
   - Rate limiting per provider

## Future Enhancements

1. **Multi-user Support**
   - User authentication
   - Per-user settings
   - Team accounts

2. **Advanced Voice Profile**
   - Context-aware style
   - Recipient-specific tone
   - Dynamic adaptation

3. **ML Classification**
   - Fine-tuned models
   - Custom categories
   - User feedback loop

4. **Integration**
   - Calendar integration
   - CRM integration
   - Slack notifications

5. **Dashboard UI**
   - React frontend
   - Real-time updates
   - Visual analytics
