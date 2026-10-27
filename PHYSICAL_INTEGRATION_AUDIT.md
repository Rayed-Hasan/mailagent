# Mail Agent Physical Integration & Configuration Audit

Audit date: 2026-10-26
Repository: `Rayed-Hasan/mailagent`
Scope: read-only configuration review, disposable local runtime checks, safe provider failure checks, and packaging verification. No real email was sent, modified, or deleted. No live Supabase, Redis, Celery, Gmail, IMAP, SMTP, or cloud-AI service was contacted.

## Executive summary

- Personal SQLite mode is physically verified after a minimal dashboard initialization fix.
- SQLite initialization, persistence across restart, account isolation, encrypted account/provider credentials, CRUD for synthetic records, export, and deletion cascades passed against disposable databases.
- The dashboard previously started with HTTP 200 on `/` but returned 500 on authenticated `/api/status` because SQLite tables were not initialized. Startup/shutdown lifecycle hooks now initialize and close the database.
- Windows Credential Manager is available and the keychain fallback generated/retrieved an encryption key successfully. Explicit invalid-key validation also fails safely.
- The local APScheduler queue persisted an importable synthetic job across restart. Non-importable nested callables are rejected by APScheduler; the public queue API currently returns `False` and logs the serialization failure.
- Supabase/PostgreSQL and Redis/Celery were not physically verified because required settings and live service access are absent.
- Gmail OAuth, IMAP, SMTP, cloud AI, and local inference were not live-verified because credentials/services are absent. IMAP connection failure is safe. SMTP is not implemented.
- The standard Windows Electron Builder path is blocked by the current account's inability to create symlinks while extracting `winCodeSign`; a no-symlink portable archive was produced through Electron Packager and physically launched.
- Render now explicitly selects Supabase/Celery, declares Redis as a Redis resource, and production configuration refuses to start with personal backends or missing enterprise credentials.
- Enterprise readiness is not established. The repository itself documents missing identity-provider integration, multi-tenant isolation, RBAC, administrator workflows, PostgreSQL retention/deletion, and live HTTPS validation.

## Status table

