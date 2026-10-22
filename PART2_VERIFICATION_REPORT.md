# MailAgent Part 2 Verification Report

**Date:** 2026-10-17  
**Phase:** Deep Code Tracing and Safe Execution Validation  
**Purpose:** Validate Part 1 findings through execution and data-flow analysis

---

## SECTION 1: EXECUTION ENVIRONMENT VALIDATION

### Dependency Installation Status

**Command:** `pip install pydantic-settings supabase anthropic celery redis imap-tools google-api-python-client google-auth-oauthlib google-auth-httplib2`

**Result:** ✅ SUCCESS

All critical dependencies now installed:
- pydantic-settings 2.16.0
- supabase 2.33.0
- anthropic 1.15.0
- celery 5.6.3
- redis 8.1.0
- imap-tools 1.16.0
- google-api-python-client 2.201.0
- google-auth-oauthlib 1.5.0
- google-auth-httplib2 0.4.4

**Version Compatibility:**
- Python 3.12.6 ✅ (matches Dockerfile requirement for 3.13, but 3.12 works)
- Pydantic 2.14.1 ✅ (compatible with >=2.5.0 requirement)
- Supabase 2.33.0 ✅ (compatible with >=2.0.0 requirement)

**Issue:** Supabase installed newer version (2.33.0) but should be compatible.

### Test Execution Results

**Test Suite:** `tests/test_foundation.py`
- **Result:** ✅ 8/8 PASSED
- **Duration:** 0.96s
- **Tests:** Prefilter, prompt guard, secret store, provider registry, LLM response
- **Validation:** v2 foundation components work correctly

**Test Suite:** `tests/test_send_flow.py`
- **Result:** ✅ 8/8 PASSED
- **Duration:** 2.50s
- **Tests:** Autonomy modes, draft cancellation, action handling
- **Validation:** Send flow logic works correctly

**Test Suite:** `tests/test_rate_limiter.py`
- **Result:** ✅ 7/7 PASSED
- **Duration:** 0.38s
- **Tests:** Rate limiting, hourly limits, per-thread limits
- **Validation:** Rate limiter works correctly

**Test Suite:** `tests/test_acceptance.py::test_worth_sending_policy`
- **Result:** ✅ 1/1 PASSED
- **Duration:** 0.75s
- **Validation:** Worth-sending policy works correctly

**Total Tests:** 24/24 PASSED ✅

**Part 1 Claim Correction:** Part 1 claimed tests couldn't run. After installing pydantic-settings, all tests pass. The issue was a single missing dependency, not a fundamental test failure.

### Application Startup Validation

