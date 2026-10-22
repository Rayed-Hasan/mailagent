# MailAgent Day 1 Technical Findings

**Date:** 2026-10-17  
**Branch:** `main`  
**Baseline commit:** `f9cdd04` (`Build MailAgent v2 BYOG foundation and inbox UX`)

## Executive summary

The active product remains the v1 orchestration path in
[`mailagent/core/agent.py`](mailagent/core/agent.py). It uses the
provider-specific Gmail/IMAP adapters and direct Claude classifier/draft
implementations. The v2 prefilter, prompt guard, provider registry, and secret
store are present but were not previously connected to the active flow.

The original dashboard exposed every sensitive route without authentication,
accepted a caller-controlled `user_id`, and allowed wildcard CORS with
credentials. The active account write path also stored credentials directly in
the `credentials` JSONB column. These were confirmed from source, not inferred
from the earlier audit.

This phase added a bounded containment layer and changed new account writes to a
versioned AES-256-GCM envelope. It did **not** complete multi-user identity,
perform a production migration, or claim that existing plaintext credentials
are safe.

## 1. Verified baseline

- Worktree initially contained two pre-existing untracked reports:
  `AUDIT_REPORT.md` and `PART2_VERIFICATION_REPORT.md`. They were not modified.
- Branch: `main`.
- Latest commit: `f9cdd04`.
- `pydantic-settings` is already declared in `requirements.txt`; no dependency
  manifest correction was needed.
- The `pytest` executable was not on PATH, but `python -m pytest -q` ran the
  repository suite.
- Day 1 result: **28 passed, 0 failed, 0 skipped, 52 warnings**.
- Current Parts 4/5 result: **33 passed, 0 failed, 0 skipped, 52 warnings**.
- Warnings are existing Pydantic, pytest-asyncio, and `datetime.utcnow`
  deprecations; they did not fail the suite.
- `python -m compileall -q mailagent tests` passed.
- A synthetic AES-GCM round trip with associated data passed.
- No production database, mailbox, OAuth credential, or external provider was
  accessed or modified.

Regression-protected behavior is covered by
[`tests/test_acceptance.py`](tests/test_acceptance.py),
[`tests/test_foundation.py`](tests/test_foundation.py),
[`tests/test_rate_limiter.py`](tests/test_rate_limiter.py), and
[`tests/test_send_flow.py`](tests/test_send_flow.py). The suite covers policy
helpers and foundation primitives, but not a live authenticated API,
Supabase RLS, provider refresh, or end-to-end send behavior.

## 2. Authentication and authorization exposure

### Confirmed before this phase

- [`mailagent/dashboard/app.py`](mailagent/dashboard/app.py) had no auth
  dependency or middleware.
- `/api/accounts` accepted `user_id` directly from the query string.
- Account, email, draft, audit, rate-limit, voice-profile, statistics, and
  kill-switch routes were reachable without a verified principal.
- Account-derived identifiers were not checked against an owning user.
- CORS was `allow_origins=["*"]`, `allow_credentials=True`, and wildcard
  methods/headers.
- The static frontend in [`app.js`](app.js) made no API requests and therefore
  provided no security boundary.

### Confirmed cross-tenant paths

1. `GET /api/accounts?user_id=<other-user>` called
   `get_accounts_by_user(<other-user>)`.
2. `GET /api/emails?account_id=<other-account>` did not verify account owner.
3. `GET /api/emails/<other-email>` did not verify the email's account owner.
4. `GET /api/voice-profile?user_id=<other-user>` accepted the target directly.
5. Draft approval, audit-log, rate-limit, and statistics routes accepted
   account/email identifiers without ownership checks.

These were demonstrated by request/data-flow inspection. No external account
was accessed.

### Endpoint inventory and current containment

| Route | Sensitivity | Current requirement | Authorization |
|---|---|---|---|
| `GET /` | Health/service metadata | Public | None |
| `GET /api/status` | System state | Bearer token | Configured principal |
| `GET /api/kill-switch` | Control state | Bearer token | Configured principal |
| `POST /api/kill-switch` | External side-effect control | Bearer token | `activated_by` is server-derived |
| `GET /api/accounts` | Account metadata | Bearer token | Configured principal |
| `GET /api/emails` | Mail content | Bearer token | Account owner check |
| `GET /api/emails/{email_id}` | Mail content | Bearer token | Email-to-account owner check |
| `GET /api/classifications` | User data | Bearer token | Account owner check |
| `GET /api/drafts` | Draft content | Bearer token | Account owner check |
| `POST /api/drafts/approve` | External side-effect authorization | Bearer token | Draft-to-email-to-account owner check |
| `GET /api/audit-log` | User activity | Bearer token | Email owner check when filtered |
| `GET /api/voice-profile` | User profile | Bearer token | Server-derived principal |
| `GET /api/rate-limits` | Account activity | Bearer token | Account owner check |
| `GET /api/stats` | User/account metrics | Bearer token | Account owner check |

