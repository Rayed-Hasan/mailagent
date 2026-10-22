# MailAgent Repository Audit Report

**Date:** 2026-10-17
**Auditor:** Senior Software Engineer
**Purpose:** 12-day hackathon preparation assessment
**Branch:** main (commit f9cdd04)
**Working Tree:** Clean (no uncommitted changes)

---

## Executive Summary

MailAgent is a BYOK (Bring Your Own Key) autonomous email agent that connects to email providers, classifies messages, drafts responses, and operates under explicit user control with safety policies. The repository contains a mix of v1 implementation (direct Claude API calls) and v2 foundation (provider-neutral interfaces, BYOG/BYOK support, encrypted secrets, deterministic prefiltering).

**Current State:** Partially implemented foundation with incomplete integration between v1 and v2 architectures. Tests fail due to missing dependencies. No production-ready end-to-end flow exists.

---

## Repository State

### Git Information
- **Branch:** main
- **Latest Commit:** f9cdd04 "Build MailAgent v2 BYOG foundation and inbox UX"
- **Working Tree:** Clean
- **Remote:** origin/main exists and is up to date

### Project Structure

```
mailagent/
├── mailagent/              # Main Python package
│   ├── core/              # Configuration, types, database, agent
│   │   ├── agent.py      # Main orchestrator (v1 implementation)
│   │   ├── config.py     # Pydantic settings
│   │   ├── database.py   # Supabase integration
│   │   ├── types.py      # Pydantic models
│   │   ├── prefilter.py  # v2 deterministic filtering
│   │   ├── prompt_guard.py # v2 prompt injection defense
│   │   └── secret_store.py # v2 AES-GCM encryption
│   ├── llm/              # v2 provider-neutral LLM interface
│   │   ├── base.py       # LLMProvider contract
│   │   └── registry.py   # Model slot registry
│   ├── mail/             # v2 provider-neutral mail interface
│   │   └── base.py       # MailProvider contract
│   ├── providers/        # Email provider implementations
│   │   ├── base.py       # v1 EmailProviderInterface
│   │   ├── gmail_provider.py # Gmail OAuth2
│   │   └── imap_provider.py  # IMAP/SMTP
│   ├── classifier/       # AI-powered classification and drafting
│   │   ├── email_classifier.py # Claude-based classifier
│   │   ├── voice_profile_learner.py
│   │   └── draft_generator.py
│   ├── policy/           # Safety and autonomy policies
│   │   ├── worth_sending_policy.py
│   │   ├── send_flow.py
│   │   ├── safety_rules.py
│   │   └── rate_limiter.py
│   ├── dashboard/        # FastAPI control plane
│   │   └── app.py
│   ├── supabase/         # Database migrations
│   │   └── migrations/
│   │       └── 001_initial_schema.sql
│   ├── worker.py         # Celery background tasks
│   └── __init__.py
├── mail/                 # Legacy v2 mail package (duplicate)
│   └── base.py
├── tests/                # Test suite
│   ├── test_acceptance.py
│   ├── test_foundation.py # v2 foundation tests
│   ├── test_rate_limiter.py
│   └── test_send_flow.py
├── examples/             # Configuration examples
│   └── example_config.py
├── index.html            # Frontend demo (static)
├── app.js                # Frontend JavaScript
├── styles.css            # Frontend CSS (minified)
├── main.py               # Entry point
├── requirements.txt      # Python dependencies
├── .env.example          # Environment template
├── Dockerfile            # Container build
├── docker-compose.yml    # Multi-container setup
├── render.yaml           # Render deployment config
├── README.md             # Project documentation
├── ARCHITECTURE.md       # Architecture documentation
├── USAGE.md              # Usage guide
├── DEPLOYMENT.md         # Deployment instructions
├── PROJECT_SUMMARY.md    # Project summary
└── DAILY-DEVELOPER-LOG.md # Development log
```

---

## Dependency Analysis

### requirements.txt vs Installed Packages

**Declared in requirements.txt:**
- anthropic>=0.18.0
- supabase>=2.0.0
- celery>=5.3.0
- redis>=5.0.0
- imap-tools>=0.60.0
- email-validator>=2.1.0
- google-api-python-client>=2.100.0
- google-auth-oauthlib>=1.1.0
- google-auth-httplib2>=0.2.0
- fastapi>=0.104.0
- uvicorn>=0.24.0
- pydantic>=2.5.0
- pydantic-settings>=2.1.0
- cryptography>=42.0.0
- python-dotenv>=1.0.0
- python-dateutil>=2.8.0
- pytz>=2023.3
- pytest>=7.4.0
- pytest-asyncio>=0.21.0

**Actually Installed (partial list):**
- fastapi==0.115.0 ✓
- uvicorn==0.30.0 ✓
- pydantic==2.9.0 ✓
- pytest==8.3.0 ✓
- pytest-asyncio==0.24.0 ✓
- cryptography==46.0.5 ✓
- python-dotenv==1.0.1 ✓
- python-dateutil==2.9.0.post0 ✓
- pytz==2026.3.post1 ✓
- httpx==0.27.0 ✓

**Missing Critical Dependencies:**
- ❌ pydantic-settings (causes import errors)
- ❌ anthropic (Claude API)
- ❌ supabase (database client)
- ❌ celery (job queue)
- ❌ redis (task queue)
- ❌ imap-tools (IMAP handling)
- ❌ google-api-python-client (Gmail API)
- ❌ google-auth-oauthlib (Gmail OAuth)
- ❌ google-auth-httplib2 (Gmail auth)

**Extra Installed Packages (not in requirements.txt):**
- Extensive data science stack (pandas, numpy, scikit-learn, scipy)
- NLP stack (spacy, nltk)
- Blockchain libraries (web3, eth-*)
- PDF processing (pdfminer.six, PyPDF2)
- Speech recognition (SpeechRecognition, pyttsx3)
- Many more unused packages

**Issue:** The installed environment contains a large number of unrelated packages that are not declared in requirements.txt, suggesting this is a shared development environment rather than a clean project-specific virtual environment.

---

## Architecture Analysis

### Dual Architecture Problem

The repository contains **two parallel architectures** that are not integrated:

