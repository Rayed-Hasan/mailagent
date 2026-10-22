# Mail Agent — Privacy-First AI Email Management

**Your inbox. Your AI. Your machine. Your rules.**

Mail Agent is an open-source, privacy-first AI email agent that individuals, professionals, businesses, and enterprises can download, install, configure, and operate on infrastructure they control. No mandatory Mail Agent accounts, no centralized backend, no telemetry—just powerful AI assistance running on your own infrastructure.

## Privacy by Architecture

- **No mandatory accounts**: Run entirely on your own infrastructure without a Mail Agent account system
- **No central backend**: All email data, classifications, and agent memory stored locally or on your own infrastructure
- **No telemetry**: No analytics or usage data sent to Mail Agent servers
- **BYOK encryption**: Email OAuth tokens, AI keys, and encryption keys protected using OS credential storage or secure server-side secret management
- **Network transparency**: All external connections are documented and optional telemetry is disabled by default

## Features

### Core Capabilities
- **BYOK/BYOG providers**: Claude, GPT, Gemini, OpenAI-compatible endpoints, and local Ollama models
- **Zero-token deterministic prefilter**: Instant classification of newsletters and bulk mail without AI inference
- **Normalized provider interfaces**: Switch between Gmail, Microsoft Graph, and IMAP/SMTP without changing agent logic
- **Priority classification**: Intelligent categorization with confidence scores and priority ranking
- **Voice-aware drafting**: Learns your writing style from sent emails for authentic responses

### Safety & Autonomy
- **Hard-coded send safety rules**: Deterministic policy checks before any email is sent
- **Three autonomy modes**: Approve (safest), Auto-safe (routine only), Auto-full (opt-in)
- **60-second cancelable send window**: Delayed sending with one-click undo
- **Rate limiting**: Prevents reply loops and volume spikes
- **Emergency kill switch**: Instantly stops all autonomous operations
- **Full audit trail**: Every decision logged with reason and context

### Enterprise deployment path
- **Account isolation**: Server-side ownership checks for the configured dashboard principal
- **Administrative controls**: Kill switch, provider settings, and audit endpoints
- **Configurable storage**: Local persistence or company-controlled database
- **Deployment flexibility**: Personal desktop or self-hosted enterprise deployment

## Architecture

### Current Implementation
- **Language**: Python with FastAPI control plane
- **Storage**: Local SQLite by default; Supabase/PostgreSQL remains supported
- **Queue**: Persistent local APScheduler queue by default; Celery/Redis remains supported
- **Email providers**: Gmail OAuth2, Microsoft Graph, generic IMAP/SMTP adapters
- **Security**: AES-256-GCM encryption for all credentials

### Privacy-First Roadmap
Personal installations use SQLite and a persistent local scheduler without a Mail
Agent-hosted service, Supabase, or Redis. Email synchronization still requires
the configured provider, and cloud inference still requires the user's explicitly
configured key. Enterprise installations can select Supabase/PostgreSQL and
Celery/Redis on company-controlled infrastructure.

Credentials are encrypted with AES-GCM. The encryption key is read from
`MAILAGENT_ENCRYPTION_KEY`, or generated and retained in the OS keychain when
that variable is absent. If neither secure option is available, startup fails;
the application never stores plaintext credentials or silently weakens protection.

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture and data flow.

## Setup

### Personal Installation (Local-First)

For personal use without any cloud dependencies:

```bash
pip install -r requirements.txt
cp .env.example .env
```

Configure `.env` for local-first operation:

```bash
# Encryption key (generate with: openssl rand -base64 32)
MAILAGENT_ENCRYPTION_KEY=your_32_byte_base64_key

# AI provider (choose one or more, or use local Ollama)
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
GOOGLE_AI_API_KEY=your_google_key

# Use local SQLite database (no cloud dependency)
STORAGE_BACKEND=sqlite
SQLITE_DB_PATH=mailagent.db

# Use local task queue (no Redis dependency)
TASK_QUEUE_BACKEND=local

# Gmail OAuth (for Gmail accounts, optional if using IMAP)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback
```

Start the application:

```bash
python main.py
```

