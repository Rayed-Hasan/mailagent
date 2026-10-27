# Public Demo Deployment — Real Gmail Integration

This deployment profile configures MailAgent for a no-login public judge demonstration integrated with a **dedicated, real Gmail account**.

Judges can open the public website without creating an account or logging in, view real test messages, filter by AI priority and category, and generate reply drafts using OpenRouter (with deterministic fallback).

---

## 1. Google Cloud Project & Gmail API Setup

1. **Create/Select a Google Cloud Project**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a project named `MailAgent-Demo`.
2. **Enable Gmail API**:
   - Navigate to **APIs & Services > Library**.
   - Search for **Gmail API** and click **Enable**.
3. **Configure OAuth Consent Screen**:
   - User Type: **External**.
   - App name: `MailAgent Demo`.
   - User support email: Select your dedicated demo Gmail address.
   - Test Users: Add the dedicated test Gmail address (e.g. `your-dedicated-demo@gmail.com`).
4. **Required OAuth Scopes**:
   - `https://www.googleapis.com/auth/gmail.readonly` (read-only inbox access for classification and synchronization).
   - `https://www.googleapis.com/auth/gmail.compose` (create and view drafts).
5. **Create OAuth 2.0 Client Credentials**:
   - Navigate to **APIs & Services > Credentials > Create Credentials > OAuth client ID**.
   - Application Type: **Web application**.
   - Name: `MailAgent Web Client`.
   - Authorized redirect URIs:
     - Local testing: `http://localhost:8000/auth/gmail/callback` (or `http://127.0.0.1:8766/auth/gmail/callback`)
     - Deployed Render URL: `https://mailagent-public-demo.onrender.com/auth/gmail/callback`
   - Copy the generated `Client ID` and `Client Secret`.

---

## 2. Environment Variables

### Core Demo Settings
```text
ENVIRONMENT=production
PUBLIC_DEMO_MODE=true
STORAGE_BACKEND=sqlite
TASK_QUEUE_BACKEND=local
DEMO_SQLITE_DB_PATH=/tmp/mailagent-public-demo.db
DASHBOARD_ALLOWED_ORIGINS=*
```

### Real Gmail Credentials (Render Persistent Configuration)
To persist authorization across Render restarts and redeployments without paid add-ons, set:
```text
DEMO_GMAIL_CLIENT_ID=<your-google-client-id>
DEMO_GMAIL_CLIENT_SECRET=<your-google-client-secret>
DEMO_GMAIL_REDIRECT_URI=https://mailagent-public-demo.onrender.com/auth/gmail/callback
DEMO_GMAIL_REFRESH_TOKEN=<your-google-refresh-token>
DEMO_GMAIL_EMAIL=<your-dedicated-demo-account>@gmail.com
```

### Owner Admin Security
Protects owner-only mailbox connection, setup, and sensitive configuration:
```text
DASHBOARD_API_TOKEN=<strong-secret-token-for-owner-only>
DASHBOARD_USER_ID=demo-owner
```

`DASHBOARD_API_TOKEN` and `DASHBOARD_USER_ID` are both required. The token is
the secret bearer credential; `DASHBOARD_USER_ID` is the non-secret principal
identifier returned internally after successful authentication.

### AI Inference (OpenRouter)
```text
OPENROUTER_API_KEY=<optional-openrouter-key>
OPENROUTER_MODEL=google/gemma-2-9b-it:free
```
*Note: If `OPENROUTER_API_KEY` is not set or rate limits occur, MailAgent automatically uses the clearly labelled deterministic fallback provider.*

### Public Safeguards
```text
DEMO_RATE_LIMIT_PER_MINUTE=30
DEMO_MAX_CONCURRENT_REQUESTS=5
DEMO_ALLOW_PUBLIC_SEND=false
DEMO_RESET_ENDPOINT_ENABLED=true
```

---

## 3. Owner-Only Mailbox Authorization

Judges never connect their personal accounts or log in. The owner authorizes the single dedicated demo Gmail account once:

### Method A: Environment Configuration (Recommended for Render)
1. Acquire a refresh token for the dedicated Gmail account (e.g., using the owner OAuth flow or Google OAuth Playground with your Client ID/Secret).
2. Set `DEMO_GMAIL_REFRESH_TOKEN`, `DEMO_GMAIL_CLIENT_ID`, `DEMO_GMAIL_CLIENT_SECRET`, and `DEMO_GMAIL_EMAIL` in Render environment variables.
3. Upon boot, MailAgent automatically connects to Gmail, verifies the token, and syncs test messages into the priority inbox.

### Method B: Authenticated Owner Endpoint (Browser)
1. Owner opens `GET /api/owner/gmail/auth-url` with header:
   ```text
   Authorization: Bearer <DASHBOARD_API_TOKEN>
   ```
2. The endpoint returns a one-time Google OAuth authorization URL with CSRF state protection.
3. Owner authorizes the dedicated Gmail account in the browser.
4. Google redirects to `GET /auth/gmail/callback`; the owner then submits the returned code and state to `POST /api/owner/gmail/callback` (authenticated).
5. MailAgent exchanges the code for a refresh token, saves it encrypted in SQLite, and performs the initial mailbox synchronization.

---

## 4. Public Routes vs Protected Routes