#### v1 Architecture (Current Implementation)
- Direct Claude API calls via HTTP in `email_classifier.py` and `draft_generator.py`
- Hardcoded model: `claude-3-sonnet-20240229`
- Provider-specific interfaces in `providers/base.py` (EmailProviderInterface)
- Direct provider implementations (Gmail, IMAP)
- Single model for both classification and drafting
- No BYOK abstraction
- No encrypted secrets
- No deterministic prefiltering

#### v2 Architecture (Foundation Only)
- Provider-neutral LLM interface in `llm/base.py` (LLMProvider)
- Model slot registry in `llm/registry.py` (classification/drafting slots)
- Provider-neutral mail interface in `mail/base.py` (MailProvider)
- AES-GCM encrypted secret storage in `core/secret_store.py`
- Deterministic prefiltering in `core/prefilter.py`
- Prompt injection defense in `core/prompt_guard.py`
- BYOK support with multiple providers (Claude, GPT, Gemini, Ollama)

**Status:** v2 interfaces are defined but **not used** by the v1 implementation. The agent orchestrator (`core/agent.py`) still uses v1 providers and classifiers.

---

## Component Analysis

### 1. Email Providers

#### Gmail Provider (`providers/gmail_provider.py`)
**Status:** Implemented but incomplete
- ✅ OAuth2 authentication flow defined
- ✅ Gmail API integration
- ✅ Thread fetching
- ✅ Label application
- ✅ Draft creation
- ✅ Send reply
- ❌ Hardcoded model version (not using v2 LLM interface)
- ❌ No integration with v2 MailProvider contract
- ❌ No actual implementation of `fetch_sender_history` (placeholder comment)
- ❌ No SMTP implementation for sending (uses Gmail API draft then send)
- ❌ No error recovery or retry logic
- ❌ No connection pooling or rate limiting at provider level

#### IMAP Provider (`providers/imap_provider.py`)
**Status:** Implemented but incomplete
- ✅ Basic IMAP connection
- ✅ Email fetching
- ✅ Thread reconstruction (via References header)
- ✅ Label application (as IMAP flags)
- ✅ Archive (move to folder)
- ❌ No SMTP implementation for sending (placeholder)
- ❌ No TLS/certificate validation mentioned
- ❌ No timeout configuration
- ❌ No connection cleanup on errors
- ❌ No incremental sync (fetches all emails)
- ❌ No cursor/sync checkpoint tracking
- ❌ No pagination for large mailboxes
- ❌ No handling of provider-specific IMAP quirks

#### v2 MailProvider Contract (`mail/base.py`)
**Status:** Defined but not implemented
- ✅ Clean abstraction defined
- ✅ Methods: list_new, get_thread, send, label, archive, smooth
- ❌ No adapters implement this contract
- ❌ Gmail and IMAP providers still use v1 interface
- ❌ No migration path from v1 to v2

### 2. AI/LLM Integration

#### v1 Implementation (Active)
**File:** `classifier/email_classifier.py`
- Direct HTTP calls to Anthropic API
- Hardcoded model: `claude-3-sonnet-20240229`
- No token counting
- No fallback mechanism
- Has offline fallback when API fails (deterministic rules)
- ❌ Does not use v2 LLMProvider interface
- ❌ No model slot selection
- ❌ No support for other providers (GPT, Gemini, Ollama)

**File:** `classifier/draft_generator.py`
- Direct HTTP calls to Anthropic API
- Hardcoded model: `claude-3-sonnet-20240229`
- No token counting
- ❌ Does not use v2 LLMProvider interface
- ❌ No model slot selection

#### v2 Implementation (Unused)
**File:** `llm/base.py`
- ✅ Provider-neutral LLMProvider contract defined
- ✅ Normalized LLMResponse with token counts
- ✅ Support for tools, JSON mode, streaming
- ❌ No actual providers implement this contract
- ❌ No Claude, GPT, Gemini, or Ollama adapters

**File:** `llm/registry.py`
- ✅ Model slot registry (classification/drafting)
- ✅ Role validation
- ❌ No integration with agent or classifiers
- ❌ No providers registered

### 3. Classification System

**File:** `classifier/email_classifier.py`
**Status:** Partially implemented
- ✅ 10 categories defined (meets_reply, FYI, newsletter, promo, received, notification, spam, personal, urgent, sensitive)
- ✅ Priority scoring (0-100)
- ✅ Action determination (reply, draft_only, archive, flag_human)
- ✅ Confidence scoring
- ✅ Offline fallback when BYOK unavailable
- ✅ Thread and sender history context
- ❌ Uses v1 interface (not v2 LLMProvider)
- ❌ No integration with v2 prefilter
- ❌ No integration with v2 prompt guard
- ❌ Hardcoded prompt (not using prompt guard wrapping)
- ❌ No structured output validation
- ❌ No confidence threshold enforcement

### 4. Draft Generation

**File:** `classifier/draft_generator.py`
**Status:** Partially implemented
- ✅ Voice profile integration
- ✅ Thread context
- ✅ User guidelines support
- ✅ Style matching (tone, length, greeting, sign-off)
- ❌ Uses v1 interface (not v2 LLMProvider)
- ❌ No integration with v2 prompt guard
- ❌ No structured output validation
- ❌ No error handling for malformed responses

### 5. Voice Profile Learning

**File:** `classifier/voice_profile_learner.py`
**Status:** Implemented but not integrated
- ✅ Analyzes last 50 sent emails
- ✅ Extracts tone, length, greetings, sign-offs
- ✅ Builds common phrase dictionary
- ❌ Not used by agent (placeholder in agent.py line 284)
- ❌ No actual implementation of fetching sent emails from providers
- ❌ No scheduled learning via Celery (task exists but not functional)

### 6. Policy Engine

#### Worth-Sending Policy (`policy/worth_sending_policy.py`)
**Status:** Implemented
- ✅ Hardcoded safety checks (not AI-dependent)
- ✅ No-reply address detection
- ✅ Newsletter/automated detection
- ✅ Sensitive topic detection
- ✅ First-time sender detection
- ✅ Confidence threshold check
- ✅ Rate limit check
- ✅ Real person/service check
- ✅ Question/action request check
- ✅ Complete implementation

