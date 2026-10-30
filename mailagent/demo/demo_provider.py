"""Demo-specific AI provider setup with Groq, OpenRouter, and fallback."""

import logging

import httpx

from mailagent.core.config import settings
from mailagent.llm.base import LLMResponse
from mailagent.llm.fallback_provider import FallbackProvider
from mailagent.llm.groq_provider import GroqProvider
from mailagent.llm.openrouter_provider import OpenRouterProvider
from mailagent.llm.registry import ModelSlot, ProviderRegistry

logger = logging.getLogger(__name__)


async def complete_demo(
    messages,
    *,
    role: str,
    max_tokens: int = 512,
    response_schema=None,
) -> tuple[LLMResponse, bool]:
    """Call the configured inference provider, falling back safely on failure.

    Returns ``(response, fallback_used)`` so callers can reject synthetic
    fallback text when they need a genuine model-generated reply.
    """
    provider, model = get_demo_provider_registry().get(role)

    if provider.provider_name == "fallback":
        logger.info("Using deterministic fallback provider for %s", role)
        response = await provider.complete(
            messages,
            model=model,
            max_tokens=max_tokens,
            response_schema=response_schema,
            json_mode=response_schema is not None,
        )
        return response, True

    try:
        logger.info("Attempting %s inference for %s with model %s", provider.provider_name, role, model)
        response = await provider.complete(
            messages,
            model=model,
            max_tokens=max_tokens,
            response_schema=response_schema,
            json_mode=response_schema is not None,
        )
        return response, False
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500] if exc.response else ""
        logger.error(
            "%s HTTP error %s for %s: %s; falling back to deterministic provider",
            provider.provider_name,
            exc.response.status_code if exc.response else "unknown",
            role,
            body,
        )
        error_message = f"HTTP {exc.response.status_code}: {body}" if exc.response else str(exc)
    except Exception as exc:
        logger.error(
            "%s inference failed for %s (%s: %s); falling back to deterministic provider",
            provider.provider_name,
            role,
            type(exc).__name__,
            exc,
        )
        error_message = f"{type(exc).__name__}: {exc}"

    logger.warning("Using deterministic fallback provider for %s after %s failure", role, provider.provider_name)
    fallback = FallbackProvider()
    response = await fallback.complete(messages, model="fallback-deterministic", max_tokens=max_tokens)
    if isinstance(response.raw, dict):
        response.raw["provider_error"] = error_message
    return response, True


def get_demo_provider_registry() -> ProviderRegistry:
    """Prefer Groq, then OpenRouter, then deterministic fallback."""
    registry = ProviderRegistry()
    logger.info("Groq API key configured: %s", bool(settings.groq_api_key))
    logger.info("OpenRouter API key configured: %s", bool(settings.openrouter_api_key))

    if settings.groq_api_key:
        provider = GroqProvider(api_key=settings.groq_api_key)
        model = settings.groq_model
    elif settings.openrouter_api_key:
        provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
        model = settings.openrouter_model
    else:
        provider = FallbackProvider()
        model = "fallback-deterministic"

    registry.register(provider)
    for role in ("classification", "drafting"):
        registry.set_slot(ModelSlot(role=role, provider=provider.provider_name, model=model))
    return registry
