"""
Application configuration using Pydantic Settings
"""

from pydantic import ConfigDict, model_validator
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", case_sensitive=False)

    # BYOK model configuration. Provider credentials are encrypted before persistence.
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_ai_api_key: str = ""
    openrouter_api_key: str = ""
    mailagent_encryption_key: str = ""
    model_classification: str = "claude-3-5-haiku-latest"
    model_drafting: str = "claude-3-5-sonnet-latest"
    openrouter_model: str = "google/gemma-2-9b-it:free"
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
    demo_sqlite_db_path: str = "mailagent-demo.db"

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

    # Public Demo Mode
    # When enabled, serves a publicly accessible demo.
    # Uses owner-authorized Gmail account for real email integration and OpenRouter for AI.
    public_demo_mode: bool = False
    demo_rate_limit_per_minute: int = 30
    demo_max_concurrent_requests: int = 5
    demo_reset_endpoint_enabled: bool = True
    demo_gmail_refresh_token: str = ""
    demo_gmail_client_id: str = ""
    demo_gmail_client_secret: str = ""
    demo_gmail_redirect_uri: str = ""
    demo_gmail_email: str = ""
    demo_allow_public_send: bool = False

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.environment != "production":
            return self

        if self.public_demo_mode:
            if self.storage_backend != "sqlite":
                raise ValueError(
                    "Public demo mode requires STORAGE_BACKEND=sqlite"
                )
            if self.task_queue_backend != "local":
                raise ValueError(
                    "Public demo mode requires TASK_QUEUE_BACKEND=local"
                )
            return self

        missing = []
        if self.storage_backend != "supabase":
            missing.append("STORAGE_BACKEND=supabase")
        if self.task_queue_backend != "celery":
            missing.append("TASK_QUEUE_BACKEND=celery")
        for field_name, env_name in (
            ("supabase_url", "SUPABASE_URL"),
            ("supabase_service_role_key", "SUPABASE_SERVICE_ROLE_KEY"),
            ("celery_broker_url", "CELERY_BROKER_URL"),
            ("celery_result_backend", "CELERY_RESULT_BACKEND"),
            ("dashboard_api_token", "DASHBOARD_API_TOKEN"),
            ("dashboard_user_id", "DASHBOARD_USER_ID"),
        ):
            if not getattr(self, field_name).strip():
                missing.append(env_name)

        if missing:
            raise ValueError(
                "Production configuration is incomplete; refusing to start: "
                + ", ".join(missing)
            )
        return self


settings = Settings()