#### Send Flow (`policy/send_flow.py`)
**Status:** Implemented
- ✅ Three autonomy modes (approve, auto_safe, auto_full)
- ✅ 60-second delayed send
- ✅ Cancelable undo window
- ✅ Routine reply detection
- ✅ Draft status management
- ✅ Complete implementation

#### Safety Rules (`policy/safety_rules.py`)
**Status:** Implemented
- ✅ Sensitive topic detection (money, legal, medical, HR, compliance)
- ✅ First-time sender detection
- ✅ Emotional content detection
- ✅ Ambiguous content detection
- ✅ Override mechanism
- ✅ Complete implementation

#### Rate Limiter (`policy/rate_limiter.py`)
**Status:** Implemented
- ✅ Max N auto-replies per hour
- ✅ Max one reply per thread per day
- ✅ Per-account tracking
- ✅ Automatic cleanup of old entries
- ✅ Complete implementation

### 7. Database Layer

**File:** `core/database.py`
**Status:** Partially implemented
- ✅ Supabase client initialization
- ✅ Email CRUD operations
- ✅ Classification CRUD operations
- ✅ Draft CRUD operations
- ✅ Audit log operations
- ✅ Voice profile operations
- ✅ Rate limit operations
- ✅ Kill switch operations
- ✅ Account management
- ❌ No integration with v2 encrypted secrets
- ❌ Credentials stored as plain JSONB (not encrypted)
- ❌ No row-level security policy implementation
- ❌ No transaction handling
- ❌ No connection pooling
- ❌ No retry logic for transient failures

**Schema File:** `supabase/migrations/001_initial_schema.sql`
**Status:** Complete
- ✅ All tables defined (users, email_accounts, emails, classifications, drafts, audit_log, user_voice_profile, rate_limits, kill_switch)
- ✅ Proper foreign key relationships
- ✅ Indexes for performance
- ✅ Check constraints for enums
- ✅ Row-level security enabled (but policies not defined)
- ❌ RLS policies are placeholder comments only
- ❌ No actual access control policies defined

### 8. Agent Orchestrator

**File:** `core/agent.py`
**Status:** Partially implemented
- ✅ Main orchestration logic
- ✅ Component initialization
- ✅ Email processing pipeline
- ✅ Provider loading
- ✅ Thread and sender history fetching
- ✅ Classification integration
- ✅ Safety rule checking
- ✅ Label/folder application
- ✅ Draft generation
- ✅ Worth-sending policy check
- ✅ Rate limiting
- ✅ Send flow processing
- ✅ Kill switch check
- ❌ Uses v1 providers (not v2 MailProvider)
- ❌ Uses v1 classifier (not v2 LLMProvider)
- ❌ No integration with v2 prefilter
- ❌ No integration with v2 prompt guard
- ❌ No integration with v2 encrypted secrets
- ❌ Voice profile learning is placeholder (line 284)
- ❌ No error recovery or retry logic
- ❌ No telemetry or metrics collection

### 9. Dashboard API

**File:** `dashboard/app.py`
**Status:** Partially implemented
- ✅ FastAPI application
- ✅ Status endpoint
- ✅ Kill switch endpoints
- ✅ Account management endpoints
- ✅ Email retrieval endpoints
- ✅ Draft approval endpoints
- ✅ Audit log endpoints
- ✅ Voice profile endpoints
- ✅ Rate limit endpoints
- ✅ Statistics endpoints
- ❌ No authentication/authorization
- ❌ Permissive CORS (allow_origins=["*"])
- ❌ No user context in endpoints (user_id as query param, not authenticated)
- ❌ No integration with v2 encrypted secrets
- ❌ No model slot configuration endpoints
- ❌ No provider configuration endpoints
- ❌ No BYOK credential management endpoints

**Security Issue:** Dashboard has no authentication. Any user can:
- Toggle kill switch
- Approve/reject any draft
- View any email
- View audit logs
- Modify rate limits
- Access any user's data via user_id parameter

### 10. Background Worker

**File:** `worker.py`
**Status:** Partially implemented
- ✅ Celery app initialization
- ✅ Process account task
- ✅ Learn voice profile task
- ✅ Process all accounts task
- ✅ Beat scheduler configuration
- ✅ Task serialization and error handling
- ❌ Hardcoded user_id in beat schedule (line 121, 126)
- ❌ No per-user scheduling
- ❌ No retry/backoff for transient failures
- ❌ No dead letter queue
- ❌ No task monitoring
- ❌ No integration with v2 prefilter or LLM providers

### 11. Frontend

**Files:** `index.html`, `app.js`, `styles.css`
**Status:** Static demo only
- ✅ Professional UI design
- ✅ Inbox layout with filters
- ✅ Agent status display
- ✅ Activity feed UI
- ✅ Command palette (Ctrl+K/Cmd+K)
- ✅ Mode indicator
- ✅ Usage meter
- ❌ No API integration
- ❌ No real data fetching
- ❌ No draft approval flow
- ❌ No kill switch control
- ❌ No settings page
- ❌ No account connection flow
- ❌ Hardcoded sample data
- ❌ CSS is minified (hard to maintain)

**Frontend is a visual prototype only, not a functional application.**

---

## Security Analysis

### Critical Security Issues

1. **No Authentication on Dashboard**
   - File: `dashboard/app.py`
   - Issue: All endpoints are public
   - Impact: Any attacker can control the system
   - Severity: CRITICAL

2. **Permissive CORS Policy**
   - File: `dashboard/app.py` line 19-25
   - Issue: `allow_origins=["*"]`
   - Impact: Cross-origin requests from any domain
   - Severity: HIGH

3. **Insecure Direct Object Reference**
   - File: `dashboard/app.py`
   - Issue: user_id passed as query parameter, not authenticated
   - Impact: Users can access other users' data
   - Severity: CRITICAL

4. **Unencrypted Credentials in Database**
   - File: `core/database.py`
   - Issue: Credentials stored as plain JSONB
   - Issue: v2 secret_store exists but not used
   - Impact: Database compromise exposes OAuth tokens and passwords
   - Severity: CRITICAL

