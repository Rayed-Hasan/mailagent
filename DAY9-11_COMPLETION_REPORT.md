# Days 9–11 completion report

## Delivered

- **Desktop:** Windows 10/11 Electron wrapper in [`desktop/`](desktop/).
  It starts the existing FastAPI application, binds it to `127.0.0.1`, creates
  an ephemeral bearer token, loads the existing frontend, and terminates the
  backend on exit. It does not rewrite the inbox workflow.
- **Onboarding:** The existing UI now presents a first-run disclosure for
  deployment mode, local versus BYOK AI, autonomy preference, and external
  provider data flow. Only non-secret preferences are stored in browser
  `localStorage`; secrets are never collected by this form. These are onboarding
  preferences for the current UI; the server's existing autonomy configuration
  remains the source of truth for send behavior.
- **Local privacy controls:** Authenticated `/api/privacy` describes actual
  network/data behavior. `/api/privacy/export` exports user-owned local data
  without credentials. `DELETE /api/privacy/data` deletes related SQLite
  records transactionally, including classifications, labels, drafts, emails,
  accounts, provider settings, and voice profile.
- **Local API security:** The default bind address is loopback. Frontend
  serving is restricted to three known assets rather than exposing the
  repository. Existing bearer authentication and server-side account-owner
  checks remain in force.
- **Deployment:** Docker/Render enterprise definitions now install the
  enterprise dependency set and explicitly select Supabase/Celery. Personal
  mode remains SQLite/local queue.

## Supported platform and installation

The working desktop target is Windows 10/11:

```powershell
cd desktop
npm install
npm start
```

Use `MAILAGENT_PYTHON` if Python is not on PATH. `npm run build` creates a
portable Windows package. macOS/Linux packaging is not claimed yet; those
platforms can use the existing Python/FastAPI local-first installation.

## Verified personal-mode dependencies

Personal mode requires Python dependencies from `requirements.txt`, SQLite,
the OS keychain or an explicit `MAILAGENT_ENCRYPTION_KEY`, and the configured
email provider. It does not require Supabase, Redis, Celery, a hosted account,
or Mail Agent infrastructure. Electron packaging additionally requires Node.js
and npm. Cloud AI is optional; if selected, the user's configured provider
receives the relevant inference request.

## Enterprise status and security gaps

The company-controlled Supabase/PostgreSQL and Celery/Redis deployment path is
documented and preserved. The current dashboard is a **single configured
principal** using `DASHBOARD_API_TOKEN` and `DASHBOARD_USER_ID`, with server-side
resource ownership checks. It is not a complete multi-tenant enterprise
deployment: an identity provider, tenant model, role-based permissions,
administrator workflow, and PostgreSQL retention deletion are still blockers.
The documentation intentionally does not call it enterprise-ready.

## Privacy and network findings

No telemetry, crash reporting, or Mail Agent-hosted destination was added.
The frontend no longer loads Google Fonts. External destinations are limited
to the configured Gmail/IMAP provider and explicitly selected AI provider;
OAuth and Anthropic endpoints remain external by necessity. The local desktop
wrapper communicates with its backend over loopback HTTP and uses an ephemeral
token. This is not an offline claim: email sync and cloud inference need
network access.

## Exact validation

- `python -m pytest -q` — **73 passed** with the existing deprecation warnings.
- `python -m pytest -q tests/test_local_infrastructure.py tests/test_dashboard_auth.py tests/test_day4_priority_inbox.py` — **11 passed**.
- `python -m compileall -q mailagent tests` — passed.
- `node --check desktop\main.js` — passed.
- `git diff --check` — passed.
- Route inspection confirmed `/app/{asset}`, `/api/privacy`,
  `/api/privacy/export`, and `/api/privacy/data`.

## Remaining blockers

- Electron dependencies were not installed or packaged in this environment.
- macOS/Linux desktop installers are not implemented.
- Enterprise multi-user identity/RBAC/tenant administration is incomplete.
- Supabase live integration and HTTPS reverse-proxy deployment were not
  exercised against external infrastructure.
