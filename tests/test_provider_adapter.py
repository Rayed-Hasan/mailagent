"""Tests for LLM provider adapter and BYOK functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mailagent.llm.claude_provider import ClaudeProvider
from mailagent.llm.base import LLMMessage, LLMResponse
from mailagent.llm.registry import ProviderRegistry, ModelSlot
from mailagent.core.secret_store import SecretStore


class FakeProvider:
    """Fake provider for testing."""
    provider_name = "fake"


def test_claude_provider_implements_interface():
    """ClaudeProvider implements LLMProvider interface."""
    provider = ClaudeProvider(api_key="test-key")
    assert provider.provider_name == "claude"
    assert provider.capabilities.supports_tools is True
    assert provider.capabilities.supports_json_mode is True
    assert provider.capabilities.context_window == 200000


@pytest.mark.asyncio
async def test_claude_provider_complete_basic():
    """Test basic completion through Claude provider."""
    provider = ClaudeProvider(api_key="test-key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "Hello world"}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        response = await provider.complete(
            messages=[LLMMessage(role="user", content="Say hello")],
            model="claude-3-5-haiku-latest",
            max_tokens=100,
        )

        assert response.text == "Hello world"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.model == "claude-3-5-haiku-latest"
        assert response.provider == "claude"


@pytest.mark.asyncio
async def test_claude_provider_complete_with_json_mode():
    """Test completion with JSON mode."""
    provider = ClaudeProvider(api_key="test-key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [
            {
                "type": "tool_use",
                "name": "output_json",
                "input": {"category": "urgent", "priority": 90},
            }
        ],
        "usage": {"input_tokens": 15, "output_tokens": 10},
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        response = await provider.complete(
            messages=[LLMMessage(role="user", content="Classify this")],
            model="claude-3-5-haiku-latest",
            response_schema={"type": "object"},
            json_mode=True,
            max_tokens=100,
        )

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["name"] == "output_json"
        assert response.tool_calls[0]["arguments"] == {"category": "urgent", "priority": 90}


@pytest.mark.asyncio
async def test_claude_provider_stream_fallback():
    """Test streaming falls back to complete."""
    provider = ClaudeProvider(api_key="test-key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "Streaming response"}],
        "usage": {"input_tokens": 5, "output_tokens": 3},
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        chunks = []
        async for chunk in provider.stream(
            messages=[LLMMessage(role="user", content="Stream this")],
            model="claude-3-5-haiku-latest",
        ):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0] == "Streaming response"


def test_provider_registry_register_and_get():
    """Test provider registry registration and retrieval."""
    registry = ProviderRegistry()
    fake = FakeProvider()

    registry.register(fake)
    assert "fake" in registry._providers

    registry.set_slot(ModelSlot("classification", "fake", "cheap-model"))
    provider, model = registry.get("classification")

    assert provider.provider_name == "fake"
    assert model == "cheap-model"


def test_provider_registry_enforces_known_roles():
    """Test registry only allows classification and drafting roles."""
    registry = ProviderRegistry()
    registry.register(FakeProvider())

    registry.set_slot(ModelSlot("classification", "fake", "model-1"))
    registry.set_slot(ModelSlot("drafting", "fake", "model-2"))

    with pytest.raises(ValueError, match="model role must be"):
        registry.set_slot(ModelSlot("replying", "fake", "model-3"))


def test_provider_registry_requires_registered_provider():
    """Test registry requires provider to be registered before setting slot."""
    registry = ProviderRegistry()

    with pytest.raises(KeyError, match="provider is not registered"):
        registry.set_slot(ModelSlot("classification", "fake", "model"))


def test_provider_registry_validates_model_not_empty():
    """Test registry validates model is not empty."""
    registry = ProviderRegistry()
    registry.register(FakeProvider())

    with pytest.raises(ValueError, match="model cannot be empty"):
        registry.set_slot(ModelSlot("classification", "fake", ""))


def test_secret_store_encrypts_provider_key():
    """Test SecretStore can encrypt provider API keys."""
    store = SecretStore(key=b"0" * 32)
    api_key = "sk-ant-api03-test-key-12345"

    encrypted = store.encrypt(api_key, "provider-setting:user-123:claude")
    assert encrypted != api_key
    assert isinstance(encrypted, str)

    decrypted = store.decrypt(encrypted, "provider-setting:user-123:claude")
    assert decrypted == api_key


def test_secret_store_binds_provider_key_to_user():
    """Test provider key is bound to user ID."""
    store = SecretStore(key=b"0" * 32)
    api_key = "sk-ant-api03-test-key"

    encrypted = store.encrypt(api_key, "provider-setting:user-123:claude")

    # Different user should fail to decrypt
    with pytest.raises(ValueError, match="invalid encrypted secret"):
        store.decrypt(encrypted, "provider-setting:user-456:claude")

    # Different provider should fail to decrypt
    with pytest.raises(ValueError, match="invalid encrypted secret"):
        store.decrypt(encrypted, "provider-setting:user-123:openai")


def test_secret_store_redacts_provider_key():
    """Test provider key redaction."""
    api_key = "sk-ant-api03-test-key-12345"
    redacted = SecretStore.redacted(api_key)
    assert redacted == "••••2345"
    assert api_key not in redacted


def test_secret_store_requires_256_bit_key():
    """Test SecretStore requires 256-bit key."""
    with pytest.raises(ValueError, match="256 bits"):
        SecretStore(key=b"0" * 16)

    with pytest.raises(ValueError, match="256 bits"):
        SecretStore(key=b"0" * 64)
