# Mail Agent

**Privacy-first, open-source AI email agent. Your data never leaves your machine unless you explicitly configure an external AI provider or connect an email account.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What It Does

Mail Agent reads your email, classifies it by priority, filters out noise, and drafts responses — all locally on your computer. You approve every action before anything is sent. A built-in kill switch stops all autonomous operations instantly.

### Features

| Feature | Status |
|---|---|
| Zero-token pre-filter (newsletters, no-reply addresses) | ✅ Implemented |
| LLM-based email classification with confidence scores | ✅ Implemented |
| Priority inbox with server-side filtering and pagination | ✅ Implemented |
| Persistent email labels | ✅ Implemented |
| Draft generation and human-approval workflow | ✅ Implemented |
| Undo window / cancellable send (delayed dispatch) | ✅ Implemented |
| Kill switch (blocks all autonomous sending) | ✅ Implemented |
| Idempotency guard (prevents duplicate sends) | ✅ Implemented |
| Rate limiting (per-account, per-hour, per-thread-per-day) | ✅ Implemented |
| Local SQLite storage (no cloud dependency) | ✅ Implemented |
| AES-256-GCM encrypted credential storage | ✅ Implemented |
| OS keychain integration (Windows Credential Manager) | ✅ Implemented |
| BYOK: Claude, OpenAI, Google AI, Ollama | ✅ Implemented |
| Gmail OAuth provider | ✅ Implemented (needs live credentials) |
| IMAP provider | ✅ Implemented (needs live credentials) |
| Local APScheduler task queue | ✅ Implemented |
| Authenticated data export and deletion | ✅ Implemented |
| Windows Electron desktop wrapper (loopback, ephemeral token) | ✅ Implemented |
| Privacy disclosure endpoint | ✅ Implemented |
| User voice-profile learner | ✅ Implemented |

### Known Limitations

- **Enterprise multi-tenant RBAC**: Single configured principal only. Full identity-provider integration, per-tenant isolation, and delegated administration are **not** implemented.
- **PostgreSQL retention/deletion**: `delete_user_data` for the Supabase backend is not implemented (administrator migration required).
- **macOS / Linux desktop packages**: Not built or tested. The Python/FastAPI backend runs cross-platform; only the Electron wrapper targets Windows 10/11.
- **Celery/Redis in this environment**: Enterprise queue not tested in CI; personal (local) queue is the supported default.
- **No external security audit or compliance certification** has been performed.

---

## Privacy Promise

1. No mandatory Mail Agent-hosted backend, central account, telemetry, or analytics.
2. Personal mode uses local SQLite and an in-process task queue — no network calls beyond your configured email provider.
3. Cloud AI sends **only the data required for inference** to the provider you explicitly configure with your own API key. This is disclosed clearly.
4. Your email provider credentials and AI API keys are encrypted with AES-256-GCM before being written to disk.
5. Every autonomous action is logged and auditable.

---

## Prerequisites

| Component | Required | Version |
|---|---|---|
| Python | ✅ | 3.11 or 3.12 |
| Node.js | For desktop wrapper only | 18+ |
| Git | For cloning | any |
| OS keychain | Recommended for personal mode | Windows Credential Manager |

---

## Personal Mode Installation (Local, No Cloud)

```powershell
# 1. Clone the repository
git clone https://github.com/your-org/mailagent.git
cd mailagent

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your environment file (never commit this)
Copy-Item .env.example .env

# 5. Generate and set an encryption key (run once, keep the output secret)
python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
# Paste the output into .env as: MAILAGENT_ENCRYPTION_KEY=<value>

# 6. Start the dashboard (personal defaults: SQLite + local queue, loopback only)
python -m uvicorn mailagent.dashboard.app:app --host 127.0.0.1 --port 8765
```

The API is now accessible at `http://127.0.0.1:8765`. Open a browser and visit that URL (you will need a configured `DASHBOARD_API_TOKEN` to use authenticated endpoints).

**Personal mode requires no Supabase, Redis, Celery, or Mail Agent cloud account.**

---

## Windows Desktop Wrapper

The Electron wrapper starts the Python backend automatically and serves the web UI in a secure sandboxed window. The token is generated fresh on each launch and never persisted.

```powershell
cd desktop
npm install
npm start                      # development launch
npm run build                  # build a Windows portable executable
```

**Requirements**: Node.js 18+, `electron` and `electron-builder` (installed via `npm install`).

**Runtime requirements when running the packaged app**: Python 3.11+ must be on PATH, or set `MAILAGENT_PYTHON` to the full path of the Python executable.

---

## Email Provider Setup

### Gmail (OAuth 2.0)

