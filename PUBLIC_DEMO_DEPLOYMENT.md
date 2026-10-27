# Public Demo Deployment

This deployment profile is for a no-login hackathon demo with synthetic email
data. It is intentionally separate from the enterprise deployment profile.

## Architecture blockers found and resolved

Before this change, `render.yaml` provisioned a web service, Celery worker,
Celery beat, and Redis, and configured the web service for Supabase/Celery.
Production settings also rejected startup without enterprise credentials.
Demo mode could additionally construct its SQLite secret store from the OS
keychain or `MAILAGENT_ENCRYPTION_KEY`.

The public profile now uses one Render web service, SQLite in `/tmp`, the
existing local/in-process path, and a demo-only in-memory encryption key.
No Gmail, SMTP, Supabase, Redis, Celery, Claude, or OpenRouter credential is
required.

## Required environment variables

These are the only required Render settings:

```text
ENVIRONMENT=production
PUBLIC_DEMO_MODE=true
STORAGE_BACKEND=sqlite
TASK_QUEUE_BACKEND=local
DEMO_SQLITE_DB_PATH=/tmp/mailagent-public-demo.db
```

The `render.yaml` file supplies these values. The demo does not require:

- `DASHBOARD_API_TOKEN`
- `DASHBOARD_USER_ID`
- `MAILAGENT_ENCRYPTION_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- Gmail OAuth credentials
- SMTP credentials
- Claude/OpenAI/Google AI credentials

## Optional environment variables

```text
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=google/gemma-2-9b-it:free
DEMO_RATE_LIMIT_PER_MINUTE=30
DEMO_MAX_CONCURRENT_REQUESTS=5
DEMO_RESET_ENDPOINT_ENABLED=true
```

`OPENROUTER_API_KEY` is server-side only and is never returned by the API.
When it is absent, or when OpenRouter fails, the demo uses a clearly labelled
deterministic fallback provider. The demo never selects another paid provider
implicitly.

## Exact Render configuration

Use the repository's `render.yaml` blueprint:

```text
Service type: Web Service
Runtime: Python
Plan: Free (or another single web-service plan)
Build command: pip install -r requirements.txt
Start command: uvicorn mailagent.dashboard.app:app --host 0.0.0.0 --port $PORT
Health check path: /health
```

Do not add worker, private service, Redis, Supabase, or database services.
After Render creates the service, its public URL is the API and frontend URL.
The public landing page is `/`; the demo dashboard is `/app/index.html`.

## Local verification

Run the same profile locally without any external credentials:

```powershell
$env:ENVIRONMENT = "production"
$env:PUBLIC_DEMO_MODE = "true"
$env:STORAGE_BACKEND = "sqlite"
$env:TASK_QUEUE_BACKEND = "local"
$env:DEMO_SQLITE_DB_PATH = "$env:TEMP\mailagent-public-demo-test.db"
Remove-Item -Force -ErrorAction SilentlyContinue $env:DEMO_SQLITE_DB_PATH
python -m uvicorn mailagent.dashboard.app:app --host 127.0.0.1 --port 8766
```

Then open `http://127.0.0.1:8766/`.

## Demo security boundaries

- `/` and `/health` are public.
- `/app/index.html`, `/app/app.js`, and `/app/styles.css` are public frontend
  assets.
- Public demo endpoints use a fixed synthetic user/account and a per-client
  rate limiter.
- `/api/accounts`, classified inbox browsing, email details, demo draft
  generation, draft approval, simulated send, demo status, and demo reset are
  available only through the demo dependency when `PUBLIC_DEMO_MODE=true`.
- Raw email listing, privacy data, kill-switch, classifications, audit log,
  provider settings, voice profile, rate limits, and stats remain protected by
  the normal dashboard authentication dependency.
- The demo account is `judge@example.com` and contains only synthetic data.
- Draft approval and `/api/demo/send` update demo state only. They never call
  Gmail, IMAP, SMTP, or a sending provider.
- `/tmp` is ephemeral on Render. A restart can reset the demo, which is
  acceptable and intentional for a hackathon demo.
- The demo-only encryption key protects the synthetic database record in
  process; it must not be used for a real deployment.

## Useful demo endpoints

```text
GET  /api/demo/status
GET  /api/accounts
GET  /api/emails/with-classifications?account_id=demo-account-001
GET  /api/emails/{email_id}
POST /api/demo/drafts/generate
POST /api/drafts/approve
POST /api/demo/send
POST /api/demo/reset
```

`POST /api/demo/drafts/generate` accepts
`{"email_id":"..."}`. It returns `provider`, `model`, and `fallback` so a
judge can see whether the response came from OpenRouter or deterministic demo
logic.

## Tests and actual results

Focused validation completed:

```text
python -m pytest -q tests/test_demo_mode.py tests/test_dashboard_auth.py tests/test_deployment_config.py
17 passed, 4 warnings
```

The warnings are existing FastAPI `on_event` deprecation warnings.

The isolated no-credential server was started with production settings and
the following checks passed:

```text
GET /health                                      200
GET /api/demo/status                             200, fallback provider
GET /api/accounts                                200
GET /api/emails/with-classifications             200, 12 synthetic emails
GET /api/emails                                  503, protected without auth
GET /api/emails/{email_id}                       200, synthetic detail
POST /api/demo/drafts/generate                   200, deterministic fallback
POST /api/drafts/approve                         200, approved
POST /api/demo/send                              200, simulated=true, sent
POST /api/demo/reset                             200, reset=true
```

Python compilation and `git diff --check` also passed.

The full regression suite completed after the compatibility fix:

```text
python -m pytest -q
104 passed, 5 warnings
```

There is no production frontend build command to run: the frontend is a
static HTML/CSS/JavaScript surface with no root `package.json` or bundler.
The static assets were syntax-checked and served successfully during smoke
testing.

## Remaining blockers before launch

1. Create the Render service from the updated blueprint and confirm the
   generated public URL.
2. Verify Render's free-plan filesystem behavior and cold-start timing with
   the real service.
3. Decide whether to set an OpenRouter key. It is optional; the deterministic
   fallback is the safe no-cost default.
4. Perform one manual browser smoke test against the deployed URL.
5. Do not expose production dashboard credentials or switch this service to
   Supabase/Celery without creating a separate enterprise deployment.
