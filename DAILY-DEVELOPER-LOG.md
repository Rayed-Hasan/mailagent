# Daily Developer Log

**Date:** 2026-10-16
**Project:** MailAgent v2 — BYOG AI

## What we did

- Built the MailAgent inbox dashboard and morning-of-mail experience.
- Added the virtual agent identity, “Everything, sorted” inbox, priority review, reply/review/read-later filters, activity feed, usage meter, approve-mode indicator, and command palette.
- Added the BYOG/BYOK LLM interface with normalized responses, tool-call fields, JSON response support, token counts, model metadata, and fallback tracking.
- Added two model slots: a cheaper classification model and a stronger drafting model.
- Added a provider registry with role validation.
- Added the normalized mail provider interface:
  - `list_new`
  - `get_thread`
  - `send`
  - `label`
  - `archive`
  - `smooth`
- Added AES-GCM encrypted secret storage with environment/KMS key support and last-four-character redaction.
- Added deterministic zero-token prefiltering for newsletters, bulk mail, and no-reply senders.
- Added prompt-injection detection and untrusted-email wrapping.
- Added an offline classification fallback when a BYOK provider is unavailable.
- Kept hard safety rules, approval mode, rate limits, delayed sending, and audit-oriented activity visible.
- Added Docker and Docker Compose setup for dashboard, worker, and Redis.
- Added BYOG environment variables and updated architecture and setup documentation.
- Fixed package initialization so optional database and network dependencies are not required for lightweight unit tests.
- Added and updated tests for prefiltering, prompt safety, encrypted secrets, provider slots, token counting, and async send flow.

## What we used

- Python 3.13
- Pydantic and Pydantic Settings
- Cryptography AES-GCM
- HTTPX
- Pytest
- Pytest Asyncio
- FastAPI/Uvicorn project structure
- Celery and Redis project structure
- Supabase/PostgreSQL project structure
- Gmail OAuth and IMAP/SMTP provider areas
- HTML, CSS, and JavaScript for the demo frontend
- Docker and Docker Compose
- Git and GitHub

## Validation

- 28 tests passed.
- Browser validation passed for inbox filters, approve-mode messaging, activity feed rendering, and `Ctrl+K`/`Cmd+K` command palette behavior.
- No diagnostics were reported in the changed Python, JavaScript, or CSS files.