1. Create a Google Cloud project and enable the Gmail API.
2. Create an OAuth 2.0 client ID (Desktop application type).
3. Set in `.env`:
   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   GOOGLE_REDIRECT_URI=http://localhost:8765/auth/gmail/callback
   ```
4. Use the `/auth/gmail` endpoints to complete OAuth authorization.

### IMAP

1. Generate an app-specific password in your email provider's security settings.
2. Configure your account via the API:
   ```
   POST /api/accounts
   {"provider": "imap", "email_address": "you@example.com",
    "credentials": {"host": "imap.example.com", "port": 993,
                    "username": "you@example.com", "password": "<app-password>"}}
   ```
   Credentials are encrypted before storage.

---

## BYOK AI Configuration

```ini
# In .env — choose one or more providers; all keys are encrypted before storage
ANTHROPIC_API_KEY=sk-ant-...       # Claude (classification + drafting)
OPENAI_API_KEY=sk-...              # OpenAI
GOOGLE_AI_API_KEY=...              # Google AI
OLLAMA_BASE_URL=http://localhost:11434/v1  # Local Ollama (no API key needed)
```

Or configure per-user via the API:
```
POST /api/provider-settings
{"provider": "claude", "api_key": "sk-ant-...", "model_classification": "claude-3-5-haiku-latest"}
```

**Cloud AI disclosure**: When a cloud provider is configured, email content is sent to that provider for inference. Only the content needed for classification or drafting is included. No data is sent to Mail Agent.

---

## Secure Credential and Encryption Key Management

- The `MAILAGENT_ENCRYPTION_KEY` must be a 256-bit key encoded as base64url.
- If the variable is absent, the application attempts to use the OS keychain (Windows Credential Manager). If the keychain is also unavailable, the application refuses to start.
- The encryption key must remain **separate from the encrypted data** it protects. Never commit it to source control.
- Use a secrets manager (Azure Key Vault, AWS Secrets Manager, HashiCorp Vault) in production.

---

## Data Storage, Export, Backup, and Recovery

| What | Where |
|---|---|
| Emails, classifications, drafts | `mailagent.db` (SQLite, encrypted credentials) |
| Local task queue | `mailagent-queue.db` (APScheduler SQLite job store) |
| API keys, email credentials | Encrypted within `mailagent.db` |
| Encryption key | OS keychain or `MAILAGENT_ENCRYPTION_KEY` env var |

**Export**: `GET /api/privacy/export` — returns your data without credential fields.

**Deletion**: `DELETE /api/privacy/data` — transactional delete of all user records including emails, labels, drafts, classifications, accounts, provider settings, and voice profiles.

**Backup**: Copy `mailagent.db` to a secure location. The backup is protected by the same encryption key; keep the key separately.

**Recovery**: Restore `mailagent.db` from backup. The same encryption key must be available. A different key will cause credential decryption to fail safely.

---

## External Network Destinations

Mail Agent calls the following external services **only when explicitly configured**:

| Service | When | Data Sent |
|---|---|---|
| Gmail API | When a Gmail account is configured | OAuth token + email headers/body for sync |
| IMAP server | When an IMAP account is configured | Credentials + email data for sync |
| Anthropic / OpenAI / Google AI | When BYOK key is configured | Email content for classification or drafting |
| Ollama (local) | When configured | Loopback only, no internet |

**No data is ever sent to any Mail Agent-operated service.**

---

## Autonomy Modes and Send Safety

| Mode | Behavior |
|---|---|
| `approve` (default) | All replies require explicit human approval |
| `auto_safe` | Short, routine replies (acknowledgments etc.) sent after delay window |
| `auto_full` | All policy-passing replies sent after delay window |

All autonomous sends go through a configurable delay window (`DELAY_SEND_SECONDS`, default 60s) during which the action can be cancelled. The kill switch cancels all pending drafts immediately.

---

## Environment Variables

See [`.env.example`](.env.example) for a full annotated reference. Critical variables:

| Variable | Purpose | Default |
|---|---|---|
| `MAILAGENT_ENCRYPTION_KEY` | AES-256 key (base64url). Required if keychain unavailable | (keychain) |
| `DASHBOARD_HOST` | Bind address. **Must be 127.0.0.1 in personal mode** | `127.0.0.1` |
| `DASHBOARD_API_TOKEN` | Bearer token for API authentication | (must be set) |
| `DASHBOARD_USER_ID` | User identity for single-principal mode | (must be set) |
| `STORAGE_BACKEND` | `sqlite` (personal) or `supabase` (enterprise) | `sqlite` |
| `TASK_QUEUE_BACKEND` | `local` (personal) or `celery` (enterprise) | `local` |

---

## Running Tests

```powershell
# Full suite (91 tests as of v0.1.0)
python -m pytest tests/ -v

# Security hardening tests only
python -m pytest tests/test_day12_hardening.py -v
```

All tests use mocked external services. No real emails are sent during testing.

---

## Enterprise Configuration (PostgreSQL + Celery)

```ini
STORAGE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
TASK_QUEUE_BACKEND=celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

**Known enterprise gaps**: Multi-tenant isolation, RBAC, delegated administration, identity-provider integration, and PostgreSQL-level data retention/deletion are not yet implemented. Do not expose this service publicly without an HTTPS reverse proxy.

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| `MAILAGENT_ENCRYPTION_KEY is required when the OS keychain is unavailable` | No key set and keychain not accessible | Set `MAILAGENT_ENCRYPTION_KEY` in `.env` |
| `Dashboard authentication is not configured` (503) | `DASHBOARD_API_TOKEN` or `DASHBOARD_USER_ID` not set | Set both in `.env` |
| Backend fails to start in Electron | Python not on PATH | Set `MAILAGENT_PYTHON=C:\path\to\python.exe` |
| `account credentials cannot be decrypted` | Encryption key changed | Restore the original key or re-provision the account |
| APScheduler import error | Missing dependency | `pip install -r requirements.txt` |

---

## License

[MIT](LICENSE) — see LICENSE for details.