| Integration | Status | Evidence | Missing configuration / blocker | Next step |
|---|---|---|---|---|
| SQLite personal storage | **VERIFIED** | Disposable SQLite database initialized; synthetic accounts, emails, classifications, drafts, labels, and provider settings persisted; restart read-back passed. | None for the tested local path. | Set `STORAGE_BACKEND=sqlite`, choose a protected `SQLITE_DB_PATH`, and run the personal checklist. |
| SQLite account isolation | **VERIFIED** | Two synthetic users were created; each saw only its own account, and deleting one user preserved the other. | Dashboard identity remains single-principal, not multi-tenant. | Keep one configured dashboard principal for personal mode. |
| SQLite export/deletion | **VERIFIED** | Export omitted credentials; deletion removed user, account, email, classification, draft, label, and provider-setting rows; foreign-key child counts reached zero. | Export currently covers accounts and emails, not every internal record in the returned payload. | Review export contract if classifications/drafts/audit history must be included in exported files. |
| Credential storage and encryption | **VERIFIED** | Windows keychain availability probe passed; AES-256-GCM disposable encrypt/decrypt path passed; invalid short key rejected. | Production key backup/recovery procedure is manual. | Back up the key separately from the database or use a managed KMS. |
| Local queue | **VERIFIED** | APScheduler SQLite job store persisted an importable synthetic job across queue restart. | Nested/non-importable callables cannot be persisted; queue shutdown left a Windows SQLite file lock during immediate cleanup. | Schedule module-level importable tasks and verify graceful process shutdown in deployment. |
| Supabase/PostgreSQL storage | **BLOCKED** | `Database(storage_backend='supabase')` correctly refused to construct with missing URL (`SupabaseException: supabase_url is required`). | `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are absent; no safe disposable PostgreSQL/Supabase instance was available. | Create a disposable project, apply migrations 001→004, verify permissions/RLS, and run non-destructive CRUD tests. |
| Supabase migrations/RLS | **CONFIGURED BUT UNTESTED** | Four ordered SQL migrations exist; foreign-key cascades and RLS enablement are present. | Migration application, ordering, policies, and actual schema compatibility were not exercised. Migration 001 enables RLS but leaves most user policies for later/operational refinement. | Apply 001, 002, 003, 004 to a disposable project and test with authenticated and service-role clients. |
| Redis/Celery enterprise queue | **NOT CONFIGURED** | Celery and Redis Python packages are installed; enterprise requirements and compose/Render definitions exist. | `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` are absent; no Redis service was reachable. | Provision Redis, set all three URLs, run worker/beat smoke tasks, and verify retries/failure results. |
| Gmail OAuth | **NOT CONFIGURED** | Gmail adapter and scopes exist in `mailagent/providers/gmail_provider.py`; no token or OAuth client was supplied. | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` are absent; no OAuth consent/app registration was tested. | Register a Google OAuth web/desktop client, configure exact redirect URI and scopes, then perform read-only list/fetch only. |
| IMAP read synchronization | **NOT CONFIGURED** | Synthetic connection to loopback port 1 failed safely without credentials/service. | No IMAP host, username, app password, or live test mailbox was supplied. | Use a disposable mailbox or local mail fixture and verify TLS, login, fetch, normalization, and disconnect. |
| SMTP | **NOT CONFIGURED** | No SMTP implementation exists in `IMAPProvider`; placeholder success was changed to explicit `NotImplementedError`. | SMTP host, port, authentication, TLS policy, and implementation are absent. | Do not enable sending through IMAP until a real SMTP adapter and safe fixture tests exist. |
| Claude AI | **NOT CONFIGURED** | `ClaudeProvider` is implemented with timeout and response parsing; no Anthropic key is present, so no live request was made. | `ANTHROPIC_API_KEY` absent; live inference was not user-enabled. | Store a BYOK key through the encrypted provider-settings path and run a consented, non-sensitive inference test. |
| OpenAI AI | **NOT CONFIGURED** | `OPENAI_API_KEY` appears in configuration/docs, but no OpenAI adapter is implemented or registered. | No adapter, provider registration, or verified model path. | Treat as unsupported until an adapter is implemented and tested. |
| Google AI | **NOT CONFIGURED** | `GOOGLE_AI_API_KEY` appears in configuration/docs, but no Google adapter is implemented or registered. | No adapter, provider registration, or verified model path. | Treat as unsupported until an adapter is implemented and tested. |
| Ollama/local inference | **BLOCKED** | No runtime responded at `127.0.0.1:11434`; the registry has no Ollama adapter. | `OLLAMA_BASE_URL` is not a `Settings` field and no local adapter is wired. | Install Ollama only if desired, then implement/register an adapter before claiming support. |
| Desktop backend startup | **VERIFIED** | Electron source binds backend to loopback, uses an ephemeral token, waits for `/`, and passes SQLite/local queue overrides. | Packaged artifact was not produced. | Complete packaging under a Windows account with Developer Mode or symlink privilege. |
| Desktop packaging and launch | **VERIFIED** | Rebuilt archive with staged backend; extracted executable opened a window titled `MailAgent — Your morning, sorted`, spawned bundled `python.exe -m uvicorn`, served root/status/privacy, persisted a disposable kill-switch marker across graceful restart, and exited cleanly. ZIP SHA-256: `5BD60BDE50152A065568818CEB64C6E486B2EF6EE0E240F991E3157236A10BC8`. | The standard `electron-builder` target remains blocked extracting `winCodeSign` because the current Windows token cannot create symlinks. | Distribute/test the verified portable archive in a controlled Windows environment; enable Developer Mode or approved symlink privilege only if an electron-builder installer/signing workflow is required. |
| Docker | **CONFIGURED BUT UNTESTED** | Dockerfile and compose file exist; Docker/Compose commands are installed. | No image build/run was completed; Dockerfile defaults to SQLite while compose overrides enterprise backends. | Build/run only with a disposable `.env`, initialize the database, and probe health/auth endpoints. |
| Render | **BLOCKED** | `render.yaml` declares web, worker, beat, and Redis-related settings. | `STORAGE_BACKEND` and `TASK_QUEUE_BACKEND` are not set in Render services, so application defaults remain SQLite/local; the Redis declaration is under `databases`, not a verified Render Redis resource. | Correct the blueprint using Render's Redis resource syntax, explicitly set enterprise backends, and validate in a private/staging project. |
| Privacy/network behavior | **VERIFIED** | `/api/privacy` reported no telemetry and explicit external-provider behavior; static inspection found only configured Gmail/IMAP/AI destinations and loopback dashboard binding in personal mode. | No packet-level test was performed because no external provider was configured. | Recheck outbound destinations after each provider is enabled; keep cloud inference opt-in. |