| Endpoint | Access Level | Description |
|---|---|---|
| `GET /` | Public | Product landing page |
| `GET /app/index.html` | Public | Priority inbox interface for judges |
| `GET /app/app.js`, `styles.css` | Public | Static UI assets |
| `GET /health` | Public | Service health check |
| `GET /api/demo/status` | Public | Real Gmail connection status, sync time, model |
| `GET /api/accounts` | Public (Demo) | Returns single configured demo mailbox metadata |
| `GET /api/emails/with-classifications` | Public (Demo) | Priority inbox data with sorting and filters |
| `GET /api/emails/{id}` | Public (Demo) | View email details, category, reason |
| `POST /api/demo/sync` | Public (Demo) | Triggers mailbox synchronization (rate limited) |
| `POST /api/demo/drafts/generate` | Public (Demo) | Generate AI reply draft (OpenRouter or fallback) |
| `POST /api/drafts/approve` | Public (Demo) | Approve draft in review queue |
| `POST /api/demo/send` | Restricted | Public sending is **disabled** (`403 Forbidden`) by default |
| `GET /api/owner/gmail/auth-url` | **Owner Only** | Requires `DASHBOARD_API_TOKEN` |
| `POST /api/owner/gmail/callback` | **Owner Only** | Requires `DASHBOARD_API_TOKEN` |
| `GET /api/emails` (raw) | **Owner Only** | Requires `DASHBOARD_API_TOKEN` |
| `GET /api/privacy/export` | **Owner Only** | Requires `DASHBOARD_API_TOKEN` |
| `POST /api/kill-switch` | **Owner Only** | Requires `DASHBOARD_API_TOKEN` |

---

## 5. Persistence on Render Free Tier

On Render's free tier, `/tmp` is ephemeral and restarts occur during deploys or idle periods.

1. **How Mailbox Persists Across Redeployments**:
   - Because `DEMO_GMAIL_REFRESH_TOKEN` and client credentials reside in Render's environment configuration, MailAgent recreates and synchronizes the local SQLite database automatically whenever the instance restarts.
   - Deduplication guarantees that re-synchronizing Gmail messages never produces duplicate emails or classifications in SQLite.
2. **Local Windows Persistence**:
   - Local runs store the SQLite database at `mailagent.db` or the configured `sqlite_db_path`, preserving all messages and credentials persistently across process restarts.

---

## 6. Verification Status

### Implemented & Verified in Test Suite
- **113/113 automated unit & integration tests passing**:
  - OAuth authorization URL generation with cryptographic state.
  - Authorization code exchange and token expiry refresh.
  - Real message body/header normalization into `EmailMessage`.
  - SQLite database deduplication (`save_email` returns existing ID on identical `message_id`).
  - Gmail sync service idempotent resynchronization.
  - Zero-login judge access to `/api/demo/status`, `/api/accounts`, and `/api/emails/with-classifications`.
  - Denial of anonymous visitors from `/api/owner/gmail/*` and protected endpoints (`401 Unauthorized`).
  - Prevention of anonymous email sending (`403 Forbidden`).
  - OpenRouter inference handling with labelled deterministic fallback (`fallback: true`).

### Live Testing Steps (Once Owner Credentials are Configured)
1. Send 5–6 genuine test emails to your dedicated Gmail account from different external addresses (e.g., invoices, meeting requests, urgent questions).
2. Set `DEMO_GMAIL_REFRESH_TOKEN`, `DEMO_GMAIL_CLIENT_ID`, `DEMO_GMAIL_CLIENT_SECRET`, and `DEMO_GMAIL_EMAIL` in `.env` (or Render dashboard).
3. Start the dashboard or click **Sync Mailbox** in the UI.
4. Verify that the 5–6 real test emails appear in the priority inbox sorted by AI priority.
5. Open an email and click **Generate AI Reply Draft** to verify live OpenRouter draft generation.

## 7. First Render Redeploy Checklist

The repository is configured as one Render web service. Do not create a separate
frontend service.

1. Review the working tree and commit the intended changes:
   ```powershell
   git diff --check
   git add render.yaml mailagent .env.example PUBLIC_DEMO_DEPLOYMENT.md tests
   git commit -m "Prepare live Gmail OAuth deployment"
   git push origin main
   ```
   Never stage `.env`, refresh tokens, client secrets, or API keys.
2. In Render, redeploy the `mailagent-public-demo` service from the new `main`
   commit. The service must use:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn mailagent.dashboard.app:app --host 0.0.0.0 --port $PORT`
   - Health check: `/health`
3. Configure these non-secret production values:
   ```text
   ENVIRONMENT=production
   PUBLIC_DEMO_MODE=true
   STORAGE_BACKEND=sqlite
   TASK_QUEUE_BACKEND=local
   DEMO_SQLITE_DB_PATH=/tmp/mailagent-public-demo.db
   DEMO_GMAIL_REDIRECT_URI=https://mailagent-public-demo.onrender.com/auth/gmail/callback
   ```
4. Configure these owner-only values before enabling Gmail:
   ```text
   DASHBOARD_API_TOKEN=<strong-random-token>
   DASHBOARD_USER_ID=demo-owner
   DEMO_GMAIL_CLIENT_ID=<Google OAuth client ID>
   DEMO_GMAIL_CLIENT_SECRET=<Google OAuth client secret>
   DEMO_GMAIL_REFRESH_TOKEN=<owner-authorized refresh token>
   DEMO_GMAIL_EMAIL=<dedicated-demo-address>
   ```
5. In Google Cloud, add exactly this Authorized redirect URI:
   ```text
   https://mailagent-public-demo.onrender.com/auth/gmail/callback
   ```
6. Verify `/health`, `/`, `/app/index.html`, and
   `/auth/gmail/callback` after deployment. The owner authorization URL and
   code-exchange routes must continue to require the bearer token:
   `GET /api/owner/gmail/auth-url` and
   `POST /api/owner/gmail/callback`.

The Render process binds to `0.0.0.0` and Render's `$PORT`. The Windows desktop
launcher intentionally remains loopback-only (`127.0.0.1`) and does not use this
production bind configuration.
