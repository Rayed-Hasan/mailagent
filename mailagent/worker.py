"""
Celery worker for scheduled email processing
"""

from celery import Celery
from datetime import datetime
import asyncio

from mailagent.core.config import settings
from mailagent.core.agent import EmailAgent
from mailagent.core.database import Database


# Initialize Celery
celery_app = Celery(
    'mailagent',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)


@celery_app.task(bind=True)
def process_account_task(self, user_id: str, account_id: str):
    """
    Process all new emails for an account.
    This task runs every 1-5 minutes or on push.
    """
    print(f"Processing account {account_id} for user {user_id} at {datetime.utcnow()}")

    # Run async task in event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        agent = EmailAgent(user_id)
        loop.run_until_complete(agent.initialize())
        loop.run_until_complete(agent.process_account(account_id))
        loop.run_until_complete(agent.shutdown())

        return {"status": "success", "account_id": account_id}
    except Exception as e:
        print(f"Error processing account {account_id}: {e}")
        return {"status": "error", "account_id": account_id, "error": str(e)}
    finally:
        loop.close()


@celery_app.task(bind=True)
def learn_voice_profile_task(self, user_id: str, account_id: str):
    """
    Learn user's voice profile from sent emails.
    This task runs periodically (e.g., daily).
    """
    print(f"Learning voice profile for user {user_id} at {datetime.utcnow()}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        agent = EmailAgent(user_id)
        loop.run_until_complete(agent.initialize())
        loop.run_until_complete(agent.learn_voice_profile(account_id))
        loop.run_until_complete(agent.shutdown())

        return {"status": "success", "user_id": user_id}
    except Exception as e:
        print(f"Error learning voice profile: {e}")
        return {"status": "error", "user_id": user_id, "error": str(e)}
    finally:
        loop.close()


@celery_app.task(bind=True)
def process_all_accounts_task(self, user_id: str):
    """
    Process all accounts for a user.
    This is the main scheduled task.
    """
    print(f"Processing all accounts for user {user_id} at {datetime.utcnow()}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        db = Database()
        accounts = loop.run_until_complete(db.get_accounts_by_user(user_id))

        results = []
        for account in accounts:
            account_id = account["id"]
            result = process_account_task.delay(user_id, account_id)
            results.append({"account_id": account_id, "task_id": result.id})

        return {"status": "success", "results": results}
    except Exception as e:
        print(f"Error processing all accounts: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        loop.close()


# Schedule periodic tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'process-emails-every-5-minutes': {
        'task': 'mailagent.worker.process_all_accounts_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'args': ('default_user_id',),  # This would be dynamic per user
    },
    'learn-voice-profile-daily': {
        'task': 'mailagent.worker.learn_voice_profile_task',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'args': ('default_user_id', 'default_account_id'),
    },
}
