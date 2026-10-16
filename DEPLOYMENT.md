# Deployment Guide for MailAgent

## Prerequisites

- Render account
- Supabase account
- Claude API key
- Redis instance (can use Redis Cloud or Render Redis)

## Step 1: Set up Supabase

1. Create a new Supabase project
2. Run the migration script:
   ```bash
   # In Supabase dashboard > SQL Editor
   # Copy and paste the contents of mailagent/supabase/migrations/001_initial_schema.sql
   # Run the script
   ```
3. Get your Supabase URL and service role key from Settings > API

## Step 2: Set up Redis

Option A: Use Render Redis
1. In Render dashboard, create a new Redis instance
2. Copy the Redis URL

Option B: Use Redis Cloud
1. Sign up at Redis Cloud
2. Create a free database
3. Copy the connection URL

## Step 3: Prepare for Deployment

1. Create a `render.yaml` file in the project root:
```yaml
services:
  - type: worker
    name: mailagent-worker
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A mailagent.worker worker --loglevel=info --concurrency=2
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: REDIS_URL
        fromService:
          type: redis
          name: mailagent-redis
          property: connectionString
      - key: CELERY_BROKER_URL
        fromService:
          type: redis
          name: mailagent-redis
          property: connectionString
      - key: CELERY_RESULT_BACKEND
        fromService:
          type: redis
          name: mailagent-redis
          property: connectionString
      - key: ENVIRONMENT
        value: production
      - key: LOG_LEVEL
        value: INFO
      - key: MAX_AUTO_REPLIES_PER_HOUR
        value: 10
      - key: CONFIDENCE_THRESHOLD
        value: 0.85
      - key: DEFAULT_AUTONOMY_MODE
        value: approve
      - key: DELAY_SEND_SECONDS
        value: 60

  - type: web
    name: mailagent-dashboard
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn mailagent.dashboard.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: REDIS_URL
        fromService:
          type: redis
          name: mailagent-redis
          property: connectionString
      - key: CELERY_BROKER_URL
        fromService:
          type: redis
          name: mailagent-redis
          property: connectionString
      - key: CELERY_RESULT_BACKEND
        fromService:
          type: redis
          name: mailagent-redis
          property: connectionString
      - key: ENVIRONMENT
        value: production
      - key: DASHBOARD_PORT
        value: 10000

  - type: pserv
    name: mailagent-beat
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A mailagent.worker beat --loglevel=info
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: REDIS_URL
        fromService:
          type: redis
          name: mailagent-redis
          property: connectionString
      - key: CELERY_BROKER_URL
        fromService:
          type: redis
          name: mailagent-redis
          property: connectionString
      - key: CELERY_RESULT_BACKEND
        fromService:
          type: redis
          name: mailagent-redis
          property: connectionString
      - key: ENVIRONMENT
        value: production

databases:
  - name: mailagent-redis
    databaseName: mailagent
    user: mailagent
```

## Step 4: Deploy to Render

1. Push your code to GitHub
2. In Render dashboard, click "New +"
3. Select "Existing repository"
4. Connect your GitHub repository
5. Render will detect the `render.yaml` file and create all services
6. Add environment variables:
   - ANTHROPIC_API_KEY
   - SUPABASE_URL
   - SUPABASE_SERVICE_ROLE_KEY
   - GOOGLE_CLIENT_ID (for Gmail OAuth)
   - GOOGLE_CLIENT_SECRET (for Gmail OAuth)

## Step 5: Verify Deployment

1. Check the worker logs to ensure it's processing emails
2. Access the dashboard at the provided URL
3. Test the kill switch via the dashboard API
4. Monitor Celery tasks in the dashboard

## Step 6: Set up Email Accounts

You'll need to create email accounts in the database via the dashboard or API:

```bash
# Example API call to add a Gmail account
curl -X POST https://your-dashboard-url/api/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your_user_id",
    "provider": "gmail",
    "email_address": "your@gmail.com",
    "credentials": {
      "token": {
        "token": "access_token",
        "refresh_token": "refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "your_client_id",
        "client_secret": "your_client_secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.send"]
      }
    }
  }'
```

## Monitoring

- Monitor the dashboard for status
- Check worker logs in Render
- Monitor Redis memory usage
- Set up alerts for errors in Celery tasks

## Scaling

- Increase worker concurrency for higher throughput
- Add more worker instances for multiple accounts
- Scale Redis for higher task volume
