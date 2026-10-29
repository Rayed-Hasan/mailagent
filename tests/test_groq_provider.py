"""Tests for Groq provider."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from mailagent.llm.groq_provider import GroqProvider
from mailagent.llm.base import LLMMessage


class TestGroqProvider:
    """Test Groq provider implementation."""

    @pytest.mark.asyncio
    async def test_groq_provider_initialization(self):
        """Test that Groq provider initializes with correct API URL."""
        provider = GroqProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.api_url == "https://api.groq.com/openai/v1/chat/completions"
        assert provider.provider_name == "groq"

    @pytest.mark.asyncio
    async def test_groq_provider_capabilities(self):
        """Test Groq provider capabilities."""
        provider = GroqProvider(api_key="test-key")
        caps = provider.capabilities
        assert caps.supports_tools is True
        assert caps.supports_json_mode is True
        assert caps.context_window == 128000

    @pytest.mark.asyncio
    async def test_groq_complete_with_response_schema(self):
        """Test Groq provider with JSON schema response."""
        provider = GroqProvider(api_key="test-key")
        response_schema = {
            "type": "object",
            "properties": {"reply": {"type": "string"}},
            "required": ["reply"],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"reply": "Test response"}',
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            response = await provider.complete(
                messages=[LLMMessage(role="user", content="Test")],
                model="llama-3.1-8b-instant",
                response_schema=response_schema,
                json_mode=True,
            )

            assert response.text == '{"reply": "Test response"}'
            assert response.provider == "groq"
            assert response.model == "llama-3.1-8b-instant"
            assert response.input_tokens == 10
            assert response.output_tokens == 5

    @pytest.mark.asyncio
    async def test_groq_extract_text_content_string(self):
        """Test text extraction from string content."""
        assert GroqProvider._extract_text_content("plain text") == "plain text"
        assert GroqProvider._extract_text_content("") == ""
        assert GroqProvider._extract_text_content(None) == ""

    @pytest.mark.asyncio
    async def test_groq_extract_text_content_list(self):
        """Test text extraction from list content."""
        content = [{"type": "text", "text": "Hello "}, {"type": "text", "text": "World"}]
        assert GroqProvider._extract_text_content(content) == "Hello World"

    @pytest.mark.asyncio
    async def test_groq_retry_on_429(self):
        """Test that Groq provider retries on 429 rate limit errors."""
        provider = GroqProvider(api_key="test-key")

        # First call returns 429, second succeeds
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.text = "Rate limit exceeded"

        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = {
            "choices": [{"message": {"content": "Success after retry"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        call_count = [0]

        async def mock_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_429
            return mock_success

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=mock_post)
            response = await provider.complete(
                messages=[LLMMessage(role="user", content="Test")],
                model="llama-3.1-8b-instant",
            )

            assert response.text == "Success after retry"
            assert call_count[0] == 2  # Should have retried once

    @pytest.mark.asyncio
    async def test_groq_fallback_provider_selection(self):
        """Test that demo provider selects Groq when API key is configured."""
        from mailagent.demo.demo_provider import get_demo_provider_registry
        from mailagent.core.config import settings

        with patch.object(settings, "groq_api_key", "test-groq-key"):
            with patch.object(settings, "groq_model", "llama-3.1-8b-instant"):
                registry = get_demo_provider_registry()
                provider, model = registry.get("drafting")
                assert provider.provider_name == "groq"
                assert model == "llama-3.1-8b-instant"

    @pytest.mark.asyncio
    async def test_groq_fallback_to_openrouter_when_groq_missing(self):
        """Test that demo provider falls back to OpenRouter when Groq key not configured."""
        from mailagent.demo.demo_provider import get_demo_provider_registry
        from mailagent.core.config import settings

        with patch.object(settings, "groq_api_key", ""):
            with patch.object(settings, "openrouter_api_key", "test-openrouter-key"):
                with patch.object(settings, "openrouter_model", "google/gemini-3.8-flash"):
                    registry = get_demo_provider_registry()
                    provider, model = registry.get("drafting")
                    assert provider.provider_name == "openrouter"
                    assert model == "google/gemini-3.8-flash"