## Environment variables

Values were not printed. The current process environment had all audited variables **missing**. Defaults below come from `mailagent/core/config.py` or `.env.example`; “required” means required for that selected integration, not for every personal installation.

| Name | Purpose | Personal requirement | Enterprise/provider requirement | Configured location |
|---|---|---:|---:|---|
| `ANTHROPIC_API_KEY` | Claude BYOK credential | Optional | Required for Claude | `.env`, Render secret |
| `OPENAI_API_KEY` | Placeholder OpenAI credential | Unsupported | Not usable: no adapter | `.env.example`, `Settings.openai_api_key` |
| `GOOGLE_AI_API_KEY` | Placeholder Google AI credential | Unsupported | Not usable: no adapter | `.env.example`, `Settings.google_ai_api_key` |
| `MAILAGENT_ENCRYPTION_KEY` | Base64url 32-byte AES key | Required if OS keychain unavailable | Required unless KMS/keychain is supplied | `.env`, secret manager |
| `MODEL_CLASSIFICATION` | Classification model name | Optional | Optional | `.env.example`, `Settings.model_classification` |
| `MODEL_DRAFTING` | Drafting model name | Optional | Optional | `.env.example`, `Settings.model_drafting` |
| `MONTHLY_BUDGET_USD` | AI budget setting | Optional | Optional | `.env.example`; not currently a `Settings` field |
| `MAX_REPLIES_PER_THREAD_PER_DAY` | Per-thread reply cap | Optional | Optional | `.env.example`; not currently a `Settings` field |
| `SUPABASE_URL` | Supabase project URL | No | Required for Supabase | `.env`, Render secret |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side Supabase service key | No | Required for current server client | `.env`, Render secret |
| `REDIS_URL` | Redis connection reference | No | Required by enterprise deployment | `.env`, compose, Render |
| `CELERY_BROKER_URL` | Celery broker URL | No | Required by Celery worker | `.env`, compose, Render |
| `CELERY_RESULT_BACKEND` | Celery result backend | No | Required for task results | `.env`, compose, Render |
| `GOOGLE_CLIENT_ID` | Gmail OAuth client ID | No | Required for Gmail OAuth | `.env`, deployment secret |
| `GOOGLE_CLIENT_SECRET` | Gmail OAuth client secret | No | Required for Gmail OAuth | `.env`, deployment secret |
| `GOOGLE_REDIRECT_URI` | Gmail OAuth callback URI | No | Required for OAuth registration match | `.env` |
| `OLLAMA_BASE_URL` | Intended local model endpoint | No | Not wired to an adapter | `.env.example` only |
| `OPENAI_COMPATIBLE_BASE_URL` | Intended OpenAI-compatible endpoint | No | Not wired to an adapter | `.env.example` only |
| `ENVIRONMENT` | Development/production mode | Optional | Set to production | `.env`, Render |
| `LOG_LEVEL` | Logging verbosity | Optional | Set in deployment | `.env`, Render |
| `MAX_AUTO_REPLIES_PER_HOUR` | Hourly send limit | Optional | Optional | `.env`, Render |
| `CONFIDENCE_THRESHOLD` | Classifier confidence threshold | Optional | Optional | `.env`, Render |
| `DEFAULT_AUTONOMY_MODE` | `approve`, `auto_safe`, or `auto_full` | Optional; default approve | Must remain explicitly reviewed | `.env`, Render |
| `DELAY_SEND_SECONDS` | Undo/delay window | Optional | Optional | `.env`, Render |
| `DASHBOARD_HOST` | Dashboard bind address | Keep `127.0.0.1` | Explicit address behind HTTPS proxy | `.env` |
| `DASHBOARD_PORT` | Dashboard port | Optional; default 8000 | Render separately supplies `$PORT` | `.env`, Render |
| `DASHBOARD_API_TOKEN` | Bearer token for dashboard | Required for dashboard API | Required | `.env`, Render secret |
| `DASHBOARD_USER_ID` | Single configured principal | Required for dashboard API | Required | `.env`, Render secret |
| `DASHBOARD_ALLOWED_ORIGINS` | Explicit CORS origins | Optional; empty is safest | Required if browser is cross-origin | `.env`, Render secret |
| `STORAGE_BACKEND` | `sqlite` or `supabase` | Set `sqlite` | Must set `supabase` | `.env`, compose/Render should set explicitly |
| `SQLITE_DB_PATH` | SQLite database file | Required for chosen path | Not used by Supabase | `.env` |
| `TASK_QUEUE_BACKEND` | `local` or `celery` | Set `local` | Must set `celery` | `.env`, compose/Render should set explicitly |
| `LOCAL_QUEUE_DB_PATH` | APScheduler SQLite job store | Required for local queue | Not used by Celery | `.env` |
| `PORT` | Render-provided web port | No | Required by Render runtime | Render platform, not `Settings` |
| `MAILAGENT_PORT` | Electron loopback port | Optional | No | `desktop/main.js` only |
| `MAILAGENT_PYTHON` | Electron Python executable override | Optional | No | `desktop/main.js` only |
| `MAILAGENT_USER_ID` | Electron local principal override | Optional | No | `desktop/main.js` only |
| `MAILAGENT_DESKTOP_DEBUG` | Electron backend stderr switch | Optional | No | `desktop/main.js` only |