5. **No Row-Level Security Policies**
   - File: `supabase/migrations/001_initial_schema.sql`
   - Issue: RLS enabled but no policies defined
   - Impact: Service role key bypasses all access control
   - Severity: HIGH

6. **No API Key Validation**
   - File: `classifier/email_classifier.py`
   - Issue: Empty API key accepted (line 18)
   - Impact: Silent failures, unclear error messages
   - Severity: MEDIUM

### Security Features Implemented

✅ Prompt injection defense (`core/prompt_guard.py`)
✅ Deterministic prefiltering (`core/prefilter.py`)
✅ AES-GCM encryption implementation (`core/secret_store.py`)
✅ Safety rules for sensitive topics
✅ Rate limiting
✅ Kill switch
✅ Audit logging

**Note:** Security features exist but are not integrated into the main pipeline.

---

## Testing Analysis

### Test Execution Attempt

**Command:** `python -m pytest -q`
**Result:** FAILED - Import errors

**Error:** `ModuleNotFoundError: No module named 'pydantic_settings'`

**Issue:** Tests cannot run because required dependencies are not installed.

### Test Files

#### test_foundation.py
**Status:** Tests v2 foundation components
- ✅ Prefilter tests (newsletter, no-reply detection)
- ✅ Prompt guard tests (instruction detection)
- ✅ Secret store tests (encryption/decryption)
- ✅ Provider registry tests (model slots)
- ✅ LLM response tests (token counting)
- ❌ Cannot execute due to missing dependencies
- **Coverage:** v2 components only

#### test_acceptance.py
**Status:** Tests v1 classification with sample emails
- ✅ 15 sample emails covering all categories
- ✅ Classification accuracy test
- ✅ Worth-sending policy tests
- ✅ Safety rules tests
- ✅ No-reply detection tests
- ❌ Cannot execute due to missing dependencies
- ❌ Tests require Claude API key to run
- **Coverage:** v1 classification and policy

#### test_send_flow.py
**Status:** Tests autonomy modes
- ✅ Approve mode tests
- ✅ Auto-safe mode tests
- ✅ Auto-full mode tests
- ✅ Draft cancellation tests
- ❌ Cannot execute due to missing dependencies
- **Coverage:** Send flow component

#### test_rate_limiter.py
**Status:** Tests rate limiting
- ✅ Initial rate limit tests
- ✅ Hourly limit tests
- ✅ Per-thread per-day tests
- ✅ Account separation tests
- ✅ Old entry cleanup tests
- ❌ Cannot execute due to missing dependencies
- **Coverage:** Rate limiter component

### Test Coverage Gaps

❌ No integration tests (end-to-end flow)
❌ No provider tests (Gmail, IMAP)
❌ No database integration tests
❌ No API endpoint tests
❌ No authentication tests
❌ No encryption/decryption integration tests
❌ No Celery task tests
❌ No frontend tests

---

## Documentation Analysis

