"""
Application configuration using Pydantic Settings
"""

from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # BYOK model configuration. Provider credentials are encrypted before persistence.
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_ai_api_key: str = ""
    mailagent_encryption_key: str = ""
    model_classification: str = "claude-3-5-haiku-latest"
    model_drafting: str = "claude-3-5-sonnet-latest"
    monthly_budget_usd: float = 0.0
    max_replies_per_thread_per_day: int = 1

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Gmail OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/gmail/callback"

    # Application
    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"

    # Storage backend configuration
    storage_backend: Literal["supabase", "sqlite"] = "sqlite"
    sqlite_db_path: str = "mailagent.db"

    # Task queue configuration
    task_queue_backend: Literal["celery", "local"] = "local"
    local_queue_db_path: str = "mailagent-queue.db"

    # Agent Settings
    max_auto_replies_per_hour: int = 10
    confidence_threshold: float = 0.85
    default_autonomy_mode: Literal["approve", "auto_safe", "auto_full"] = "approve"
    delay_send_seconds: int = 60

    # Dashboard
    # Loopback is the safe personal default. Enterprise deployments should put
    # the service behind HTTPS and set an explicit bind address.
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8000
    dashboard_api_token: str = ""
    dashboard_user_id: str = ""
    dashboard_allowed_origins: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
