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
    )

    assert configured.public_demo_mode is True
    assert configured.dashboard_api_token == ""


def test_public_demo_rejects_enterprise_backends():
    with pytest.raises(ValidationError, match="STORAGE_BACKEND=sqlite"):
        Settings(
            _env_file=None,
            environment="production",
            public_demo_mode=True,
            storage_backend="supabase",
            task_queue_backend="local",
        )