### Configuration conflicts and unsafe/unwired settings

1. `render.yaml` supplies Supabase and Redis variables but does not set `STORAGE_BACKEND=supabase` or `TASK_QUEUE_BACKEND=celery`; application defaults therefore select SQLite/local queue.
2. The Dockerfile defaults to SQLite/local behavior, while `docker-compose.yml` overrides to Supabase/Celery. These are different operating modes and must not be conflated.
3. `OPENAI_API_KEY`, `GOOGLE_AI_API_KEY`, `OLLAMA_BASE_URL`, and `OPENAI_COMPATIBLE_BASE_URL` imply support that is not implemented in the provider registry.
4. `MODEL_CLASSIFICATION`, `MODEL_DRAFTING`, `MONTHLY_BUDGET_USD`, and `MAX_REPLIES_PER_THREAD_PER_DAY` appear in `.env.example`, but the settings class does not expose all of them.
5. The configured Supabase service-role client bypasses normal end-user RLS. The repository explicitly does not provide full multi-tenant identity/RBAC controls.
6. IMAP credentials use an `imap_server`/`imap_port` shape in code while older deployment examples show `host`/`port`; use the code's actual field names.
7. `render.yaml` was not accepted or deployed in this audit. Its Redis resource declaration requires validation against the current Render Blueprint schema.

## Exact setup commands

### Personal Windows installation

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set these values in `.env` without committing it:

```ini
STORAGE_BACKEND=sqlite
SQLITE_DB_PATH=mailagent.db
TASK_QUEUE_BACKEND=local
LOCAL_QUEUE_DB_PATH=mailagent-queue.db
DASHBOARD_API_TOKEN=<random-long-token>
DASHBOARD_USER_ID=<single-local-user-id>
DASHBOARD_HOST=127.0.0.1
```

Either set `MAILAGENT_ENCRYPTION_KEY` to a protected base64url-encoded 32-byte value, or allow Windows Credential Manager to create/store it. Do not copy the key into the database or logs.

Run:

```powershell
python -m uvicorn mailagent.dashboard.app:app --host 127.0.0.1 --port 8000
```

The Electron wrapper, after packaging prerequisites are fixed:

```powershell
Set-Location desktop
npm install
npm run build
```

### Enterprise staging setup

1. Create a disposable Supabase project and a Redis instance.
2. Apply SQL migrations in order: `001_initial_schema.sql`, `002_credential_encryption_contract.sql`, `003_provider_settings.sql`, `004_email_labels.sql`.
3. Verify the migration statements, RLS policies, service-role permissions, and a backup before any data test.
4. Set:

```ini
ENVIRONMENT=production
STORAGE_BACKEND=supabase
TASK_QUEUE_BACKEND=celery
SUPABASE_URL=<project-url>
SUPABASE_SERVICE_ROLE_KEY=<server-secret>
REDIS_URL=<redis-url>
CELERY_BROKER_URL=<redis-url>
CELERY_RESULT_BACKEND=<redis-url>
DASHBOARD_API_TOKEN=<server-secret>
DASHBOARD_USER_ID=<configured-principal>
MAILAGENT_ENCRYPTION_KEY=<protected-key-or-kms-injection>
```

5. Start the dashboard, worker, and beat as separate processes. Run only synthetic CRUD/task tests first.
6. Place the dashboard behind an HTTPS reverse proxy; do not expose the current service directly to multiple users.

### Gmail OAuth setup

1. Create a Google Cloud project and OAuth consent screen.
2. Register a web/desktop OAuth client.
3. Add the exact local or reverse-proxy callback URI from `GOOGLE_REDIRECT_URI`.
4. Request only the scopes required by the intended behavior. The current adapter requests Gmail readonly, modify, and send scopes; do not grant them to an unreviewed deployment.
5. Store the resulting authorized-user token only through the encrypted account credential path.
6. Perform a read-only list/fetch test before enabling any send operation.

### IMAP setup

Use an app password or equivalent provider credential and configure `email_address`, `password`, `imap_server`, `imap_port`, plus provider metadata. The current implementation supports read/sync and folder/flag operations but has no SMTP implementation.

## Tests and real results

| Command/check | Result |
|---|---|
| `python -m pytest -q` before fixes | 91 passed, 1 warning |
| Disposable SQLite CRUD/restart/isolation/export/deletion script | Passed; deletion removed all synthetic child records and preserved the second user |
| Disposable local queue with importable task | Passed; scheduled job persisted across restart |
| Nested local queue callable | Failed to schedule as expected by APScheduler serialization rules; logged a clear serialization error and returned `False` |
| Windows Credential Manager availability probe | Passed |
| SecretStore invalid key-length check | Passed; rejected non-256-bit key |
| Clean disposable dashboard startup probe before fix | `/` 200, authenticated `/api/status` 500 (`no such table: kill_switch`) |
| `python -m pytest -q tests/test_local_infrastructure.py tests/test_dashboard_auth.py tests/test_day12_hardening.py` after fixes | 25 passed, 5 deprecation warnings |
| Clean disposable dashboard startup probe after fix | `/` 200, authenticated `/api/status` 200, authenticated `/api/privacy` 200 |
| `python -m pytest -q` after fixes | 91 passed, 5 warnings |
| `python -m pytest -q` after Render fail-closed changes | 93 passed, 5 warnings |
| Supabase construction without URL | Correctly blocked: `SupabaseException: supabase_url is required` |
| IMAP connection to disposable unavailable endpoint | Failed safely; no connection made |
| SMTP placeholder behavior | Confirmed unimplemented; now raises `NotImplementedError` instead of returning success |
| Ollama probe at `127.0.0.1:11434` | No service reachable (`curl` timeout) |
| Electron dependency installation | Completed; npm reported 15 audit vulnerabilities (14 high, 1 critical) after adding the reproducible packager |
| `cd desktop; npm run build` | Blocked during `winCodeSign` extraction because symlink creation privilege is unavailable |
| `cd desktop; npm run build:portable` | Passed; produced a Windows x64 portable app directory and zipped archive without invoking `winCodeSign` |
| Extracted portable launch on Windows | Passed; GUI title, backend child process, root endpoint, authenticated `/api/status`, and authenticated `/api/privacy` verified |
| Portable restart/persistence | Passed; disposable kill-switch state was active after relaunch, then cleared before shutdown |
| Portable shutdown/network exposure | Passed; Electron, Python/Uvicorn, and loopback listeners exited after close; listeners were `127.0.0.1` only |
| Docker/Compose tooling | Docker and Compose installed; no live deployment was run |

## Confirmed bugs and minimal fixes