The immediate containment uses `DASHBOARD_API_TOKEN` and
`DASHBOARD_USER_ID`, compared with a constant-time comparison. Missing
configuration returns `503`; missing, malformed, or invalid bearer credentials
return `401`. There is no development fallback that trusts a query parameter,
header, or default user.

This is a **single configured principal**, not a complete multi-tenant
authentication system. Before supporting multiple users, replace it with
verified Supabase/OIDC JWT identity and retain resource ownership checks.

## 3. CORS and deployment containment

`DASHBOARD_ALLOWED_ORIGINS` is a comma-separated allowlist. Methods are limited
to `GET`, `POST`, and `OPTIONS`; headers are limited to `Authorization` and
`Content-Type`; credentialed cross-origin requests are disabled. An empty
allowlist permits no browser origin. Render now declares the three dashboard
settings as deployment variables in [`render.yaml`](render.yaml), but values
must be configured before deployment.

CORS is not treated as authentication. Non-browser clients still require the
bearer token.

## 4. OAuth credential storage and migration plan

### Confirmed current model

[`mailagent/supabase/migrations/001_initial_schema.sql`](mailagent/supabase/migrations/001_initial_schema.sql)
defines `email_accounts.credentials JSONB`. Before this phase,
[`mailagent/core/database.py`](mailagent/core/database.py) wrote the caller's
credential dictionary directly. Gmail OAuth values include access token,
refresh token, client secret, client ID, scopes, and expiry. IMAP credentials
include the mailbox password. The active agent read that JSONB directly and
passed it to providers.

### New-write contract

[`mailagent/core/secret_store.py`](mailagent/core/secret_store.py) now requires
a 32-byte key and uses AES-256-GCM with a random 12-byte nonce and optional
associated data. New account writes use:

```json
{"version": 1, "ciphertext": "<base64url AES-GCM payload>"}
```

Associated data binds the ciphertext to `user_id`, provider, and email address.
The active database layer encrypts before insert and decrypts only server-side.
Legacy/unversioned rows fail closed with an explicit migration error; they are
not silently treated as encrypted. Account API responses omit credentials.

### Controlled migration sequence

1. Configure and verify the encryption key from environment/KMS; never store it
   in the database or source.
2. Take the approved secure database backup.
3. Restore a disposable copy and run a synthetic migration test.
4. For each eligible account, encrypt the exact JSON credential object with
   owner/provider/email associated data and write version `1`.
5. Verify envelope shape, ciphertext non-equality to plaintext, decryptability,
   ownership binding, and provider initialization using synthetic values.
6. Keep failed rows unchanged and record only non-secret identifiers and
   failure classes.
7. Switch all reads to the versioned reader, then verify no plaintext rows
   remain.
8. Remove any temporary compatibility reader under a documented release
   condition.

No production migration was run. Rotation, backup restoration, and incident
response for credentials that may have appeared in historical exports/logs
remain deployment decisions. Real credentials were not rotated or revoked.

## 5. v1/v2 compatibility matrix

| Component | Evidence | Recommendation |
|---|---|---|
| v2 `SecretStore` | AES-GCM primitive and tests in `core/secret_store.py` | Reuse now for credential writes; migration separately |
| v2 `Prefilter` | Deterministic bulk/no-reply rules and foundation tests | Reuse with adapter after normalized message contract is agreed |
| v2 `PromptGuard` | Suspicious-instruction detection and wrapping tests | Add as defense-in-depth; never the sole policy boundary |
| v2 `LLMProvider`/registry | Provider-neutral slots and tests | Defer to Day 2 BYOK/provider-adapter work |
| v2 mail contract | Separate `mail/base.py` contract | Defer; avoid replacing working provider interfaces |
| v1 classifier/drafter | Active direct Claude path | Preserve as regression baseline |
| v1 policy/send flow | Active safety, worth-sending, rate-limit, and autonomy logic | Keep authoritative until a tested replacement exists |

## 6. Frontend integration plan and first workflow

The current [`index.html`](index.html) and [`app.js`](app.js) are a static
prototype with hardcoded messages and toast-only interactions. The next safe
increment is not a rewrite:

1. Define a frontend API client with the bearer token supplied through the
   authenticated deployment mechanism, never embedded in source.
2. Load account list and inbox data from authenticated endpoints.
3. Replace hardcoded cards incrementally, preserving the existing layout,
   filters, badges, and priority visual language.
4. Add explicit loading, unauthorized, disconnected-mailbox, provider-error,
   and empty states.
5. Wire draft approval only after server ownership and audit tests exist.
6. Add browser/API contract tests against synthetic data before calling the
   priority-inbox milestone complete.

