# Public Demo Mode Setup Guide

This guide explains how to deploy Mail Agent in public demo mode for hackathon evaluation.

## Overview

Public demo mode allows judges to evaluate Mail Agent without:
- Downloading anything
- Signing up or logging in
- Connecting a real mailbox
- Entering API keys

The demo uses:
- Synthetic email data (pre-seeded realistic inbox)
- OpenRouter with free models (or deterministic fallback)
- Separate SQLite database for isolation
- Rate limiting and security controls

## Local Deployment

### Using Docker Compose (Recommended)

1. Build and start the demo:
```bash
docker-compose -f docker-compose.demo.yml up
```

2. The demo will be available at `http://localhost:8000`

3. To stop:
```bash
docker-compose -f docker-compose.demo.yml down
```

### Using Python Directly

1. Set environment variables:
```bash
export PUBLIC_DEMO_MODE=true
export OPENROUTER_API_KEY=your_openrouter_key  # Optional
export DEMO_RATE_LIMIT_PER_MINUTE=30
export DEMO_MAX_CONCURRENT_REQUESTS=5
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start the server:
```bash
uvicorn mailagent.dashboard.app:app --host 0.0.0.0 --port 8000
```

## Render Deployment

### Deploying to Render

1. Create a new web service on Render
2. Connect your GitHub repository
3. Use `render-demo.yaml` as the deployment configuration
4. Set environment variables:
   - `PUBLIC_DEMO_MODE=true`
   - `OPENROUTER_API_KEY` (optional - for real AI)
   - `OPENROUTER_MODEL=google/gemma-4-26b-a4b-it:free`
5. Deploy

The demo will be available at the Render-provided URL.

## Environment Variables

### Required for Demo Mode

- `PUBLIC_DEMO_MODE=true` - Enables public demo mode
- `STORAGE_BACKEND=sqlite` - Uses SQLite (default)
- `TASK_QUEUE_BACKEND=local` - Uses local queue (default)

### Optional for Demo Mode

- `OPENROUTER_API_KEY` - OpenRouter API key for real AI inference
- `OPENROUTER_MODEL` - OpenRouter model (default: `google/gemma-4-26b-a4b-it:free`)
- `DEMO_RATE_LIMIT_PER_MINUTE` - Max requests per minute per IP (default: 30)
- `DEMO_MAX_CONCURRENT_REQUESTS` - Max concurrent requests per IP (default: 5)
- `DEMO_RESET_ENDPOINT_ENABLED` - Enable reset endpoint (default: true)
- `DEMO_SQLITE_DB_PATH` - Path to demo database (default: `mailagent-demo.db`)

### Not Used in Demo Mode

The following are not required in demo mode:
- `DASHBOARD_API_TOKEN` - Authentication is bypassed
- `DASHBOARD_USER_ID` - Uses demo user ID
- `SUPABASE_URL` - Uses SQLite instead
- `REDIS_URL` - Uses local queue instead
- `ANTHROPIC_API_KEY` - Uses OpenRouter or fallback

## Demo Data

The demo includes 12 synthetic emails with:
- Urgent production incidents
- Legal document reviews
- Marketing approvals
- Security alerts
- Payment confirmations
- Shipping notifications
- Newsletters
- Personal networking
- HR deadlines
- Promotional content
- IT maintenance notices
- Invoices

Each email includes:
- Realistic sender and subject
- Believable body content
- Pre-computed classification
- Priority score (0-100)
- Category (urgent, meets_reply, sensitive, FYI, newsletter, promo)
- Suggested action (reply, archive, draft_only)
- Labels (Security, Production, High Priority, etc.)

## Security Features

- **Storage Isolation**: Demo uses separate `mailagent-demo.db` database
- **No Real Credentials**: Demo account has no real email provider credentials
- **Rate Limiting**: 30 requests/minute per IP, 5 concurrent requests
- **No External Mail**: Real email sync is disabled
- **Simulated Actions**: Draft approval and sending are simulated
- **Clear Disclaimers**: UI and API responses clearly indicate demo mode

## AI Inference

### With OpenRouter (Real AI)

If `OPENROUTER_API_KEY` is set:
- Uses OpenRouter with configured free model
- Real AI classification and draft generation
- Falls back gracefully on errors

### Without OpenRouter (Fallback)

If no API key:
- Uses deterministic fallback responses
- Classification based on input hash
- Draft generation uses templates
- Clearly labeled as fallback

## Judge Workflow

1. **Open Demo URL** - No login required
2. **View Priority Inbox** - 12 pre-classified emails
3. **Filter and Search** - By priority, category, label, reply status
4. **Inspect Email** - View classification, labels, priority score
5. **Generate Draft** - AI-powered contextual reply
6. **Edit Draft** - Modify before approval
7. **Approve Draft** - Simulated send with disclaimer
8. **Reset Demo** - Restore original state

## Testing the Demo

### Manual Testing

1. Start the demo server
2. Open browser to `http://localhost:8000`
3. Verify:
   - No login prompt
   - Demo inbox loads with 12 emails
   - Filters work correctly
   - Email detail view shows classification
   - Draft generation works (AI or fallback)
   - Reset endpoint restores data

### Automated Testing

Run the demo mode security tests:
```bash
pytest tests/test_demo_mode.py -v
```

## Troubleshooting

### Demo endpoint returns 403
- Check `PUBLIC_DEMO_MODE=true` is set
- Verify environment variables are loaded

### No emails appear
- Check demo database was seeded on startup
- Review logs for seeding errors
- Try `/api/demo/reset` endpoint

### AI inference fails
- Check `OPENROUTER_API_KEY` is valid
- Verify selected model is available
- Fallback should activate automatically

### Rate limit errors
- Reduce `DEMO_RATE_LIMIT_PER_MINUTE`
- Wait 1 minute before retrying
- Check for bot/scanner traffic

## Production Considerations

**Demo mode is for hackathon evaluation only.**

For production use:
- Set `PUBLIC_DEMO_MODE=false`
- Configure proper authentication
- Use Supabase for persistence
- Configure real email providers
- Set up Redis for task queue
- Use Claude or enterprise AI providers
- Implement proper RBAC and multi-tenant isolation