### README.md
**Status:** Outdated
- ✅ Describes v2 BYOK architecture
- ✅ Lists features
- ✅ Provides setup instructions
- ❌ Setup instructions don't work (missing dependencies)
- ❌ Claims 28 tests passed (tests don't run)
- ❌ References v2 folder structure that doesn't match reality
- ❌ No mention of v1/v2 dual architecture problem

### ARCHITECTURE.md
**Status:** Describes v2, not v1
- ✅ Comprehensive v2 architecture description
- ✅ Data flow diagram
- ✅ Safety architecture
- ❌ Does not reflect actual implementation (v1 active, v2 unused)
- ❌ No mention of integration path between v1 and v2
- ❌ No acknowledgment of dual architecture problem

### USAGE.md
**Status:** Detailed but inaccurate
- ✅ Detailed usage examples
- ✅ Configuration examples
- ✅ API usage examples
- ❌ Examples won't work (missing dependencies)
- ❌ References v2 features that aren't integrated
- ❌ No mention of v1/v2 duality

### DEPLOYMENT.md
**Status:** Complete but won't work
- ✅ Render deployment steps
- ✅ Supabase setup
- ✅ Redis setup
- ❌ Application won't run (missing dependencies)
- ❌ No migration from v1 to v2
- ❌ No production hardening steps

### DAILY-DEVELOPER-LOG.md
**Status:** Accurate for v2 work
- ✅ Lists v2 foundation work completed
- ✅ Claims 28 tests passed
- ❌ Tests don't actually run in current environment
- ❌ No mention of v1/v2 integration work needed

### PROJECT_SUMMARY.md
**Status:** Misleading
- ✅ Lists all components
- ❌ Claims everything is "completed"
- ❌ No mention of v1/v2 dual architecture
- ❌ No mention of missing integration
- ❌ No mention of test failures

---

## Integration Status

### v1 → v2 Migration Path

**Status:** NOT DEFINED

The repository has no clear path to migrate from v1 to v2 architecture. Key missing pieces:

1. **No Adapter Layer**
   - No adapters to make v1 providers implement v2 MailProvider contract
   - No adapters to make v1 classifiers use v2 LLMProvider interface

2. **No Configuration Migration**
   - No way to configure model slots in v2 registry
   - No way to configure BYOK credentials via v2 secret_store
   - No migration of existing plain-text credentials to encrypted storage

3. **No Pipeline Integration**
   - v2 prefilter not integrated into agent pipeline
   - v2 prompt guard not integrated into classifier/draft generator
   - v2 encrypted secrets not used by database layer

4. **No Gradual Rollout**
   - No feature flags to enable v2 components incrementally
   - No A/B testing capability
   - No rollback mechanism

---

## Data Flow Analysis

### Current Flow (v1 Implementation)

```
Email Received
  ↓
Provider.fetch_emails() [v1 EmailProviderInterface]
  ↓
Database.save_email()
  ↓
Provider.fetch_thread() [v1]
  ↓
Provider.fetch_sender_history() [v1 - placeholder]
  ↓
Classifier.classify() [v1 - direct Claude API call]
  ↓
SafetyRules.should_flag_for_human()
  ↓
Provider.apply_label() [v1]
  ↓
DraftGenerator.generate_draft() [v1 - direct Claude API call]
  ↓
WorthSendingPolicy.should_send_reply()
  ↓
RateLimiter.check_rate_limit()
  ↓
SendFlow.process_draft()
  ↓
Provider.create_draft() [v1]
  ↓
Provider.send_reply() [v1]
  ↓
Database.update_draft_status()
  ↓
Audit logging
```

**Issues:**
- ❌ v2 prefilter not used
- ❌ v2 prompt guard not used
- ❌ v2 LLMProvider not used
- ❌ v2 MailProvider not used
- ❌ v2 encrypted secrets not used
- ❌ v2 model slots not used

### Intended v2 Flow (Not Implemented)

```
Email Received
  ↓
MailProvider.list_new() [v2]
  ↓
Prefilter.inspect() [v2 - zero-token filtering]
  ↓
Database.save_email()
  ↓
MailProvider.get_thread() [v2]
  ↓
LLMProvider.complete() [v2 - classification slot]
  ↓
PromptGuard.wrap_untrusted() [v2]
  ↓
SafetyRules.should_flag_for_human()
  ↓
MailProvider.label() [v2]
  ↓
LLMProvider.complete() [v2 - drafting slot]
  ↓
PromptGuard.wrap_untrusted() [v2]
  ↓
WorthSendingPolicy.should_send_reply()
  ↓
RateLimiter.check_rate_limit()
  ↓
SendFlow.process_draft()
  ↓
MailProvider.send() [v2]
  ↓
SecretStore.decrypt() [v2 - for credentials]
  ↓
Audit logging
```

---

## Provider Integration Status

### Gmail
**Status:** Partially implemented (v1)
- ✅ OAuth2 authentication flow
- ✅ Gmail API integration
- ✅ Email fetching
- ✅ Thread fetching
- ✅ Label application
- ✅ Draft creation
- ✅ Send reply
- ❌ No integration with v2 MailProvider
- ❌ No error recovery
- ❌ No retry logic
- ❌ No rate limiting at API level
- ❌ No incremental sync
- ❌ No webhook support

### IMAP (Yahoo, Generic)
**Status:** Partially implemented (v1)
- ✅ Basic IMAP connection
- ✅ Email fetching
- ✅ Thread reconstruction
- ✅ Label application (as flags)
- ✅ Archive (move to folder)
- ❌ No SMTP for sending
- ❌ No integration with v2 MailProvider
- ❌ No TLS configuration
- ❌ No timeout handling
- ❌ No connection pooling
- ❌ No incremental sync
- ❌ No error recovery

### Microsoft Graph
**Status:** NOT IMPLEMENTED
- ❌ Mentioned in documentation but no code exists
- ❌ No provider implementation

### iCloud
**Status:** NOT IMPLEMENTED
- ❌ Mentioned in documentation but no code exists
- ❌ No provider implementation

### Custom Domains
**Status:** PARTIAL (via IMAP)
- ✅ Can use generic IMAP
- ❌ No domain-specific optimizations
- ❌ No custom configuration support

---

## Email Domain Model

### Current Model (v1)
**File:** `core/types.py` - EmailMessage
```python
- message_id: str
- thread_id: Optional[str]
- sender: str
- sender_email: str
- subject: str
- body: str
- received_at: datetime
- raw_headers: Dict[str, Any]
- recipients: List[str]
- cc: List[str]
- in_reply_to: Optional[str]
- references: List[str]
```

**Status:** Adequate for basic use
- ✅ Contains essential fields
- ❌ No content_hash (deduplication)
- ❌ No is_read flag
- ❌ No html_body field
- ❌ No attachments support
- ❌ No sync_checkpoint (incremental sync)

### v2 Model
**File:** `mail/base.py` - MailMessage
```python
- message_id: str
- thread_id: str
- sender: str
- sender_email: str
- recipients: List[str]
- subject: str
- text_body: str
- html_body: Optional[str]
- received_at: datetime
- headers: Dict[str, str]
- content_hash: str
- is_read: bool
```

**Status:** Better model but not used
- ✅ Includes content_hash for deduplication
- ✅ Includes html_body
- ✅ Includes is_read flag
- ❌ Not used by v1 implementation
- ❌ No attachments support

---

## AI Integration Analysis

### Claude API Usage

**Files:** `classifier/email_classifier.py`, `classifier/draft_generator.py`

**Implementation:**
- Direct HTTP calls via httpx
- Hardcoded model: `claude-3-sonnet-20240229`
- No token counting
- No budget tracking
- No retry logic
- No fallback when API fails (classifier has fallback, draft generator does not)

**Prompt Construction:**
- System prompt + email content
- No prompt guard wrapping
- No structured output validation
- No confidence threshold enforcement
- No instruction separation from data

**Safety:**
- ❌ Email content not wrapped as untrusted
- ❌ No validation of structured outputs
- ❌ No fingerprinting of model-generated instructions
- ❌ No protection against prompt injection

### BYOK/BYOG Support

**Status:** v2 foundation exists but not integrated

**v2 Components:**
- ✅ LLMProvider contract defined
- ✅ Model slot registry
- ✅ Encrypted secret storage
- ✅ Provider-agnostic interface

**Integration:**
- ❌ No actual provider implementations (Claude, GPT, Gemini, Ollama)
- ❌ No integration with v1 classifiers
- ❌ No integration with v1 draft generators
- ❌ No configuration UI
- ❌ No credential management

---

## External Side Effects

### Email Sending

**Implementation:** `providers/gmail_provider.py` send_reply()
**Status:** Implemented via Gmail API
- ✅ Can send emails
- ❌ No validation of recipient addresses
- ❌ No size limits
- ❌ No attachment support
- ❌ No retry on failure
- ❌ No undo after send (only delay before send)

### Label Application

**Implementation:** `providers/gmail_provider.py` apply_label()
**Status:** Implemented
- ✅ Can apply labels
- ❌ No validation of label names
- ❌ No label creation if missing
- ❌ No error handling

### Archiving

**Implementation:** `providers/gmail_provider.py` archive()
**Status:** Implemented
- ✅ Can archive emails
- ❌ No confirmation
- ❌ No undo

### Draft Creation

**Implementation:** `providers/gmail_provider.py` create_draft()
**Status:** Implemented
- ✅ Can create drafts
- ❌ No validation of draft content
- ❌ No size limits

### Authorization Checks

**Status:** NONE
- ❌ No authorization checks before sending
- ❌ No authorization checks before labeling
- ❌ No authorization checks before archiving
- ❌ No authorization checks before creating drafts
- ❌ Dashboard endpoints have no authentication

**Security Risk:** Any request to dashboard API can perform these actions.

---

## Logging and Observability

### Current Logging

**Status:** Minimal
- Print statements in various files
- No structured logging
- No log levels
- No log aggregation
- No metrics collection

### Audit Logging

**Implementation:** `core/database.py` log_audit()
**Status:** Implemented
- ✅ Records all decisions
- ✅ Includes reason, confidence, context
- ✅ Timestamp
- ❌ No log of raw email content (good for privacy)
- ❌ No log of prompts sent to AI
- ❌ No log of AI responses
- ❌ No aggregation or querying by time range
- ❌ No alerting on failures

### Potential Information Leakage

**Risk Assessment:**
- ✅ Credentials not logged (encrypted storage)
- ✅ Email content not in audit log
- ⚠️ Prompts may contain email content (not logged)
- ⚠️ AI responses not logged (may contain sensitive info)
- ❌ No sanitization of error messages
- ❌ No redaction of personal data in logs

---

## Deployment Configuration

### Dockerfile
**Status:** Basic
- ✅ Uses Python 3.13
- ✅ Installs dependencies
- ✅ Copies application
- ❌ No health check
- ❌ No non-root user
- ❌ No multi-stage build
- ❌ No optimization for image size

### docker-compose.yml
**Status:** Basic
- ✅ Defines dashboard, worker, redis services
- ✅ Uses env_file
- ✅ Depends on for redis
- ❌ No Celery beat service
- ❌ No Supabase service (assumes external)
- ❌ No volume mounts
- ❌ No network isolation
- ❌ No restart policies

### render.yaml
**Status:** Complete but for v1
- ✅ Defines worker, dashboard, beat services
- ✅ Redis database
- ✅ Environment variables
- ❌ No migration strategy
- ❌ No health checks
- ❌ No auto-scaling configuration
- ❌ Assumes v1 implementation

### Environment Configuration

**File:** `.env.example`
**Status:** Comprehensive
- ✅ BYOK provider credentials
- ✅ Supabase configuration
- ✅ Redis configuration
- ✅ Gmail OAuth
- ✅ Application settings
- ✅ Model configuration
- ❌ No validation of values
- ❌ No documentation of required vs optional

---

## Feature Inventory

### Core Features

| Feature | Status | Evidence | Dependencies | Recommendation |
|---------|--------|----------|--------------|----------------|
| Email fetching (Gmail) | Partially Implemented | `providers/gmail_provider.py` | Google APIs, OAuth | Integrate with v2 MailProvider |
| Email fetching (IMAP) | Partially Implemented | `providers/imap_provider.py` | imap-tools | Add SMTP, error recovery |
| Email classification | Partially Implemented | `classifier/email_classifier.py` | Claude API | Integrate with v2 LLMProvider |
| Draft generation | Partially Implemented | `classifier/draft_generator.py` | Claude API | Integrate with v2 LLMProvider |
| Voice profile learning | Implemented but not integrated | `classifier/voice_profile_learner.py` | None | Integrate into agent pipeline |
| Worth-sending policy | Implemented | `policy/worth_sending_policy.py` | None | Already complete |
| Autonomy modes | Implemented | `policy/send_flow.py` | None | Already complete |
| Safety rules | Implemented | `policy/safety_rules.py` | None | Already complete |
| Rate limiting | Implemented | `policy/rate_limiter.py` | None | Already complete |
| Kill switch | Implemented | `database.py` | None | Already complete |
| Audit logging | Implemented | `database.py` | None | Already complete |
| 60-second delayed send | Implemented | `policy/send_flow.py` | None | Already complete |
| Deterministic prefiltering | Implemented but not integrated | `core/prefilter.py` | None | Integrate into agent pipeline |
| Prompt injection defense | Implemented but not integrated | `core/prompt_guard.py` | None | Integrate into classifier/draft generator |
| Encrypted secrets | Implemented but not integrated | `core/secret_store.py` | None | Integrate into database layer |
| BYOK/BYOG support | Foundation only | `llm/base.py`, `llm/registry.py` | None | Implement provider adapters |
| Model slot registry | Implemented but not integrated | `llm/registry.py` | None | Integrate into agent |
| Dashboard API | Partially Implemented | `dashboard/app.py` | FastAPI | Add authentication |
| Frontend UI | Static demo only | `index.html`, `app.js` | None | Build real frontend |

### Integration Features

| Feature | Status | Evidence | Dependencies | Recommendation |
|---------|--------|----------|--------------|----------------|
| Gmail OAuth2 | Implemented | `providers/gmail_provider.py` | Google Auth | Integrate with v2 |
| Microsoft Graph | Not Implemented | None | Microsoft Graph | Implement if needed |
| Yahoo IMAP | Partially Implemented | `providers/imap_provider.py` | imap-tools | Add SMTP |
| Generic IMAP | Partially Implemented | `providers/imap_provider.py` | imap-tools | Add SMTP |
| iCloud | Not Implemented | None | iCloud APIs | Defer |
| Custom domains | Partial (IMAP) | `providers/imap_provider.py` | IMAP | Add SMTP |

### Safety Features

| Feature | Status | Evidence | Dependencies | Recommendation |
|---------|--------|----------|--------------|----------------|
| No-reply detection | Implemented | `policy/worth_sending_policy.py` | None | Already complete |
| Newsletter detection | Implemented | `policy/worth_sending_policy.py` | None | Already complete |
| Sensitive topic detection | Implemented | `policy/safety_rules.py` | None | Already complete |
| First-time sender detection | Implemented | `policy/safety_rules.py` | None | Already complete |
| Emotional content detection | Implemented | `policy/safety_rules.py` | None | Already complete |
| Rate limiting | Implemented | `policy/rate_limiter.py` | None | Already complete |
| Prompt injection defense | Implemented but not integrated | `core/prompt_guard.py` | None | Integrate |
| Encrypted credentials | Implemented but not integrated | `core/secret_store.py` | None | Integrate |

---

## Critical Blockers

### 1. Missing Dependencies (BLOCKS ALL TESTING)
**File:** `requirements.txt`
**Issue:** pydantic-settings and other critical packages not installed
**Impact:** Cannot run tests, cannot start application
**Fix:** Install missing dependencies
**Effort:** 5 minutes

### 2. No Authentication (CRITICAL SECURITY)
**File:** `dashboard/app.py`
**Issue:** All endpoints are public
**Impact:** Any attacker can control the system
**Fix:** Implement authentication middleware
**Effort:** 2-3 days

### 3. Unencrypted Credentials (CRITICAL SECURITY)
**File:** `core/database.py`
**Issue:** Credentials stored as plain JSONB
**Impact:** Database compromise exposes OAuth tokens
**Fix:** Integrate v2 secret_store
**Effort:** 1 day

### 4. v1/v2 Dual Architecture (BLOCKS V2 FEATURES)
**Files:** All agent, classifier, provider files
**Issue:** v2 interfaces defined but not used
**Impact:** Cannot use BYOK, prefiltering, prompt guard
**Fix:** Migrate v1 to v2 or create adapter layer
**Effort:** 5-7 days

### 5. No SMTP for Sending (BLOCKS IMAP PROVIDERS)
**File:** `providers/imap_provider.py`
**Issue:** create_draft() is placeholder
**Impact:** Cannot send emails from IMAP accounts
**Fix:** Implement SMTP
**Effort:** 1-2 days

### 6. Tests Don't Run (BLOCKS VALIDATION)
**Files:** All test files
**Issue:** Missing dependencies cause import errors
**Impact:** Cannot validate changes
**Fix:** Install dependencies, fix imports
**Effort:** 30 minutes

---

## Important Improvements

### 1. Frontend Integration
**Status:** Static demo only
**Impact:** No functional user interface
**Recommendation:** Build React/Next.js frontend with API integration
**Effort:** 5-7 days

### 2. Error Recovery
**Status:** Minimal error handling
**Impact:** Transient failures cause permanent failures
**Recommendation:** Add retry logic with exponential backoff
**Effort:** 2-3 days

### 3. Incremental Sync
**Status:** Full mailbox scans
**Impact:** Wasteful, slow, hits API limits
**Recommendation:** Implement cursor-based sync
**Effort:** 2-3 days

### 4. Row-Level Security Policies
**Status:** RLS enabled but no policies
**Impact:** No actual access control
**Recommendation:** Define RLS policies in Supabase
**Effort:** 1 day

### 5. Monitoring and Metrics
**Status:** Minimal logging
**Impact:** No visibility into system health
**Recommendation:** Add structured logging, metrics collection
**Effort:** 2-3 days

### 6. Provider-Specific Optimizations
**Status:** Generic implementation
**Impact:** Suboptimal performance
**Recommendation:** Add provider-specific optimizations
**Effort:** 3-5 days

---

## Optional Polish

### 1. Attachment Support
**Status:** Not implemented
**Recommendation:** Add attachment handling
**Effort:** 2-3 days

### 2. Webhook Support
**Status:** Not implemented
**Recommendation:** Add webhook-based push notifications
**Effort:** 2-3 days

### 3. Multi-Tenant Support
**Status:** Single-user only
**Recommendation:** Add team/organization support
**Effort:** 5-7 days

### 4. Advanced Voice Profile
**Status:** Basic implementation
**Recommendation:** Add context-aware style, recipient-specific tone
**Effort:** 3-5 days

### 5. Calendar Integration
**Status:** Not implemented
**Recommendation:** Add calendar event detection
**Effort:** 2-3 days

---

## Prioritized Technical Gaps

### Priority 1: Blockers (Must Fix Before Hackathon)

1. **Install Missing Dependencies** (5 min)
   - Install pydantic-settings
   - Install other missing packages
   - Verify tests run

2. **Add Authentication to Dashboard** (2-3 days)
   - Implement JWT or session-based auth
   - Add authentication middleware
   - Secure all endpoints
   - Fix CORS policy

3. **Integrate v2 Encrypted Secrets** (1 day)
   - Modify database.py to use secret_store
   - Migrate existing credentials to encrypted format
   - Add migration script

4. **Define v1→v2 Migration Path** (1 day)
   - Decide: migrate v1 to v2 or create adapter layer
   - Document the approach
   - Create implementation plan

### Priority 2: Critical Gaps (Must Fix for Hackathon Success)

5. **Implement SMTP for IMAP Providers** (1-2 days)
   - Add SMTP to imap_provider.py
   - Implement send_reply with SMTP
   - Add error handling

6. **Integrate v2 Prefilter into Agent Pipeline** (1 day)
   - Add prefilter before classification
   - Skip model calls for filtered emails
   - Update audit logging

7. **Integrate v2 Prompt Guard** (1 day)
   - Wrap email content before sending to AI
   - Add to classifier and draft generator
   - Validate no instruction execution

8. **Fix Test Suite** (30 min)
   - Install dependencies
   - Fix import errors
   - Verify all tests pass
   - Add integration tests

### Priority 3: Important Improvements (Should Fix for Production)

9. **Implement Error Recovery** (2-3 days)
   - Add retry logic with exponential backoff
   - Add dead letter queue for failed tasks
   - Add monitoring for retry attempts

10. **Implement Incremental Sync** (2-3 days)
    - Add cursor/sync checkpoint tracking
    - Fetch only new messages
    - Handle provider-specific sync events

11. **Define RLS Policies** (1 day)
    - Write Row-Level Security policies
    - Test access control
    - Document policy rules

12. **Add Structured Logging** (1 day)
    - Replace print statements with logging
    - Add log levels
    - Add context to logs

### Priority 4: Polish (Nice to Have)

13. **Build Real Frontend** (5-7 days)
    - React/Next.js application
    - API integration
    - Authentication
    - Real-time updates

14. **Add Monitoring** (2-3 days)
    - Metrics collection
    - Dashboard visualization
    - Alerting

15. **Optimize Provider Implementations** (3-5 days)
    - Provider-specific optimizations
    - Connection pooling
    - Rate limiting at provider level

---

## Next Required Tasks

### Immediate (Before Any Development)

1. **Install Dependencies**
   ```bash
   pip install pydantic-settings supabase celery redis imap-tools google-api-python-client google-auth-oauthlib google-auth-httplib2 anthropic
   ```

2. **Verify Tests Run**
   ```bash
   python -m pytest -q
   ```

3. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

### For Hackathon Success

4. **Decide v1→v2 Strategy**
   - Option A: Migrate v1 to v2 (cleaner, more work)
   - Option B: Create adapter layer (faster, more technical debt)
   - Document decision

5. **Implement Critical Security Fixes**
   - Add authentication to dashboard
   - Integrate encrypted secrets
   - Define RLS policies

6. **Integrate v2 Foundation Components**
   - Prefilter into agent pipeline
   - Prompt guard into AI calls
   - Model slot registry into agent

7. **Complete IMAP SMTP**
   - Implement send_reply with SMTP
   - Add error handling

8. **Fix and Expand Tests**
   - Make tests runnable
   - Add integration tests
   - Add end-to-end tests

---

## Known Limitations

### Current Implementation

1. **Dual Architecture Problem**
   - v1 and v2 coexist without integration
   - No clear migration path
   - v2 features unused

2. **No Authentication**
   - Dashboard completely public
   - No access control
   - Security vulnerability

3. **Unencrypted Credentials**
   - OAuth tokens stored in plain text
   - Passwords stored in plain text
   - Security vulnerability

4. **Incomplete IMAP Support**
   - No SMTP for sending
   - No incremental sync
   - No error recovery

5. **No BYOK Integration**
   - v2 secret store exists but unused
   - v2 LLM provider exists but unused
   - Hardcoded Claude API usage

6. **Frontend is Static Demo**
   - No API integration
   - No real functionality
   - Hardcoded data

7. **Tests Don't Run**
   - Missing dependencies
   - Cannot validate changes
   - No CI/CD

### Architecture Limitations

1. **No Webhook Support**
   - Only polling
   - Delayed email processing
   - Higher API usage

2. **No Attachment Support**
   - Email bodies only
   - Cannot handle attachments
   - Limited functionality

3. **No Multi-Tenant Support**
   - Single-user only
   - No team features
   - No organization support

4. **No Calendar Integration**
   - No event detection
   - No scheduling
   - Limited context

---

## Summary for Next Developer

### Repository State

The MailAgent repository contains a partially implemented email agent with two parallel architectures (v1 and v2) that are not integrated. The v1 implementation has working components (classification, drafting, safety rules, rate limiting) but uses direct Claude API calls and lacks security features. The v2 foundation provides provider-neutral interfaces, encrypted secrets, deterministic prefiltering, and prompt injection defense, but these components are not integrated into the main pipeline.

### Critical Issues

1. **Dependencies not installed** - Tests cannot run
2. **No authentication** - Dashboard is completely public
3. **Unencrypted credentials** - OAuth tokens stored in plain text
4. **v1/v2 dual architecture** - No integration path defined
5. **No SMTP for IMAP** - Cannot send emails from IMAP accounts

### Working Components

- Email classification (Claude API)
- Draft generation (Claude API)
- Safety rules (hardcoded)
- Rate limiting
- Autonomy modes
- Kill switch
- Audit logging
- Worth-sending policy
- Gmail provider (partial)
- IMAP provider (partial - no SMTP)

### Not Working Components

- v2 prefiltering (not integrated)
- v2 prompt guard (not integrated)
- v2 encrypted secrets (not integrated)
- v2 LLM provider (not integrated)
- v2 model slots (not integrated)
- Frontend (static demo only)
- Tests (missing dependencies)
- Authentication (not implemented)
- RLS policies (not defined)

### Recommended Approach

1. **First:** Install dependencies and verify tests run
2. **Second:** Decide on v1→v2 migration strategy
3. **Third:** Implement critical security fixes (authentication, encrypted secrets)
4. **Fourth:** Integrate v2 foundation components into pipeline
5. **Fifth:** Complete IMAP SMTP implementation
6. **Sixth:** Build real frontend with API integration

### Files to Modify First

1. `requirements.txt` - Ensure all dependencies listed
2. `dashboard/app.py` - Add authentication middleware
3. `core/database.py` - Integrate secret_store for credentials
4. `core/agent.py` - Integrate prefilter and prompt guard
5. `providers/imap_provider.py` - Add SMTP implementation

### Commands to Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest -q

# Start dashboard
python -m mailagent.dashboard.app

# Start worker
celery -A mailagent.worker worker --loglevel=info

# Start beat scheduler
celery -A mailagent.worker beat --loglevel=info
```

### Environment Variables Required

- `ANTHROPIC_API_KEY` (for Claude API)
- `SUPABASE_URL` (for database)
- `SUPABASE_SERVICE_ROLE_KEY` (for database)
- `REDIS_URL` (for Celery)
- `MAILAGENT_ENCRYPTION_KEY` (for v2 secret store)
- `GOOGLE_CLIENT_ID` (for Gmail OAuth)
- `GOOGLE_CLIENT_SECRET` (for Gmail OAuth)

### Test Execution Evidence

**Status:** Tests cannot run due to missing dependencies
**Command Attempted:** `python -m pytest -q`
**Result:** FAILED with `ModuleNotFoundError: No module named 'pydantic_settings'`
**Expected:** 28 tests passing (per DAILY-DEVELOPER-LOG.md)
**Actual:** 4 collection errors

---

## Conclusion

The MailAgent repository has a solid foundation with well-designed v2 interfaces and comprehensive safety policies, but it suffers from a critical dual architecture problem where v1 and v2 coexist without integration. The immediate blockers are missing dependencies, lack of authentication, and unencrypted credentials. For a successful 12-day hackathon, the team must first resolve these critical issues, then decide on a clear v1→v2 migration strategy before implementing new features.

**Estimated Time to Production-Ready:** 3-4 weeks (with full team)
**Estimated Time to Hackathon Demo:** 5-7 days (with focused scope)
**Recommended Hackathon Scope:** Focus on v1 integration with v2 security features, defer BYOK provider variety, use static frontend.
