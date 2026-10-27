# Mail Agent v0.1.0 — Release Notes

**Release date**: 2026-10-27
**Status**: Initial open-source release (personal mode)

---

## What This Release Includes

### Core Functionality

- **Email pre-filtering**: Newsletters, promotional content, and no-reply senders are filtered before any LLM call, keeping inference costs near zero for noise.
- **LLM-based classification**: Emails are classified into 10 categories with a priority score (0-100), confidence rating, and plain-language reason.
- **Priority inbox**: Filtered and paginated inbox with server-side sorting by priority or date, and filtering by category, label, and reply-needed status.
- **Persistent labels**: Labels are deduplicated and stored per email; system and user labels are distinguished.
- **Draft generation**: AI-drafted replies in the user's own voice style.
- **Approval workflow**: All sends require explicit human approval in default `approve` mode.
- **Undo window**: Autonomous sends are delayed (default: 60 seconds) and can be cancelled before dispatch.
- **Kill switch**: Instantly cancels all pending sends and blocks new autonomous actions.
- **Idempotency**: A second send attempt for the same email is rejected before queuing.
- **Rate limiting**: Configurable maximum auto-replies per hour and one reply per thread per day.
- **Local storage**: SQLite with AES-256-GCM encrypted credentials and API keys.
- **OS keychain**: Encryption key is generated and stored in the OS keychain on first use if not otherwise provided.
- **BYOK**: Bring-Your-Own-Key for Claude, OpenAI, Google AI, and local Ollama.
- **Gmail OAuth provider**: Full OAuth 2.0 flow with token encryption.
- **IMAP provider**: Encrypted password storage and standard IMAP/SSL.
- **Local task queue**: APScheduler with SQLite job store — survives process restarts.
- **Authenticated data export**: `GET /api/privacy/export` returns user data without credentials.
- **Transactional deletion**: `DELETE /api/privacy/data` removes all records in one SQLite transaction.
- **Windows Electron wrapper**: Loopback-only binding, 256-bit ephemeral token per launch, sandboxed WebView, safe shutdown.
- **Privacy disclosure endpoint**: `GET /api/privacy` returns machine-readable disclosure of all data flows.

### Security (Days 12-14 Hardening)

- Fixed `DASHBOARD_HOST=0.0.0.0` dangerous default in `.env.example` → `127.0.0.1`
- Replaced `print()` statements in send flow with structured `logging` (prevents uncontrolled stdout disclosure)
- Fixed `delete_email_label` always returning `True` regardless of whether the label existed
- Fixed all `datetime.utcnow()` deprecations with timezone-aware `datetime.now(timezone.utc)`
- Fixed Pydantic V2 `class Config` deprecation → `model_config = ConfigDict`
- Added `pytest.ini` with `asyncio_mode=auto` to silence pytest-asyncio deprecation warning
- Added 18 new security hardening tests covering: token entropy, auth boundaries, encryption key separation, AAD binding, plaintext credential absence from DB, transactional delete completeness, label deletion correctness, kill switch effectiveness, send idempotency, CORS defaults, privacy disclosure, env host validation, credential stripping from public APIs, and asset-serving path traversal protection.

---

## Test Results

```
python -m pytest tests/ -v
91 passed, 1 warning in 28.07s  (EXIT 0)
```

The 1 warning is from Starlette's test client (`anyio.abc.BlockingPortal` renamed upstream) — not from Mail Agent code.

**Checks passed**:
- `node --check desktop/main.js` → syntax OK
- `python -c "from mailagent.dashboard.app import app"` → imports OK
- `git diff --check` → no whitespace errors

---

## Live vs Mocked Integrations

| Integration | Status in This Release |
|---|---|
| Gmail API (email sync/send) | **Mocked** — real credentials required |
| IMAP server (email sync/send) | **Mocked** — real credentials required |
| Claude / OpenAI / Google AI | **Mocked** — BYOK credentials required |
| Ollama (local) | Requires running Ollama instance |
| SQLite (local storage) | **Live** — in-process, tested |
| OS keychain | **Live** — Windows Credential Manager |
| Local APScheduler queue | **Live** — tested |
| Supabase / PostgreSQL | Not tested (requires enterprise credentials) |
| Redis / Celery | Not tested (requires Redis instance) |

---

## Known Issues and Remaining Gaps

1. **Enterprise multi-tenant RBAC**: Not implemented. Single principal per deployment only.
2. **PostgreSQL-level user deletion**: Raises `NotImplementedError` — administrator migration required.
3. **macOS / Linux desktop packages**: Not built or tested.
4. **HTTPS reverse proxy**: Enterprise deployments must configure a proxy; no TLS built in.
5. **No external security audit**: This software has not been audited by a third party.
6. **Celery/Redis test coverage**: Enterprise queue is untested in CI.
7. **Real email provider integration tests**: Omitted to avoid sending real emails or requiring live credentials in CI.
8. **Token in query string**: The Electron wrapper passes the bearer token as a URL query parameter (`?token=...`) which may appear in access logs. This is mitigated by loopback-only binding (no network log infrastructure in personal mode) but is noted for improvement.

---

## Installation (Reproducible Steps)

```powershell
git clone https://github.com/your-org/mailagent.git
cd mailagent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env: set MAILAGENT_ENCRYPTION_KEY, DASHBOARD_API_TOKEN, DASHBOARD_USER_ID
python -m pytest tests/ -v                           # Verify: 91 passed
python -m uvicorn mailagent.dashboard.app:app --host 127.0.0.1 --port 8765
```

---

## Upgrade Notes

No prior stable release. This is v0.1.0.

If migrating from development checkpoints:
- Run `python -m pytest tests/` after pulling — any new failures indicate a migration issue.
- The SQLite schema adds tables incrementally with `CREATE TABLE IF NOT EXISTS` and is backward-compatible for additions.
- If you change `MAILAGENT_ENCRYPTION_KEY`, all previously stored credentials become unreadable. Re-provision accounts after a key rotation.
