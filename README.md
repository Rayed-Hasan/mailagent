# MailAgent v2 — BYOG AI

An autonomous inbox agent where every user brings their own model key. MailAgent
connects to a mailbox, sorts the inbox, drafts only worthwhile replies, and
keeps a human in control by default.

## Features

- BYOK/BYOG providers: Claude, GPT, Gemini, OpenAI-compatible endpoints, and Ollama
- Zero-token deterministic prefilter for newsletters and bulk mail
- Normalized LLM and mailbox interfaces so providers do not change agent logic
- Priority classification, voice-aware drafting, and hard-coded send safety rules
- Approve, auto-safe, and explicit auto-full autonomy modes
- 60-second cancelable send window, rate limits, kill switch, and audit feed
- Encrypted BYOK credentials with AES-256-GCM; keys never go to the browser or logs
- Three-panel inbox UI with usage meter, live activity reasons, and command palette

## Architecture

- Python worker and FastAPI control plane
- Frontend demo shell, ready for a Next.js/Vercel split
- Supabase PostgreSQL with row-level security
- Celery + Redis queue
- Gmail OAuth2, Microsoft Graph, and generic IMAP/SMTP adapter seams
- Render worker/dashboard deployment and Vercel frontend deployment

See [ARCHITECTURE.md](ARCHITECTURE.md) for the v2 folder structure and data flow.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Set `MAILAGENT_ENCRYPTION_KEY` from an environment/KMS secret. Do not place
provider keys in source control. Start local services with:

```bash
docker compose up --build
```

The static demo is available by opening `index.html` directly.

## Testing

```bash
pytest -q
```

The foundation and safety suite is green. Production acceptance still needs
disposable Gmail, Yahoo/IMAP, Claude, GPT, and Ollama fixtures before enabling
auto modes.

## 14-day build plan

1. Days 1–2: provider contracts, Supabase schema, IMAP/SMTP and Gmail OAuth
2. Day 3: worker queue, content-hash cache, audit log, retry/backoff
3. Day 4: BYOK settings, adapters, model slots, JSON fallback
4. Days 5–6: prefilter, three-filter classifier, labels, inbox UI
5. Days 7–8: voice matching from 50 sent sentences and send-worthiness policy
6. Days 9–10: draft/send queue, 60-second cancelable kill switch, undo
7. Days 11–12: autonomy modes, activity feed, teach loop, usage budget
8. Day 13: follow-ups, unsubscribe, digest, calendar detection, agent chat
9. Day 14: responsive polish, onboarding, demo fixtures, provider test pass

The order is intentional: safety and provider seams precede automation.