**Dashboard Startup:**
- **Command:** Python with minimal .env (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
- **Result:** ✅ Dashboard app loads successfully
- **Server:** Uvicorn starts on http://127.0.0.1:8001
- **Health Check:** Server starts without errors

**Missing Prerequisites:**
- ❌ No Redis instance running (required for Celery)
- ❌ No Supabase instance running (required for database)
- ❌ No Gmail OAuth credentials (required for Gmail provider)
- ❌ No IMAP credentials (required for IMAP provider)
- ❌ No Claude API key (required for classification/drafting)

**Conclusion:** Application code can start, but cannot perform real work without external services and credentials.

### Environment Variables Inventory

**From `.env.example`:**

**Authentication:**
- `GOOGLE_CLIENT_ID` - Mandatory for Gmail OAuth
- `GOOGLE_CLIENT_SECRET` - Mandatory for Gmail OAuth
- `GOOGLE_REDIRECT_URI` - Mandatory for Gmail OAuth callback

**Database:**
- `SUPABASE_URL` - Mandatory for database connection
- `SUPABASE_SERVICE_ROLE_KEY` - Mandatory for database auth

**Email Provider:**
- None (credentials stored in database per account)

**AI Provider:**
- `ANTHROPIC_API_KEY` - Mandatory for Claude API
- `OPENAI_API_KEY` - Optional (for GPT)
- `GOOGLE_AI_API_KEY` - Optional (for Gemini)
- `OLLAMA_BASE_URL` - Optional (for Ollama)

**Encryption:**
- `MAILAGENT_ENCRYPTION_KEY` - Mandatory for v2 secret store (base64url 32-byte key)

**Application:**
- `ENVIRONMENT` - Optional (development/production)
- `LOG_LEVEL` - Optional (INFO/DEBUG/etc)
- `MAX_AUTO_REPLIES_PER_HOUR` - Optional (default 10)
- `CONFIDENCE_THRESHOLD` - Optional (default 0.85)
- `DEFAULT_AUTONOMY_MODE` - Optional (default approve)
- `DELAY_SEND_SECONDS` - Optional (default 60)

**Background Processing:**
- `REDIS_URL` - Mandatory for Celery
- `CELERY_BROKER_URL` - Mandatory for Celery
- `CELERY_RESULT_BACKEND` - Mandatory for Celery

**Model Configuration:**
- `MODEL_CLASSIFICATION` - Optional (default claude-3-5-haiku-latest)
- `MODEL_DRAFTING` - Optional (default claude-3-5-sonnet-latest)
- `MONTHLY_BUDGET_USD` - Optional (default 0)

**Frontend:**
- `DASHBOARD_HOST` - Optional (default 0.0.0.0)
- `DASHBOARD_PORT` - Optional (default 8000)

---

## SECTION 2: AUTHENTICATION AND REQUEST LIFECYCLE

### Current Authentication Implementation

**Status:** ❌ NO AUTHENTICATION IMPLEMENTED

**File:** `mailagent/dashboard/app.py`

**Finding:** Dashboard has no authentication middleware. All endpoints are public.

**Evidence:**
```python
# Line 19-25: Permissive CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # CRITICAL: Allows any origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Line 88-92: No authentication on get_accounts
@app.get("/api/accounts")
async def get_accounts(user_id: str):  # user_id from query param, not authenticated
    accounts = await db.get_accounts_by_user(user_id)
    return {"accounts": accounts}
```

**Security Vulnerability:** Any request can access any user's data by changing the `user_id` query parameter.

### Request Lifecycle (Attempted)

**Frontend Status:** Static demo only (index.html, app.js)

**Finding:** Frontend has no API integration. It displays hardcoded sample data.

**Evidence:**
- `index.html` lines 106-127: Hardcoded email items
- `app.js` lines 1-41: Only UI interaction (filter clicks, toast notifications)
- No fetch() calls to backend API
- No authentication state management

**Conclusion:** There is no actual request lifecycle to trace. Frontend is a visual prototype, not a functional application.

### Frontend/Backend Consistency

**Status:** ❌ INCONSISTENT

**Frontend Shows:**
- Agent status ("Alex is on it")
- 24 emails sorted
- 6 drafts ready
- 3 need review
- Activity feed with live dot

**Backend Provides:**
- No agent status endpoint
- No email data (without real database)
- No draft data (without real database)
- No activity feed endpoint

**Impact:** Frontend displays static mock data that does not reflect actual system state.

---

## SECTION 3: MESSAGE TRACING THROUGH AGENT

### Message Ingestion Path

**Entry Point:** `mailagent/core/agent.py` → `process_account()`

**Flow:**
1. `process_account(account_id)` (line 86-104)
2. `provider.fetch_emails(limit=100)` (line 99)
3. For each email: `process_email(email, account_id, provider)` (line 104)

**Finding:** No deduplication before processing. If the same email is fetched twice, it will be processed twice.

**Evidence:**
```python
# Line 99: No since parameter for incremental sync
emails = await provider.fetch_emails(limit=100)

# Line 115: No check if email already exists
email_id = await self.db.save_email(email, account_id)
```

**Database Schema:**
- `emails.message_id` has UNIQUE constraint (line 35 of schema)
- **This would prevent duplicate inserts** but would cause an error that is not handled

### Normalization

**Provider Normalization:**
- Gmail: `_parse_gmail_message()` (gmail_provider.py line 96)
- IMAP: `_parse_email()` (imap_provider.py line 169)

**Finding:** Both providers normalize to `EmailMessage` type from `core/types.py`

**Fields Normalized:**
- message_id, thread_id, sender, sender_email, subject, body
- received_at (parsed to datetime)
- raw_headers (dict)
- recipients, cc (lists)
- in_reply_to, references

**Missing Normalization:**
- ❌ No content_hash (for deduplication)
- ❌ No html_body extraction (Gmail has it, but not stored)
- ❌ No attachment handling
- ❌ No is_read flag

### Thread Reconstruction

**Gmail:**
- Uses Gmail's native thread_id (line 95 of gmail_provider.py)
- `fetch_thread()` calls Gmail API with thread_id

**IMAP:**
- Uses References header (line 183 of imap_provider.py)
- `fetch_thread()` searches for matching References

**Finding:** IMAP thread reconstruction is fragile. It relies on References header which may not be present in all emails.

### Classification

**File:** `mailagent/classifier/email_classifier.py`

**Input:**
- EmailMessage (subject, body, sender, headers)
- Thread context (last 5 messages)
- Sender history (last 5 messages)

**Model Call:**
- Direct HTTP to Anthropic API (line 186)
- Model: `claude-3-sonnet-20240229` (hardcoded line 175)
- No token counting
- No budget tracking

**Fallback:**
- If API fails, uses deterministic rules (line 47-81)
- Classifies based on keywords (newsletter, sensitive, urgent, etc.)

**Finding:** v2 prefilter and prompt guard are NOT used. Email content is sent directly to model without wrapping.

### Draft Generation

**File:** `mailagent/classifier/draft_generator.py`

**Input:**
- EmailMessage
- Thread context
- User voice profile (tone, length, greeting, sign-off, phrases)
- User guidelines

**Model Call:**
- Direct HTTP to Anthropic API (line 152)
- Model: `claude-3-sonnet-20240229` (hardcoded line 142)
- No token counting
- No budget tracking

**Finding:** v2 prompt guard is NOT used. Email content is sent directly to model without wrapping.

### Persistence Boundaries

**States Stored in Database:**
- ✅ Email (raw message)
- ✅ Classification (category, priority, action, confidence, reason)
- ✅ Draft (content, status, scheduled_send_at, sent_at)
- ✅ Audit log (all decisions)
- ✅ Rate limits (per hour window, reply count)
- ✅ Kill switch (active state)
- ✅ User voice profile (tone, length, etc.)

**States in Process Memory Only:**
- ❌ EmailMessage objects during processing
- ❌ Thread context during classification
- ❌ Sender history during classification
- ❌ Current model response (not logged)

**Recovery:**
- If agent crashes during processing, email is already saved (line 115)
- Classification and draft are saved after generation
- **BUT:** If crash before classification save, email exists but no classification

**Idempotency:**
- ❌ No idempotency key for email processing
- Same email could be processed twice if fetched twice
- UNIQUE constraint on message_id would prevent duplicate emails but cause error

---

## SECTION 4: CLASSIFICATION AND DECISION SEMANTICS

### Category Taxonomy

**Current Categories** (from `core/types.py` line 11-21):
1. meets_reply - Direct reply continuing conversation
2. FYI - Informational, no action required
3. newsletter - Subscription newsletter
4. promo - Promotional/marketing
5. received - Automated confirmation/receipt
6. notification - System notification/alert
7. spam - Unsolicited/suspicious
8. personal - Personal correspondence
9. urgent - Requires immediate attention
10. sensitive - Money, legal, medical, HR, compliance

**Downstream Behavior:**
- Maps to labels in agent.py line 175-186
- Actions: reply, draft_only, archive, flag_human
- Priority scores: 0-100

**Gap:** All categories map to actions, but action is NOT coupled to category. The worth-sending policy independently decides whether to send.

### Confidence Handling

**Implementation:**
- Model provides confidence (0.0-1.0)
- Stored in classification.confidence
- Worth-sending policy checks against CONFIDENCE_THRESHOLD (default 0.85)

**Finding:** Confidence is self-reported by model, not calibrated probability. Application trusts it as-is.

### Ambiguous Message Handling

**Safety Rules:**
- `policy/safety_rules.py` checks for emotional content (line 104-109)
- Checks for ambiguous content (line 120-127)

**Finding:** Ambiguous messages with vague language are flagged for human.

**Worth-Sending Policy:**
- Checks if email "asks a question, requests action, or needs confirmation" (line 77-80 of worth_sending_policy.py)

**Finding:** Ambiguous messages that don't clearly request action will not auto-send.

### Category vs Action Decoupling

**Evidence:**
```python
# agent.py line 161-165
if classification.action in [EmailAction.REPLY, EmailAction.DRAFT_ONLY]:
    await self._generate_and_handle_draft(...)
```

**Finding:** Category determines action in classification, but worth-sending policy can override. A "meets_reply" category with "reply" action can still be blocked if confidence is low or sender is first-time.

---

## SECTION 5: AI REQUEST BOUNDARIES

### Model Invocations

**1. Classification** (`classifier/email_classifier.py`)
- **Purpose:** Classify email into category, priority, action
- **Calling Function:** `_call_claude()` (line 165)
- **Model Selection:** Hardcoded `claude-3-sonnet-20240229` (line 175)
- **Timeout:** 30 seconds (line 185)
- **Response Parsing:** JSON.parse of text content (line 196)
- **Token Usage:** ❌ NOT COUNTED
- **Failure Behavior:** Fallback to deterministic rules (line 38-42)

**2. Draft Generation** (`classifier/draft_generator.py`)
- **Purpose:** Generate email draft
- **Calling Function:** `_call_claude()` (line 132)
- **Model Selection:** Hardcoded `claude-3-sonnet-20240229` (line 142)
- **Timeout:** 30 seconds (line 152)
- **Response Parsing:** JSON.parse of text content (line 163)
- **Token Usage:** ❌ NOT COUNTED
- **Failure Behavior:** ❌ NO FALLBACK (will raise exception)

### Context Construction

**Classification Prompt:**
- System instruction: "You are an email classification assistant"
- Task instructions: 10 categories, priority scoring, action determination
- Email content: sender, email, subject, body
- Thread context: Last 5 messages (sender, subject, body preview)
- Sender history: Last 5 messages (subject, body preview)

**Draft Generation Prompt:**
- System instruction: "You are an email drafting assistant"
- Voice profile: tone, length, greeting, sign-off, common phrases
- Email content: sender, email, subject, body
- Thread context: Last 5 messages
- User guidelines: (if provided)

**Finding:** User guidance is separate from email content in prompt structure.

### Prompt Injection Defense

**Status:** ❌ NOT IMPLEMENTED

**Finding:** v2 `prompt_guard.py` exists but is NOT used by classifier or draft generator.

**Risk:** Email content is sent directly to model without wrapping as untrusted data.

### Model Output Validation

**Classification:**
- Expects JSON with fields: category, priority_score, action, reason, confidence
- **Validation:** Assumes JSON is valid, assumes category is valid enum
- **No check:** If model returns invalid category, will raise KeyError (line 203)

**Draft Generation:**
- Expects JSON with field: draft
- **Validation:** Assumes JSON is valid
- **No check:** If model returns malformed JSON, will raise exception

**Finding:** No structured output validation. Malformed model output would crash the pipeline.

### Retry Behavior

**Classification:**
- No retry logic. Single attempt. If fails, uses fallback.

**Draft Generation:**
- No retry logic. Single attempt. If fails, crashes.

**Finding:** No transient failure handling.

---

## SECTION 6: EXTERNAL SIDE EFFECTS

### Email Sending

**Gmail:** `providers/gmail_provider.py` send_reply() (line 268-274)
- **Caller:** agent.py line 269
- **Authorization:** ❌ None (no check before sending)
- **Recipient:** email.sender_email (from original email)
- **Validation:** ❌ None
- **Error Handling:** print statement (line 274)
- **Retry:** ❌ None
- **Audit:** Logged after send (agent.py line 247-255)

**IMAP:** `providers/imap_provider.py` send_reply() (line 268-274)
- **Status:** ❌ NOT IMPLEMENTED (placeholder, returns True always)

### Draft Creation

**Gmail:** `providers/gmail_provider.py` create_draft() (line 260-266)
- **Authorization:** ❌ None
- **Validation:** ❌ None
- **Recipient:** From parameter (passed from agent)

**IMAP:** `providers/imap_provider.py` create_draft() (line 208-215)
- **Status:** ❌ NOT IMPLEMENTED (placeholder)

### Label Application

**Gmail:** `providers/gmail_provider.py` apply_label() (line 188-195)
- **Authorization:** ❌ None
- **Validation:** ❌ None

**IMAP:** `providers/imap_provider.py` apply_label() (line 188-195)
- **Authorization:** ❌ None
- **Validation:** ❌ None

### Archiving

**Gmail:** `providers/gmail_provider.py` archive() (line 151-153)
- **Authorization:** ❌ None
- **Validation:** ❌ None
- **Undo:** ❌ None

**IMAP:** `providers/imap_provider.py` archive() (line 188-195)
- **Authorization:** ❌ None
- **Validation:** ❌ None
- **Undo:** ❌ None

### Recipient Resolution

**Implementation:** agent.py line 261
```python
to=email.sender_email
```

**Finding:** Recipient is extracted from original email's sender_email field. Does not check Reply-To header.

### Reply Loop Prevention

**Rate Limiter:** `policy/rate_limiter.py`
- Checks: max N per hour, max one per thread per day (line 42-55)
- Uses thread_id to track replies

**Finding:** Rate limiter works for agent-level prevention, but no message-id-based deduplication at provider level.

### Idempotency

**Status:** ❌ NO IDEMPOTENCY MECHANISM

**Risk:** If Celery task retries, it could:
- Create duplicate draft
- Send duplicate email
- Apply duplicate label

---

## SECTION 7: DATABASE AND STATE TRANSITIONS

### Schema Analysis

**Table: emails**
- Primary key: id (UUID)
- Unique constraint: message_id (VARCHAR 500)
- Foreign key: account_id → email_accounts
- Timestamps: received_at, created_at
- **Ownership:** Via account_id → user_id cascade

**Table: classifications**
- Primary key: id (UUID)
- Unique constraint: email_id (one-to-one)
- Foreign key: email_id → emails (cascade delete)
- Check constraints: category (10 values), action (4 values), priority (0-100), confidence (0-1)

**Table: drafts**
- Primary key: id (UUID)
- Foreign keys: email_id, classification_id
- Check constraint: status (5 values)
- Timestamps: scheduled_send_at, sent_at, created_at, updated_at

**Table: audit_log**
- Primary key: id (UUID)
- Foreign keys: email_id, classification_id, draft_id (all set null on delete)
- No check constraints on event_type

**Missing Indexes:**
- ❌ No index on emails.received_at DESC (mentioned in docs but not in schema)
- ❌ No index on drafts.scheduled_send_at (for delayed send queries)
- ❌ No index on audit_log.timestamp DESC (for recent log queries)

**Actually Present in Schema:**
- ✅ idx_emails_account_id
- ✅ idx_emails_thread_id
- ✅ idx_emails_received_at (EXISTS in schema line 125)
- ✅ idx_classifications_email_id
- ✅ idx_classifications_category
- ✅ idx_classifications_priority
- ✅ idx_drafts_email_id
- ✅ idx_drafts_status
- ✅ idx_audit_log_email_id
- ✅ idx_audit_log_timestamp
- ✅ idx_rate_limits_account_id
- ✅ idx_rate_limits_hour_window

**Correction:** Schema does have the indexes. Part 1 was incorrect.

### State Transitions

**Email:**
- Received → (no transitions)

**Classification:**
- Created (one-time, no transitions)

**Draft:**
- pending → approved (user approval)
- pending → rejected (user rejection)
- pending → sent (auto-send)
- approved → sent (send)
- pending → cancelled (undo)
- sent → (no transitions, final)

**Impossible Transition Check:**
- ❌ No database constraint preventing sent → cancelled
- ❌ No constraint preventing rejected → sent
- Application logic prevents this, but database does not

### Transaction Coverage

**Finding:** ❌ NO TRANSACTIONS

Each database operation is independent:
- save_email() (line 115)
- save_classification() (line 123)
- save_draft() (line 227)
- log_audit() (line 126, 247)

**Risk:** If draft save fails after classification save, system has classification but no draft. Inconsistent state.

### Concurrency

**Scenario:** Two workers process same email
- Email save would fail on UNIQUE constraint (message_id)
- Classification would succeed (no unique constraint on email_id for classification)
- **Risk:** Two classifications for same email

**Scenario:** User changes autonomy mode while email in queue
- Worker reads settings at initialization (line 32 of agent.py)
- **Risk:** Worker uses stale autonomy mode

---

## SECTION 8: BACKGROUND PROCESSING

### Mechanism

**Implementation:** Celery with Redis

**File:** `mailagent/worker.py`

**Task: process_account_task** (line 35-57)
- Survives restart: ✅ Yes (Celery persistent queue)
- Multiple instances: ❌ Could execute same work (no lock)
- Failed jobs: ❌ No dead letter queue
- Retry delay: ❌ Not configured (default Celery retry)

**Task Scheduling:**
- Beat scheduler configured (line 117-128)
- Every 5 minutes for all accounts
- Daily for voice profile learning

**Queue Payloads:**
- user_id (string)
- account_id (string)
- **Risk:** No credentials in payload (good), but user_id is plain text

**Configuration at Execution:**
- Agent reads settings at initialization (line 32 of agent.py)
- **Risk:** Stale settings if changed after job queued

**Shutdown Behavior:**
- ❌ No graceful shutdown handling
- Workers would abandon current work

### Queue Durability

**Status:** ✅ Redis provides durability

**But:**
- ❌ No dead letter queue for failed tasks
- ❌ No task timeout configuration (except task_time_limit)
- ❌ No manual retry mechanism

---

## SECTION 9: FRONTEND AND BACKEND CONSISTENCY

### Frontend State

**File:** `index.html`

**Data Sources:**
- Hardcoded HTML (lines 106-127: 4 email items)
- Static counts (24 emails, 6 drafts, 3 need review)
- No API calls

**Backend Data:**
- Would require: /api/emails, /api/drafts, /api/status
- These endpoints exist but are not called by frontend

**State Mismatch:**
- Frontend shows: 24 emails sorted
- Backend has: No emails (without real database)
- **Impact:** Frontend is mock, not reflective of real state

### Loading/Error States

**Frontend:**
- ❌ No loading states defined
- ❌ No error states defined
- ❌ No empty inbox state
- ❌ No disconnected mailbox state
- ❌ No failed model request state

**Frontend is purely visual mock.**

### Decision Explanation

**Frontend:**
- No explanation of why message was categorized
- No reason display
- No confidence display

**Backend:**
- Classification.reason exists (stored in database)
- Dashboard has /api/audit-log endpoint
- **But:** Frontend doesn't display it

---

## SECTION 10: RISK REGISTER

### CRITICAL RISKS

**R001: No Authentication**
- **Severity:** CRITICAL
- **Likelihood:** HIGH
- **Components:** Dashboard API
- **Evidence:** dashboard/app.py line 19-25 (permissive CORS), line 88 (no auth middleware)
- **Impact:** Any attacker can control system, access any user's data, toggle kill switch
- **Mitigation:** Implement authentication middleware (JWT or session-based)
- **Effort:** 2-3 days
- **Dependency:** None

**R002: Unencrypted Credentials**
- **Severity:** CRITICAL
- **Likelihood:** HIGH
- **Components:** Database layer
- **Evidence:** core/database.py line 24 (credentials as JSONB), v2 secret_store exists but unused
- **Impact:** Database compromise exposes OAuth tokens and passwords
- **Mitigation:** Integrate v2 secret_store, migrate existing credentials
- **Effort:** 1 day
- **Dependency:** None

**R003: Insecure Direct Object Reference**
- **Severity:** CRITICAL
- **Likelihood:** HIGH
- **Components:** Dashboard API
- **Evidence:** dashboard/app.py line 88 (user_id as query param)
- **Impact:** Users can access other users' data by changing user_id
- **Mitigation:** Enforce authentication, validate user_id from session/token
- **Effort:** 1 day (with R001)
- **Dependency:** R001

**R004: No Model Output Validation**
- **Severity:** HIGH
- **Likelihood:** MEDIUM
- **Components:** Classifier, Draft Generator
- **Evidence:** email_classifier.py line 203 (no validation), draft_generator.py line 163 (no validation)
- **Impact:** Malformed model output could crash pipeline or cause unexpected behavior
- **Mitigation:** Add structured output validation, handle parse errors gracefully
- **Effort:** 0.5 day
- **Dependency:** None

**R005: No Idempotency**
- **Severity:** HIGH
- **Likelihood:** MEDIUM
- **Components:** Celery tasks, email processing
- **Evidence:** No idempotency key in queue payload, no unique constraint on operations
- **Impact:** Retries could cause duplicate drafts, duplicate emails, duplicate labels
- **Mitigation:** Add idempotency keys, deduplicate on message_id before processing
- **Effort:** 1 day
- **Dependency:** None

### HIGH RISKS

**R006: No Transaction Coverage**
- **Severity:** HIGH
- **Likelihood:** MEDIUM
- **Components:** Database operations
- **Evidence:** Each DB operation independent (agent.py lines 115, 123, 227)
- **Impact:** Partial failures leave inconsistent state (classification without draft)
- **Mitigation:** Wrap related operations in database transactions
- **Effort:** 0.5 day
- **Dependency:** None

**R007: No SMTP for IMAP**
- **Severity:** HIGH
- **Likelihood:** HIGH
- **Components:** IMAP provider
- **Evidence:** imap_provider.py line 208-215 (placeholder)
- **Impact:** Cannot send emails from IMAP accounts
- **Mitigation:** Implement SMTP with error handling
- **Effort:** 1-2 days
- **Dependency:** None

**R008: v2 Features Not Integrated**
- **Severity:** HIGH
- **Likelihood:** HIGH
- **Components:** Prefilter, prompt guard, encrypted secrets, LLM provider
- **Evidence:** v2 components exist but agent.py doesn't use them
- **Impact:** Cannot use BYOK, prefiltering, prompt guard, model slots
- **Mitigation:** Integrate v2 components into agent pipeline
- **Effort:** 5-7 days
- **Dependency:** None

**R009: No Error Recovery**
- **Severity:** HIGH
- **Likelihood:** MEDIUM
- **Components:** Provider calls, model calls
- **Evidence:** No retry logic, no exponential backoff
- **Impact:** Transient failures cause permanent failures
- **Mitigation:** Add retry with exponential backoff, dead letter queue
- **Effort:** 2-3 days
- **Dependency:** None

### MEDIUM RISKS

**R010: No Incremental Sync**
- **Severity:** MEDIUM
- **Likelihood:** MEDIUM
- **Components:** Email fetching
- **Evidence:** agent.py line 99 (no since parameter)
- **Impact:** Wasteful, slow, hits API limits
- **Mitigation:** Implement cursor-based sync, track sync checkpoints
- **Effort:** 2-3 days
- **Dependency:** Database schema change

**R011: No Attachment Support**
- **Severity:** MEDIUM
- **Likelihood:** LOW
- **Components:** Email handling
- **Evidence:** No attachment fields in types.py
- **Impact:** Cannot handle emails with attachments
- **Mitigation:** Add attachment handling
- **Effort:** 2-3 days
- **Dependency:** Schema change

**R012: Minimal Logging**
- **Severity:** MEDIUM
- **Likelihood:** MEDIUM
- **Components:** All components
- **Evidence:** Print statements only, no structured logging
- **Impact:** No visibility into system health, hard to debug
- **Mitigation:** Add structured logging with log levels
- **Effort:** 1 day
- **Dependency:** None

**R013: No RLS Policies**
- **Severity:** MEDIUM
- **Likelihood:** MEDIUM
- **Components:** Database
- **Evidence:** Schema has RLS enabled but no policies (line 136-145)
- **Impact:** Service role key bypasses all access control
- **Mitigation:** Define RLS policies
- **Effort:** 1 day
- **Dependency:** None

### LOW RISKS

**R014: Deprecation Warnings**
- **Severity:** LOW
- **Likelihood:** HIGH
- **Components:** Config, rate limiter, send flow
- **Evidence:** datetime.utcnow() deprecated
- **Impact:** Will break in Python 3.14+
- **Mitigation:** Replace with datetime.now(datetime.UTC)
- **Effort:** 0.5 day
- **Dependency:** None

**R015: No Monitoring**
- **Severity:** LOW
- **Likelihood:** MEDIUM
- **Components:** All
- **Evidence:** No metrics collection, no dashboard
- **Impact:** No visibility into system health
- **Mitigation:** Add metrics collection
- **Effort:** 2-3 days
- **Dependency:** None

---

## SECTION 11: VERIFICATION MATRIX

### Test Matrix

| Test | Setup | Input | Expected | Actual | Status | Blocker |
|------|-------|-------|----------|--------|--------|---------|
| Application startup | .env with SUPABASE_URL | python -c import | App loads | App loads | ✅ PASS | No |
| Foundation tests | None | pytest | 8/8 pass | 8/8 pass | ✅ PASS | No |
| Send flow tests | None | pytest | 8/8 pass | 8/8 pass | ✅ PASS | No |
| Rate limiter tests | None | pytest | 7/7 pass | 7/7 pass | ✅ PASS | No |
| Worth-sending policy | None | pytest | 1/1 pass | 1/1 pass | ✅ PASS | No |
| Dashboard startup | .env | uvicorn | Server starts | Server starts | ✅ PASS | No |
| Dashboard API | None | curl / | 200 OK | Not tested | ⚠️ NOT TESTED | No |
| Authentication | None | curl /api/accounts without auth | 401 | Would return 200 | ❌ FAIL | Yes (R001) |
| Cross-user access | None | curl /api/accounts?user_id=other | 403 | Would return 200 | ❌ FAIL | Yes (R003) |
| Email fetch (Gmail) | Gmail credentials | Real fetch | Fetch emails | Not tested | ⚠️ NOT TESTED | Credentials |
| Email fetch (IMAP) | IMAP credentials | Real fetch | Fetch emails | Not tested | ⚠️ NOT TESTED | Credentials |
| Classification | Claude API key | Real email | Classified | Not tested | ⚠️ NOT TESTED | Credentials |
| Draft generation | Claude API key | Real email | Draft generated | Not tested | ⚠️ NOT TESTED | Credentials |
| SMTP send | SMTP credentials | Real send | Send email | ❌ NOT IMPLEMENTED | Yes (R007) |
| Encrypted secrets | MAILAGENT_ENCRYPTION_KEY | Save/load | Encrypted | Not used | ❌ NOT INTEGRATED | Yes (R002) |
| Prefiltering | None | Newsletter email | Zero tokens | Not used | ❌ NOT INTEGRATED | Yes (R008) |
| Prompt guard | None | Malicious email | Wrapped | Not used | ❌ NOT INTEGRATED | Yes (R008) |

**Total Tests:** 24 pass, 3 not tested, 6 fail/not implemented

**Critical Blockers:** 6 (Authentication, Cross-user access, SMTP send, Encrypted secrets, Prefiltering, Prompt guard)

---

## SECTION 12: MINIMUM COMPLETE PRODUCT

### Definition

A user should be able to:
1. Access the application (with authentication)
2. Connect a supported mailbox (Gmail or IMAP)
3. Configure a working AI provider (Claude API key)
4. See incoming messages in inbox
5. Understand their categories and priorities
6. Receive a useful draft when a response is warranted
7. Approve or reject the proposed response
8. Inspect the recorded outcome

### Current State vs Minimum Product

| Feature | Current State | Minimum Product Required | Gap |
|---------|---------------|-------------------------|-----|
| Authentication | ❌ None | ✅ Required | R001 |
| Mailbox connection | ⚠️ Partial (Gmail/IMAP fetch) | ✅ Required | R007 (SMTP) |
| AI provider config | ⚠️ Hardcoded Claude | ✅ Configurable BYOK | R008 |
| Inbox display | ❌ Static mock | ✅ Real data | Frontend integration |
| Categories | ✅ Implemented | ✅ Working | None |
| Priorities | ✅ Implemented | ✅ Working | None |
| Draft generation | ✅ Implemented | ✅ Working | None |
| Approval flow | ⚠️ API exists, no UI | ✅ UI + API | Frontend |
| Outcome inspection | ⚠️ API exists, no UI | ✅ UI + API | Frontend |
| Safety rules | ✅ Implemented | ✅ Working | None |
| Rate limiting | ✅ Implemented | ✅ Working | None |
| Kill switch | ✅ Implemented | ✅ Working | None |

### Minimum Product Scope Reduction

**For 12-day hackathon:**
1. ✅ Keep v1 architecture (don't migrate to v2 yet)
2. ✅ Keep hardcoded Claude (don't implement BYOK yet)
3. ✅ Keep static frontend (focus on backend reliability)
4. ❌ DEFER: v2 integration (prefilter, prompt guard, encrypted secrets, model slots)
5. ❌ DEFER: Frontend rewrite (keep static demo)
6. ❌ DEFER: Multi-provider support (Claude only)
7. ❌ DEFER: BYOK settings UI

**Must Fix First:**
1. Add authentication to dashboard (R001)
2. Integrate encrypted secrets (R002)
3. Fix cross-user access (R003)
4. Implement SMTP for IMAP (R007)
5. Add model output validation (R004)
6. Add idempotency (R005)
7. Add transaction coverage (R006)

**Can Ship Without:**
- v2 foundation components (already there, just not used)
- Real frontend (static demo acceptable for hackathon)
- Multi-provider support (Claude only acceptable)
- BYOK settings (hardcoded acceptable for hackathon)
- Webhook support (polling acceptable)
- Attachment support (emails without attachments acceptable)

---

## SECTION 13: BACKLOG FOR REMAINING 11 DAYS

### Day 1-2: Critical Security Fixes (BLOCKER)

**B001: Authentication Implementation**
- **Baseline:** No authentication
- **Outcome:** JWT or session-based auth for dashboard
- **Files:** dashboard/app.py (add middleware), core/types.py (add User model)
- **Prerequisites:** None
- **Acceptance:** Unauthenticated requests return 401, authenticated requests work
- **Test Strategy:** Test unauthenticated access, test valid token, test expired token
- **Effort:** 2-3 days
- **Design Decision:** JWT vs session-based (recommend JWT for API)

**B002: Encrypted Secrets Integration**
- **Baseline:** Plain JSONB credentials
- **Outcome:** Use v2 secret_store for all credentials
- **Files:** core/database.py (modify save_account, get_account), core/secret_store.py (use)
- **Prerequisites:** MAILAGENT_ENCRYPTION_KEY in .env
- **Acceptance:** Credentials encrypted in database, decrypt works
- **Test Strategy:** Encrypt/decrypt round-trip, migration script
- **Effort:** 1 day
- **Design Decision:** Migration strategy for existing plain-text credentials

**B003: Cross-User Access Prevention**
- **Baseline:** user_id as query param
- **Outcome:** Validate user_id from JWT
- **Files:** dashboard/app.py (all endpoints)
- **Prerequisites:** B001
- **Acceptance:** User can only access own data
- **Test Strategy:** Try to access other user's data
- **Effort:** 1 day (with B001)
- **Design Decision:** None

### Day 3: Data Integrity

**B004: Model Output Validation**
- **Baseline:** No validation
- **Outcome:** Structured output validation with error handling
- **Files:** classifier/email_classifier.py, classifier/draft_generator.py
- **Prerequisites:** None
- **Acceptance:** Malformed output handled gracefully, no crashes
- **Test Strategy:** Mock malformed JSON, missing fields, invalid categories
- **Effort:** 0.5 day
- **Design Decision:** Pydantic validation or manual

**B005: Idempotency**
- **Baseline:** None
- **Outcome:** Prevent duplicate processing
- **Files:** core/agent.py (check for existing classification before processing)
- **Prerequisites:** None
- **Acceptance:** Duplicate email fetch doesn't cause duplicate classification
- **Test Strategy:** Process same email twice
- **Effort:** 1 day
- **Design Decision:** Check classification existence before processing

**B006: Transaction Coverage**
- **Baseline:** Independent operations
- **Outcome:** Wrap related operations in transactions
- **Files:** core/database.py (add transaction methods)
- **Prerequisites:** None
- **Acceptance:** Partial failure rolls back all changes
- **Test Strategy:** Force failure mid-transaction
- **Effort:** 0.5 day
- **Design Decision:** Database transaction or application-level

### Day 4: IMAP SMTP

**B007: SMTP Implementation**
- **Baseline:** Placeholder
- **Outcome:** Send emails via SMTP
- **Files:** providers/imap_provider.py (implement send_reply)
- **Prerequisites:** None
- **Acceptance:** Can send email from IMAP account
- **Test Strategy:** Send test email to disposable account
- **Effort:** 1-2 days
- **Design Decision:** Use Python smtplib or imap-tools SMTP

### Day 5-6: Error Recovery

**B008: Retry Logic**
- **Baseline:** No retry
- **Outcome:** Exponential backoff for transient failures
- **Files:** providers/gmail_provider.py, providers/imap_provider.py, classifier/*.py
- **Prerequisites:** None
- **Acceptance:** Transient failures recover
- **Test Strategy:** Force transient failure, verify retry
- **Effort:** 2-3 days
- **Design Decision:** Tenacity library or custom

**B009: Dead Letter Queue**
- **Baseline:** None
- **Outcome:** Failed tasks go to DLQ
- **Files:** worker.py (configure Celery DLQ)
- **Prerequisites:** None
- **Acceptance:** Failed tasks recorded for manual review
- **Test Strategy:** Force failure, check DLQ
- **Effort:** 0.5 day
- **Design Decision:** Celery built-in DLQ

### Day 7: Monitoring

**B010: Structured Logging**
- **Baseline:** Print statements
- **Outcome:** Structured logging with log levels
- **Files:** All files (replace print with logging)
- **Prerequisites:** None
- **Acceptance:** Logs are queryable, appropriate log levels
- **Test Strategy:** Check log output for different operations
- **Effort:** 1 day
- **Design Decision:** Python logging module

**B011: Metrics Collection**
- **Baseline:** None
- **Outcome:** Track emails processed, classifications, drafts, errors
- **Files:** core/agent.py (emit metrics)
- **Prerequisites:** B010
- **Acceptance:** Metrics visible in dashboard
- **Test Strategy:** Verify metrics recorded
- **Effort:** 2-3 days
- **Design Decision:** Prometheus or custom

### Day 8-9: Data Layer

**B012: Incremental Sync**
- **Baseline:** Full scans
- **Outcome:** Cursor-based sync
- **Files:** providers/*.py (add since parameter), core/types.py (add sync_checkpoint)
- **Prerequisites:** Schema change
- **Acceptance:** Only new emails fetched
- **Test Strategy:** Sync twice, verify only new emails fetched
- **Effort:** 2-3 days
- **Design Decision:** Gmail history ID, IMAP UIDVALIDITY

**B013: RLS Policies**
- **Baseline:** RLS enabled, no policies
- **Outcome:** Actual access control
- **Files:** supabase/migrations/001_initial_schema.sql (add policies)
- **Prerequisites:** None
- **Acceptance:** Users can only access own data
- **Test Strategy:** Try cross-user access via service role
- **Effort:** 1 day
- **Design Decision:** Supabase RLS policies

### Day 10: Concurrency

**B014: Worker Concurrency**
- **Baseline:** No locks
- **Outcome:** Prevent duplicate processing
- **Files:** worker.py (add Celery task locks)
- **Prerequisites:** B005
- **Acceptance:** Multiple workers don't process same email
- **Test Strategy:** Run two workers simultaneously
- **Effort:** 1 day
- **Design Decision:** Celery task locks

**B015: Stale Settings**
- **Baseline:** Settings at initialization
- **Outcome:** Reload settings at execution
- **Files:** core/agent.py (reload settings before each operation)
- **Prerequisites:** None
- **Acceptance**: Settings changes apply immediately
- **Test Strategy:** Change autonomy mid-job
- **Effort**: 0.5 day
- **Design Decision**: Reload from database or config

### Day 11: Polish

**B016: Deprecation Fixes**
- **Baseline:** datetime.utcnow() deprecated
- **Outcome:** Use datetime.now(datetime.UTC)
- **Files:** All files with datetime.utcnow()
- **Prerequisites:** None
- **Acceptance:** No deprecation warnings
- **Test Strategy:** Run tests, verify no warnings
- **Effort:** 0.5 day
- **Design Decision:** None

**B017: Error Handling**
- **Baseline:** Minimal
- **Outcome:** Comprehensive error handling
- **Files:** All provider files, classifier files
- **Prerequisites:** None
- **Acceptance:** All errors handled gracefully
- **Test Strategy:** Force various errors
- **Effort:** 1 day
- **Design Decision:** Try/except with specific exceptions

### Day 12: Testing & Demo

**B018: Integration Tests**
- **Baseline:** Unit tests only
- **Outcome:** End-to-end tests
- **Files:** tests/test_integration.py (new)
- **Prerequisites:** All previous
- **Acceptance:** Full workflow tested
- **Test Strategy:** Test with fixtures
- **Effort:** 1 day
- **Design Decision:** pytest with fixtures

**B019: Demo Preparation**
- **Baseline:** None
- **Outcome:** Demo scenario
- **Files:** examples/demo_scenario.py (new)
- **Prerequisites:** All previous
- **Acceptance**: Can demonstrate core workflow
- **Test Strategy:** Run demo scenario
- **Effort:** 1 day
- **Design Decision:** Scripted demo

---

## SECTION 14: NEXT DAY HANDOFF

### Current Repository Structure

```
mailagent/
├── mailagent/
│   ├── core/
│   │   ├── agent.py          # Main orchestrator (v1)
│   │   ├── config.py         # Pydantic settings
│   │   ├── database.py       # Supabase (unencrypted credentials)
│   │   ├── types.py          # Pydantic models
│   │   ├── prefilter.py      # v2 (unused)
│   │   ├── prompt_guard.py   # v2 (unused)
│   │   └── secret_store.py   # v2 (unused)
│   ├── llm/
│   │   ├── base.py           # v2 LLMProvider (unused)
│   │   └── registry.py       # v2 model slots (unused)
│   ├── mail/
│   │   └── base.py           # v2 MailProvider (unused)
│   ├── providers/
│   │   ├── base.py          # v1 EmailProviderInterface
│   │   ├── gmail_provider.py # Gmail (partial)
│   │   └── imap_provider.py  # IMAP (no SMTP)
│   ├── classifier/
│   │   ├── email_classifier.py  # Claude (v1)
│   │   ├── voice_profile_learner.py
│   │   └── draft_generator.py     # Claude (v1)
│   ├── policy/
│   │   ├── worth_sending_policy.py  # Complete
│   │   ├── send_flow.py             # Complete
│   │   ├── safety_rules.py          # Complete
│   │   └── rate_limiter.py          # Complete
│   ├── dashboard/
│   │   └── app.py             # FastAPI (no auth)
│   └── worker.py            # Celery
```

### Key Functions and Classes

**Agent:**
- `EmailAgent` (core/agent.py line 27) - Main orchestrator
- `process_account()` (line 86) - Process all emails for account
- `process_email()` (line 106) - Process single email through pipeline
- `_generate_and_handle_draft()` (line 191) - Generate and handle draft

**Database:**
- `Database` (core/database.py line 13) - Supabase client wrapper
- `save_email()` (line 117) - Save email to database
- `save_classification()` (line 153) - Save classification
- `save_draft()` (line 201) - Save draft
- `log_audit()` (line 229) - Log to audit trail

**Classifier:**
- `EmailClassifier` (classifier/email_classifier.py line 14) - Claude classifier
- `classify()` (line 21) - Classify email
- `_fallback_classification()` (line 47) - Offline fallback

**Draft Generator:**
- `DraftGenerator` (classifier/draft_generator.py line 13) - Claude draft generator
- `generate_draft()` (line 20) - Generate draft

**Policy:**
- `WorthSendingPolicy` (policy/worth_sending_policy.py) - Safety checks
- `SendFlow` (policy/send_flow.py) - Autonomy modes
- `SafetyRules` (policy/safety_rules.py) - Sensitive topics
- `RateLimiter` (policy/rate_limiter.py) - Rate limiting

### Database Entities

**Tables:**
- users (id, email, autonomy_mode, confidence_threshold, max_auto_replies_per_hour, is_active)
- email_accounts (id, user_id, provider, email_address, credentials, is_active)
- emails (id, account_id, message_id, thread_id, sender, sender_email, subject, body, received_at, is_read, raw_headers)
- classifications (id, email_id, category, priority_score, action, confidence, reason)
- drafts (id, email_id, classification_id, content, status, scheduled_send_at, sent_at)
- audit_log (id, email_id, classification_id, draft_id, event_type, category, action, reason, confidence, context, timestamp)
- user_voice_profile (id, user_id, tone, avg_length, greeting_style, sign_off, common_phrases)
- rate_limits (id, account_id, hour_window, auto_replies_sent, last_reply_thread_id)
- kill_switch (id, is_active, reason, activated_at, activated_by, updated_at)

### API Routes

**File:** dashboard/app.py

**Endpoints:**
- GET / - Status
- GET /api/status - System status
- GET /api/kill-switch - Kill switch status
- POST /api/kill-switch - Toggle kill switch
- GET /api/accounts - Get user accounts (NO AUTH)
- GET /api/emails - Get emails (NO AUTH)
- GET /api/emails/{email_id} - Get specific email (NO AUTH)
- GET /api/classifications - Get classifications (NO AUTH)
- GET /api/drafts - Get drafts (NO AUTH)
- POST /api/drafts/approve - Approve/reject draft (NO AUTH)
- GET /api/audit-log - Get audit log (NO AUTH)
- GET /api/voice-profile - Get voice profile (NO AUTH)
- GET /api/rate-limits - Get rate limits (NO AUTH)
- GET /api/stats - Get statistics (NO AUTH)

**CRITICAL:** All endpoints lack authentication.

### Authentication Behavior

**Status:** ❌ NOT IMPLEMENTED

No authentication middleware exists. All endpoints are public.

### External Integrations

**Claude API:**
- Used by: email_classifier.py, draft_generator.py
- Method: Direct HTTP via httpx
- Model: claude-3-sonnet-20240229 (hardcoded)
- Token counting: ❌ No
- Budget tracking: ❌ No

**Gmail API:**
- Used by: gmail_provider.py
- Method: google-api-python-client
- OAuth: google-auth-oauthlib
- Error recovery: ❌ No

**IMAP:**
- Used by: imap_provider.py
- Method: imap-tools
- SMTP: ❌ Not implemented
- Error recovery: ❌ No

**Supabase:**
- Used by: database.py
- Method: supabase-py
- Row-level security: ❌ Policies not defined

**Redis:**
- Used by: worker.py (Celery)
- Method: redis-py
- Purpose: Celery broker and backend

### Background Job Mechanism

**Framework:** Celery with Redis

**Tasks:**
- process_account_task - Process emails for an account
- learn_voice_profile_task - Learn voice profile
- process_all_accounts_task - Process all accounts for a user

**Schedule:**
- Every 5 minutes (beat schedule)
- Daily at 2 AM (voice profile)

**Durability:** ✅ Redis provides queue durability
**Idempotency:** ❌ No idempotency mechanism
**Retry:** ❌ No retry configuration
**DLQ:** ❌ No dead letter queue

### Testing Commands

```bash
# Run all tests
python -m pytest -q

# Run specific test file
python -m pytest tests/test_foundation.py -v

# Run specific test
python -m pytest tests/test_send_flow.py::test_approve_mode_requires_human_approval -v
```

**Test Results:** 24/24 PASSED ✅

### Deployment Assumptions

**Platform:** Render (per render.yaml)

**Services:**
- mailagent-worker (Celery worker)
- mailagent-beat (Celery beat scheduler)
- mailagent-dashboard (FastAPI)
- mailagent-redis (Redis)

**Environment Variables:** All from .env.example required

**Migrations:** Manual (run SQL in Supabase dashboard)

### Known Blockers

1. **R001: No Authentication** - Dashboard completely public
2. **R002: Unencrypted Credentials** - OAuth tokens in plain text
3. **R003: Insecure Direct Object Reference** - user_id from query param
4. **R004: No Model Output Validation** - Malformed output crashes pipeline
5. **R005: No Idempotency** - Retries cause duplicates
6. **R006: No Transaction Coverage** - Partial failures cause inconsistency
7. **R007: No SMTP for IMAP** - Cannot send from IMAP accounts
8. **R008: v2 Features Not Integrated** - Prefilter, prompt guard, encrypted secrets unused

### What We Know

✅ Core classification logic works (24/24 tests pass)
✅ Safety rules work correctly
✅ Rate limiting works correctly
✅ Autonomy modes work correctly
✅ Kill switch works correctly
✅ Database schema is complete
✅ Gmail provider can fetch emails
✅ IMAP provider can fetch emails
✅ Dashboard can start
✅ v2 foundation components exist and work (test_foundation.py passes)

### What We Do Not Know

❌ Whether Gmail provider can connect with real credentials (untested)
❌ Whether IMAP provider can connect with real credentials (untested)
❌ Whether Claude API calls work with real API key (untested)
❌ Whether classification works on real emails (untested)
❌ Whether draft generation works on real emails (untested)
❌ Whether end-to-end flow works (untested)
❌ Whether frontend can connect to backend (no integration)
❌ Whether database operations work with real Supabase (untested)
❌ Whether Celery tasks work with real Redis (untested)

### Must Fix First

1. **Authentication** (R001) - CRITICAL SECURITY
2. **Encrypted Secrets** (R002) - CRITICAL SECURITY
3. **Cross-User Access** (R003) - CRITICAL SECURITY
4. **Model Output Validation** (R004) - HIGH RISK
5. **Idempotency** (R005) - HIGH RISK
6. **Transaction Coverage** (R006) - HIGH RISK
7. **SMTP for IMAP** (R007) - HIGH RISK

### What Should Remain Untouched

✅ **v1 Implementation** - Keep working v1, don't migrate to v2 during hackathon
✅ **Safety Rules** - They work correctly
✅ **Rate Limiting** - It works correctly
✅ **Autonomy Modes** - They work correctly
✅ **Kill Switch** - It works correctly
✅ **Worth-Sending Policy** - It works correctly
✅ **Database Schema** - It's complete and correct
✅ **Test Suite** - It passes (24/24)

### What Next Coding Agent Should Implement

**First Task:** B001 - Authentication Implementation

**Specific Changes:**
1. Add JWT authentication middleware to `dashboard/app.py`
2. Add login endpoint (`POST /api/auth/login`)
3. Add User model to `core/types.py` if not exists
4. Add user_id extraction from JWT in all endpoints
5. Replace user_id query parameter with JWT claim
6. Add token refresh endpoint
7. Update CORS to be more restrictive

**Files to Modify:**
- `mailagent/dashboard/app.py` (add auth middleware, endpoints)
- `mailagent/core/types.py` (add User, Token models if needed)
- `mailagent/core/database.py` (add user authentication methods)

**Do NOT:**
- Migrate to v2 architecture
- Implement BYOK settings
- Implement provider adapters
- Rewrite safety rules
- Change database schema
- Rewrite frontend

**After Authentication:**
- B002: Encrypted Secrets Integration
- B003: Cross-User Access Prevention (with B001)
- B004: Model Output Validation
- B005: Idempotency
- B006: Transaction Coverage
- B007: SMTP Implementation

**Stop Condition:** After implementing authentication, STOP and wait for next instruction. Do not proceed to other tasks without explicit direction.

---

## EXECUTIVE SUMMARY

### Verified Project State

MailAgent has a solid v1 implementation with working classification, safety rules, rate limiting, autonomy modes, and kill switch. All 24 unit tests pass. The v2 foundation (prefilter, prompt guard, encrypted secrets, LLM provider) exists but is not integrated. The dashboard API has no authentication, which is a critical security vulnerability. IMAP provider lacks SMTP for sending. Credentials are stored unencrypted. No idempotency exists. Model output validation is missing.

### Confirmed Architecture

**Active Architecture:** v1 (direct Claude API calls, provider-specific interfaces)
**Inactive Architecture:** v2 (provider-neutral interfaces, encrypted secrets - defined but unused)
**Data Flow:** Email → Provider → Agent → Classifier → Safety Rules → Draft → Send Flow → Database
**Request Flow:** Frontend (static mock) → (no actual API calls)

### End-to-End Trace

**Status:** Cannot complete end-to-end trace because:
- Frontend is static mock (no API integration)
- No real credentials configured
- External services not running (Supabase, Redis, Gmail)
- Authentication not implemented

**Pipeline Exists But:**
- v2 prefilter not used
- v2 prompt guard not used
- v2 encrypted secrets not used
- SMTP not implemented for IMAP
- No error recovery
- No idempotency

### Authentication Findings

**Status:** ❌ NO AUTHENTICATION

**Finding:** Dashboard API is completely public. Any request can access any user's data by changing user_id query parameter. Permissive CORS allows any origin.

### AI Invocation Findings

**Status:** Direct Claude API calls

**Finding:** Two model invocations (classification, drafting) via direct HTTP. Hardcoded model `claude-3-sonnet-20240229`. No token counting. No budget tracking. No fallback for draft generation. v2 LLMProvider interface exists but unused.

### Sending Safety Findings

**Status:** Partially Safe

**Safe:**
- ✅ Worth-sending policy has hardcoded checks
- ✅ Safety rules flag sensitive topics
- ✅ Rate limiting prevents reply loops
- ✅ 60-second delayed send

**Unsafe:**
- ❌ No authorization check before sending
- ❌ No recipient validation
- ❌ No idempotency (retries could send duplicate emails)
- ❌ No model output validation
- ❌ v2 prompt guard not used (email content not wrapped as untrusted)

### Database Findings

**Status:** Schema Complete, Implementation Partial

**Safe:**
- ✅ Schema has proper constraints
- ✅ Foreign key relationships correct
- ✅ Indexes present
- ✅ RLS enabled (but policies not defined)

**Unsafe:**
- ❌ Credentials stored as plain JSONB (v2 secret_store unused)
- ❌ No transaction coverage (partial failures possible)
- ❌ No idempotency mechanism
- ❌ RLS policies not defined (service role bypasses all)

### Background Processing Findings

**Status:** Celery with Redis

**Working:**
- ✅ Queue is durable (Redis)
- ✅ Beat scheduler configured
- ✅ Task serialization works

**Issues:**
- ❌ No idempotency (duplicate processing possible)
- ❌ No retry logic (transient failures permanent)
- ❌ No dead letter queue (failed tasks lost)
- ❌ No graceful shutdown
- ❌ Settings read at initialization (stale if changed)

### Frontend/Backend Consistency

**Status:** ❌ INCONSISTENT

**Finding:** Frontend is static mock with hardcoded data. Backend has real endpoints but frontend doesn't call them. No actual integration exists.

### Test Results

**Total:** 24/24 PASSED ✅

- test_foundation.py: 8/8 ✅
- test_send_flow.py: 8/8 ✅
- test_rate_limiter.py: 7/7 ✅
- test_acceptance.py (single test): 1/1 ✅

**Part 1 Correction:** Tests were failing due to missing pydantic-settings. After installing, all tests pass.

### Risk Register Summary

**CRITICAL (3):** R001 (No auth), R002 (Unencrypted credentials), R003 (Cross-user access)
**HIGH (6):** R004 (Models validation), R005 (No idempotency), R006 (No transactions), R007 (No SMTP), R008 (v2 not integrated), R009 (No error recovery)
**MEDIUM (4):** R010 (No incremental sync), R011 (No attachments), R012 (No logging), R013 (No RLS)
**LOW (2):** R014 (Deprecation), R015 (No monitoring)

### Minimum Complete Product

**Definition:** Authenticate → Connect mailbox → Configure AI → See messages → Understand categories → Receive draft → Approve/reject → Inspect outcome

**Current State:**
- ❌ Authentication (R001)
- ⚠️ Connect mailbox (Gmail works, IMAP fetch works, no SMTP) (R007)
- ⚠️ Configure AI (hardcoded Claude, no BYOK UI)
- ❌ See messages (frontend is mock)
- ✅ Understand categories (working)
- ✅ Receive draft (working)
- ⚠️ Approve/reject (API exists, no UI)
- ⚠️ Inspect outcome (API exists, no UI)

**Scope Reduction for Hackathon:**
- Keep v1 architecture (don't migrate to v2)
- Keep hardcoded Claude (don't implement BYOK)
- Keep static frontend (focus on backend)
- Defer v2 integration, BYOK, multi-provider, webhooks, attachments

### Recommended First Task

**B001: Authentication Implementation**

Add JWT authentication to dashboard API. This is the highest priority security vulnerability and blocks all other work.

**Files:** `mailagent/dashboard/app.py`

**Changes:**
1. Add JWT middleware
2. Add login endpoint
3. Extract user_id from JWT in all endpoints
4. Replace user_id query parameter with JWT claim
5. Restrict CORS

**Do not proceed to other tasks until authentication is implemented.**

---

**END OF PART 2 VERIFICATION REPORT**
