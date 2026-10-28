import base64

import pytest
from pydantic import ValidationError

from mailagent.core.config import Settings


def test_production_configuration_rejects_personal_backends():
    with pytest.raises(ValidationError, match="STORAGE_BACKEND=supabase"):
        Settings(
            _env_file=None,
            environment="production",
            storage_backend="sqlite",
            task_queue_backend="local",
        )


def test_complete_production_configuration_is_accepted():
    configured = Settings(
        _env_file=None,
        environment="production",
        storage_backend="supabase",
        task_queue_backend="celery",
        supabase_url="https://synthetic.invalid",
        supabase_service_role_key="synthetic",
        celery_broker_url="redis://synthetic.invalid:6379/0",
        celery_result_backend="redis://synthetic.invalid:6379/0",
        dashboard_api_token="synthetic",
        dashboard_user_id="synthetic",
    )

    assert configured.storage_backend == "supabase"
    assert configured.task_queue_backend == "celery"


def test_public_demo_production_configuration_needs_no_enterprise_services():
    configured = Settings(
        _env_file=None,
        environment="production",
        public_demo_mode=True,
        storage_backend="sqlite",
        task_queue_backend="local",
        mailagent_encryption_key=base64.urlsafe_b64encode(b"t" * 32).decode().rstrip("="),
        dashboard_api_token="synthetic-owner-token",
        dashboard_user_id="demo-owner",
        demo_gmail_client_id="synthetic-client-id",
        demo_gmail_client_secret="synthetic-client-secret",
        demo_gmail_redirect_uri="https://demo.invalid/auth/gmail/callback",
        demo_gmail_email="demo@example.invalid",
    )

    assert configured.public_demo_mode is True
    assert configured.dashboard_api_token == "synthetic-owner-token"


def test_public_demo_requires_owner_authentication():
    with pytest.raises(ValidationError, match="DASHBOARD_API_TOKEN"):
        Settings(
            _env_file=None,
            environment="production",
            public_demo_mode=True,
            storage_backend="sqlite",
            task_queue_backend="local",
            mailagent_encryption_key=base64.urlsafe_b64encode(b"t" * 32).decode().rstrip("="),
            dashboard_user_id="demo-owner",
            demo_gmail_client_id="synthetic-client-id",
            demo_gmail_client_secret="synthetic-client-secret",
            demo_gmail_redirect_uri="https://demo.invalid/auth/gmail/callback",
            demo_gmail_email="demo@example.invalid",
        )


def test_public_demo_production_requires_private_encryption_key():
    with pytest.raises(ValidationError, match="MAILAGENT_ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            environment="production",
            public_demo_mode=True,
            storage_backend="sqlite",
            task_queue_backend="local",
            mailagent_encryption_key="",
        )


@pytest.mark.parametrize("key", ["short", "A" * 44, "!" * 43])
def test_public_demo_production_rejects_malformed_encryption_key(key):
    with pytest.raises(ValidationError, match="MAILAGENT_ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            environment="production",
            public_demo_mode=True,
            storage_backend="sqlite",
            task_queue_backend="local",
            mailagent_encryption_key=key,
        )


def test_public_demo_rejects_enterprise_backends():
    with pytest.raises(ValidationError, match="STORAGE_BACKEND=sqlite"):
        Settings(
            _env_file=None,
            environment="production",
            public_demo_mode=True,
            storage_backend="supabase",
            task_queue_backend="local",
        )
