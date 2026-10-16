# MailAgent Usage Guide

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd mailagent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```bash
# Claude API
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Application
DEFAULT_AUTONOMY_MODE=approve
CONFIDENCE_THRESHOLD=0.85
MAX_AUTO_REPLIES_PER_HOUR=10
```

### 3. Database Setup

Run the Supabase migration:
1. Go to your Supabase project dashboard
2. Navigate to SQL Editor
3. Copy the contents of `mailagent/supabase/migrations/001_initial_schema.sql`
4. Run the script

### 4. Start Redis

```bash
# If using local Redis
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis:latest
```

### 5. Start Celery Worker

```bash
# Terminal 1: Start the worker
celery -A mailagent.worker worker --loglevel=info

# Terminal 2: Start the beat scheduler
celery -A mailagent.worker beat --loglevel=info
```

### 6. Start the Dashboard

```bash
python -m mailagent.dashboard.app
```

The dashboard will be available at `http://localhost:8000`

## Adding Email Accounts

### Gmail Account

1. Create a Google Cloud project
2. Enable Gmail API
3. Create OAuth 2.0 credentials
4. Add the following to your `.env`:
   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback
   ```

5. Use the OAuth flow to get tokens:
   ```python
   from mailagent.providers.gmail_provider import GmailOAuthFlow

   # Get authorization URL
   auth_url = GmailOAuthFlow.get_authorization_url()
   print(f"Visit: {auth_url}")

   # After user authorizes, exchange code for token
   token = GmailOAuthFlow.exchange_code_for_tken(code)
   ```

6. Add account via API:
   ```bash
   curl -X POST http://localhost:8000/api/accounts \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "user_123",
       "provider": "gmail",
       "email_address": "your@gmail.com",
       "credentials": {"token": {...}}
     }'
   ```

### IMAP Account (Yahoo, Generic)

```bash
curl -X POST http://localhost:8000/api/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "provider": "imap",
    "email_address": "your@yahoo.com",
    "credentials": {
      "email_address": "your@yahoo.com",
      "password": "your_app_password",
      "imap_server": "imap.mail.yahoo.com",
      "imap_port": 993,
      "smtp_server": "smtp.mail.yahoo.com",
      "smtp_port": 587
    }
  }'
```

## Running the Agent

### Manual Processing

```bash
python main.py
```

### Scheduled Processing

The Celery beat scheduler will automatically process emails every 5 minutes.

## Autonomy Modes

### Approve Mode (Default)
- Agent drafts all replies
- Human must approve every send
- Safest mode

### Auto Safe Mode
- Agent sends routine replies automatically
- Non-routine replies require approval
- Good balance of automation and safety

### Auto Full Mode
- Agent sends all replies that pass policy
- User is warned after each send
- Requires explicit opt-in
- Maximum automation

Change mode via dashboard:
```bash
curl -X POST http://localhost:8000/api/autonomy-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "auto_safe"}'
```

## Kill Switch

Activate the kill switch to stop all processing:
```bash
curl -X POST http://localhost:8000/api/kill-switch \
  -H "Content-Type: application/json" \
  -d '{
    "activate": true,
    "reason": "Emergency stop",
    "activated_by": "admin"
  }'
```

Deactivate:
```bash
curl -X POST http://localhost:8000/api/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"activate": false}'
```

## Approving Drafts

View pending drafts:
```bash
curl http://localhost:8000/api/drafts?account_id=account_123
```

Approve a draft:
```bash
curl -X POST http://localhost:8000/api/drafts/approve \
  -H "Content-Type: application/json" \
  -d '{
    "draft_id": "draft_123",
    "approve": true
  }'
```

Reject a draft:
```bash
curl -X POST http://localhost:8000/api/drafts/approve \
  -H "Content-Type: application/json" \
  -d '{
    "draft_id": "draft_123",
    "approve": false
  }'
```

## Viewing Audit Logs

```bash
# Get audit log for a specific email
curl http://localhost:8000/api/audit-log?email_id=email_123

# Get recent audit log entries
curl http://localhost:8000/api/audit-log?limit=100
```

## Monitoring

Check system status:
```bash
curl http://localhost:8000/api/status
```

View statistics:
```bash
curl http://localhost:8000/api/stats?account_id=account_123
```

## Testing

Run acceptance tests:
```bash
pytest tests/test_acceptance.py -v
```

Run unit tests:
```bash
pytest tests/ -v
```

## Troubleshooting

### Claude API Errors
- Check your API key is valid
- Ensure you have sufficient credits
- Verify the API endpoint is accessible

### IMAP Connection Errors
- Verify credentials are correct
- Check IMAP server and port
- Ensure app passwords are used (not regular passwords)
- Check firewall settings

### Celery Worker Not Processing
- Check Redis is running
- Verify Celery broker URL is correct
- Check worker logs for errors
- Ensure tasks are being scheduled

### Dashboard Not Loading
- Check the port is not in use
- Verify environment variables are set
- Check for Python errors in logs

## Best Practices

1. **Start with Approve Mode**: Always start in approve mode to review drafts before enabling auto-send
2. **Monitor Audit Logs**: Regularly review audit logs to ensure the agent is making correct decisions
3. **Test with Sample Emails**: Use the acceptance test suite to verify classification accuracy
4. **Update Voice Profile**: Periodically retrain the voice profile as your writing style evolves
5. **Use Kill Switch**: Keep the kill switch handy for emergencies
6. **Review Sensitive Emails**: Always review emails flagged as sensitive before sending
7. **Monitor Rate Limits**: Keep an eye on rate limits to avoid hitting provider limits

## Security Considerations

1. **Never Commit Secrets**: Never commit `.env` or API keys to version control
2. **Use Service Role Keys**: Use Supabase service role keys only in trusted environments
3. **Rotate Credentials**: Regularly rotate API keys and passwords
4. **Limit Permissions**: Use minimum required permissions for OAuth scopes
5. **Audit Access**: Regularly audit who has access to the dashboard
6. **Enable SSL**: Always use SSL/TLS in production
7. **Monitor for Abuse**: Monitor for unusual activity that could indicate abuse