### Enterprise Installation (Supabase + Redis)

For enterprise deployments with centralized database:

```bash
pip install -r requirements-enterprise.txt
cp .env.example .env
```

Configure `.env` for enterprise operation:

```bash
# Encryption key
MAILAGENT_ENCRYPTION_KEY=your_32_byte_base64_key

# AI provider (BYOK)
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
GOOGLE_AI_API_KEY=your_google_key

# Supabase (enterprise database)
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

# Redis (for Celery task queue)
REDIS_URL=redis://localhost:6379/0

# Use Supabase storage backend
STORAGE_BACKEND=supabase

# Use Celery task queue
TASK_QUEUE_BACKEND=celery
```

Start services:

```bash
docker compose up --build
```

## Testing

```bash
pytest -q
```

The suite contains 73 tests covering the baseline safety behavior and the Days
6–8 local infrastructure. Run:
- Foundation and safety systems
- Provider adapter contracts
- Send flow and autonomy modes
- Rate limiting and kill switch
- Worth-sending policy enforcement

## Deployment Modes

### Personal Desktop
- Single-machine installation
- Local SQLite or PostgreSQL database
- OS keychain for the encryption key where available, with an explicit
  `MAILAGENT_ENCRYPTION_KEY` alternative
- No external dependencies beyond email providers

### Enterprise Self-Hosted (Partially implemented)
- Multi-user deployment on company infrastructure
- Centralized PostgreSQL database
- Company secret management system
- Administrative policies and audit logs
- The current dashboard supports one configured principal (`DASHBOARD_USER_ID`)
  with server-side ownership checks. Multi-tenant identity, roles, delegated
  administration, and PostgreSQL retention deletion are not complete and must
  be added before calling a deployment enterprise-ready.

## Philosophy

Mail Agent is built on these principles:

1. **Privacy by architecture**: No data sent to Mail Agent infrastructure unless explicitly configured
2. **Personal intelligence**: Learn user preferences locally with transparent, controllable memory
3. **Enterprise control**: Support company-controlled infrastructure and policies
4. **Provider freedom**: Support local models and user-owned AI API keys
5. **Safe autonomy**: Clear autonomy levels, human approval, undo where possible, auditable decisions
6. **Local-first operation**: Run without Mail Agent cloud services
7. **Storage abstraction**: Separate application logic from persistence
8. **Network transparency**: Document all external connections

## Current Status

**Completed (Days 1-4):**
- ✅ Foundation and security infrastructure
- ✅ Provider abstraction and BYOK encryption
- ✅ Email pre-filtering, classification, and labeling
- ✅ Priority inbox frontend/backend

**Day 5:**
- ✅ Worth-sending policy engine
- ✅ Approval modes and autonomy controls
- ✅ Safe send flow with validation
- ✅ Undo window with persistent queue state
- ✅ Idempotency controls for duplicate prevention
- ✅ Enhanced kill switch with queued message handling
- ✅ Comprehensive test coverage (73 tests passing)

**Days 6–8:**
- ✅ Storage abstraction and SQLite personal backend
- ✅ OS keychain integration with secure failure behavior
- ✅ Persistent local queue; Celery/Redis remains configurable for enterprise
- ✅ SQLite, credential isolation, queue cancellation/recovery, and safety tests

**Days 9–11:**
- ✅ Windows-first Electron wrapper with loopback-only backend startup
- ✅ First-run privacy/onboarding disclosure and restricted frontend asset serving
- ✅ Local export and deletion controls
- ⚠️ Enterprise path is self-hosted but not yet multi-tenant/RBAC complete

**Remaining Work:**
- 🔄 macOS/Linux desktop packaging
- 🔄 Admin console for enterprise

## Contributing

Mail Agent is open-source. We welcome contributions that:
- Preserve privacy-first architecture
- Support local-first operation
- Enhance security and safety
- Improve provider compatibility
- Add enterprise features

## License

[Your License Here]

## Acknowledgments

Built with:
- FastAPI for the control plane
- Supabase for database (default, replaceable)
- Celery for background tasks
- Cryptography library for credential encryption
- Various email provider APIs