1. **Dashboard database initialization** — fixed in `mailagent/dashboard/app.py`. Added startup initialization and shutdown close hooks for the global database. This fixed the verified clean-start `/api/status` 500.
2. **False SMTP success** — fixed in `mailagent/providers/imap_provider.py`. `create_draft`, `send_reply`, and `delete_draft` now raise explicit `NotImplementedError` instead of returning placeholder IDs or `True`.
3. **Render enterprise fallback risk** — fixed in `render.yaml` and `mailagent/core/config.py`. Render now declares Redis correctly and sets Supabase/Celery explicitly; production settings reject personal backends and missing enterprise credentials.

No production settings, live databases, real email accounts, or real user data were changed.

## Remaining blockers ranked by severity

1. **Critical — enterprise data/security claims are unverified.** Supabase CRUD, migration application, RLS behavior, backups, retention deletion, identity integration, RBAC, and tenant isolation were not physically tested.
2. **High — live enterprise credentials/services are unavailable.** Supabase/PostgreSQL and Redis/Celery were not physically tested.
3. **High — outbound sending is incomplete for IMAP.** SMTP is not implemented; Gmail send exists in code but was not OAuth-verified.
4. **High — desktop artifact is not packaged.** Windows symlink privilege blocked `electron-builder`.
5. **Medium — cloud AI is unavailable.** No Claude credential was configured; OpenAI/Google adapters are absent; Ollama is not wired.
6. **Medium — local queue callable contract is narrow.** Persisted jobs must be importable module-level callables; immediate Windows queue-file cleanup can retain a file lock.
7. **Low — configuration drift.** Several `.env.example` variables are unused or placeholders, and lifecycle hooks emit FastAPI deprecation warnings.

## Prioritized checklist for a fully working personal installation

- [ ] Install `requirements.txt` in the intended Python environment.
- [ ] Create `.env` with SQLite/local queue settings and loopback dashboard binding.
- [ ] Configure `DASHBOARD_API_TOKEN` and `DASHBOARD_USER_ID`.
- [ ] Confirm Windows Credential Manager or provide a protected `MAILAGENT_ENCRYPTION_KEY`.
- [ ] Start the dashboard and verify `/`, authenticated `/api/status`, and `/api/privacy`.
- [ ] Add one disposable or read-only Gmail/IMAP account; verify provider credentials and synchronization.
- [ ] Run synthetic CRUD, export, deletion, restart, and queue recovery checks.
- [ ] Configure Claude only if cloud inference is explicitly approved; otherwise keep AI unconfigured.
- [ ] Keep autonomy mode `approve` until provider reads and policy behavior are verified.
- [x] Produce the no-symlink Windows portable artifact; test it in a controlled Windows environment before distribution.
- [ ] Enable Electron packaging prerequisites (Developer Mode or approved symlink privilege) only if a signed electron-builder installer is required.
- [ ] Back up the SQLite file and encryption key separately; test restore before storing valuable data.

## Separate enterprise-readiness checklist

- [ ] Correct and validate the Render Blueprint, including an actual Redis resource and explicit backend selectors.
- [ ] Apply migrations 001→004 to a disposable Supabase project and verify schema/query compatibility.
- [ ] Validate RLS with authenticated users and service-role workers; remove reliance on a single shared principal.
- [ ] Implement and test tenant isolation, identity-provider login, RBAC, administrator workflows, retention, and PostgreSQL deletion.
- [ ] Configure and rotate encryption keys through a KMS/secrets manager with a tested recovery procedure.
- [ ] Run Redis/Celery worker and beat smoke tests, retry tests, cancellation, duplicate-send prevention, undo windows, and kill-switch tests using synthetic tasks.
- [ ] Register Gmail OAuth with reviewed scopes and exact HTTPS redirect URIs.
- [ ] Implement and test SMTP for non-Gmail providers before enabling outbound sends.
- [ ] Implement/register only the AI adapters that are actually supported; verify timeouts, error propagation, response schemas, and log redaction.
- [ ] Place the dashboard behind a controlled HTTPS reverse proxy with secure headers and audited origins.
- [ ] Complete backup/restore, monitoring, alerting, incident response, and network-egress validation in staging.
- [ ] Do not claim full enterprise security until all items above are independently verified.