This phase implements the first increment. The **Connect inbox** action asks
for the dashboard URL and bearer token at runtime, keeps both only in
`sessionStorage`, loads the first authenticated account, then loads its emails
through `GET /api/accounts` and `GET /api/emails`. Real email fields are rendered
with DOM text APIs rather than HTML interpolation. Empty, loading, connection
failure, and authentication failure states are shown in the existing message
list. The static sample remains the fallback when no runtime connection exists.

This is a development/demo workflow, not a production login flow. A token is
never committed to frontend source, but entering a bearer token in a browser
session is still an operational compromise. A production frontend needs a
proper authenticated session or OIDC/Supabase flow before public deployment.

## 7. Safety invariants

- Email content is untrusted and must not alter settings, kill-switch state,
  approval, forwarding, or recipient authorization.
- `SafetyRules.should_flag_for_human` runs deterministic sensitive-topic,
  first-time-sender, emotional, ambiguous, and sensitive-category checks.
- `WorthSendingPolicy.should_send_reply` requires a response need, sufficient
  confidence, non-automated/non-no-reply sender, no sensitive topic, and
  sender history; rate-limit input is supported.
- `SendFlow.process_draft` enforces approve, auto-safe, and auto-full modes,
  with routine detection and a cancellation check.
- The current delayed-send implementation is test-simulated and not yet a
  durable queue/undo guarantee.
- Authorization and current autonomy/kill-switch state must be rechecked
  immediately before a real external send in future worker work.
- Model output must be schema-validated before provider actions; this remains
  incomplete in v1.

## 8. Remaining 11-day sequence

| Milestone | Prerequisites | Acceptance criteria / blocker |
|---|---|---|
| Day 2: provider adapters and BYOK | This audit; encrypted key contract | Typed provider slots, safe key storage, no direct plaintext exposure |
| Day 3: prefilter and classification | Normalized message contract | Deterministic labels preserve v1 regression behavior |
| Day 4: authenticated priority inbox | Authenticated API and frontend client | Real mailbox data, ownership tests, useful error states |
| Day 5: thread-aware drafting | Stable thread retrieval | Persistent drafts distinguish generated vs approved |
| Day 6: worth-sending/send flow | Recipient resolution, validation, idempotency | No duplicate sends; policy and authorization at dispatch |
| Day 7: autonomy and kill switch | Durable worker path | Every retry/background path enforces current controls |
| Day 8: activity and teach loop | Audit events and persistent decisions | Corrections associate with future guidance |
| Day 9: digest/follow-ups | Sync state and scheduling | Durable timestamps and thread state |
| Day 10: unsubscribe/summaries | Scoped provider actions | Untrusted content cannot broaden action scope |
| Day 11: agent chat/calendar experiments | Stable core workflow and permissions | Only proceed if core email path is reliable |
| Day 12: polish/onboarding | Real API behavior | Disconnected/invalid-model states are useful |
| Day 13: final validation/demo | Synthetic fixtures and deployment config | End-to-end real behavior, tests, docs, and demo |

Schema and credential changes should remain serialized. Do not run parallel
work against the same migration or active agent pipeline.

## 9. Changes made in this phase

- Added single-principal bearer authentication and fail-closed configuration
  handling to the dashboard.
- Removed client-supplied identity from account and voice-profile resolution.
- Added account/email ownership checks for account-derived routes.
- Restricted CORS and disabled credentialed wildcard access.
- Added draft and email-owner lookup methods.
- Stopped account API responses from including credentials.
- Encrypted new account credentials with a versioned AES-256-GCM envelope and
  owner/provider/email associated data.
- Added migration contract
  [`002_credential_encryption_contract.sql`](mailagent/supabase/migrations/002_credential_encryption_contract.sql).
- Added Render configuration entries for dashboard auth and CORS settings.
- Connected the existing static inbox shell to the authenticated account/email
  endpoints with runtime loading, empty, success, and error states.

## 10. Remaining risks and blockers

- Multi-user authentication is not implemented; the current containment is
  suitable only for one explicitly configured principal.
- Existing plaintext credential rows require an approved migration and cannot
  be used by the new reader until migrated.
- Dashboard import requires valid Supabase settings; no local API integration
  test exists yet.
- The frontend workflow was syntax-checked but not live-verified because no
  configured Supabase database, dashboard token, mailbox account, or allowed
  browser origin was available in this environment.
- Supabase service-role access and database RLS policies remain deployment
  concerns.
- Model output validation, idempotency, durable undo, incremental sync,
  IMAP/SMTP sending, and retry recovery remain incomplete.
- The frontend remains static until authenticated API contracts are tested.

## Stop condition

Day 1 is complete for the agreed scope: the v1 path is mapped and preserved,
the demonstrated public API exposure has a concrete containment layer, new
credential writes fail closed into an encrypted representation, the production
migration is planned but not executed, and the remaining work is sequenced
without starting the Day 2 adapter/BYOK milestone.
