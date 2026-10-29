"""Demo-specific AI provider setup with Groq, OpenRouter, and fallback."""

import httpx
from mailagent.llm.registry import ProviderRegistry, ModelSlot
from mailagent.llm.groq_provider import GroqProvider
from mailagent.llm.openrouter_provider import OpenRouterProvider
from mailagent.llm.fallback_provider import FallbackProvider
from mailagent.llm.claude_provider import ClaudeProvider
from mailagent.core.config import settings
import logging

logger = logging.getLogger(__name__)
from mailagent.llm.base import LLMResponse


async def complete_demo(
    messages,
    *,
    role: str,
    max_tokens: int = 512,
    response_schema=None,
) -> tuple[LLMResponse, bool]:
    """Use optional Groq/OpenRouter inference with an explicit deterministic fallback.

    Returns:
        Tuple of (response, fallback_used) where fallback_used is True if
        the deterministic fallback provider was used.
    """
    registry = get_demo_provider_registry()
    provider, model = registry.get(role)

    # If the registry is already configured to use fallback, use it directly
    if provider.provider_name == "fallback":
        logger.info("Using deterministic fallback provider for %s", role)
        return (
            await provider.complete(
                messages,
                model=model,
                max_tokens=max_tokens,
                response_schema=response_schema,
                json_mode=response_schema is not None,
            ),
            True,
        )

    # Try Groq/OpenRouter with detailed error logging
    provider_name = provider.provider_name
    try:
        logger.info("Attempting %s inference for %s with model %s", provider_name, role, model)
        response = await provider.complete(
            messages,
            model=model,
            max_tokens=max_tokens,
            response_schema=response_schema,
            json_mode=response_schema is not None,
        )
        logger.info("%s inference successful for %s", provider_name, role)
        return (response, False)
    except httpx.HTTPStatusError as exc:
        err_body = exc.response.text[:300] if hasattr(exc, "response") and exc.response else ""
        if exc.response.status_code == 429:
            logger.error("%s rate limited (429) for %s: %s. Falling back to deterministic provider.", provider_name, role, err_body)
        else:
            logger.error(
                "%s HTTP error %d for %s: %s; falling back to deterministic provider",
                provider_name,
                exc.response.status_code,
                role,
                err_body,
            )
        # Store error message in fallback response raw for diagnostic visibility
        last_error_msg = f"HTTP {exc.response.status_code}: {err_body}"
    except Exception as exc:
        logger.error(
            "%s inference failed for %s (%s: %s); falling back to deterministic provider",
            provider_name,
            role,
            type(exc).__name__,
            exc,
        )
        last_error_msg = f"{type(exc).__name__}: {exc}"

    # Fallback to deterministic provider
    logger.warning("Using deterministic fallback provider for %s after %s failure", role, provider_name)
    fallback = FallbackProvider()
    response = await fallback.complete(
        messages,
        model="fallback-deterministic",
        max_tokens=max_tokens,
        response_schema=response_schema,
        json_mode=response_schema is not None,
    )
    if isinstance(response.raw, dict):
        response.raw["provider_error"] = last_error_msg
    return response, True


def get_demo_provider_registry() -> ProviderRegistry:
    """
    Get a provider registry configured for demo mode.

    In demo mode:
    - Use Groq if API key is configured (preferred - faster, free tier)
    - Fall back to OpenRouter if Groq key not configured
    - Fall back to deterministic responses if no keys or on error
    - Never use Claude in demo mode
    """
    registry = ProviderRegistry()

    # Prefer Groq if API key is configured
    if settings.groq_api_key:
        groq = GroqProvider(api_key=settings.groq_api_key)
        registry.register(groq)

        # Set model slots
        registry.set_slot(
            ModelSlot(
                role="classification",
                provider="groq",
                model=settings.groq_model,
            )
        )
        registry.set_slot(
            ModelSlot(
                role="drafting",
                provider="groq",
                model=settings.groq_model,
            )
        )
    # Fall back to OpenRouter if Groq not configured
    elif settings.openrouter_api_key:
        openrouter = OpenRouterProvider(api_key=settings.openrouter_api_key)
        registry.register(openrouter)

        # Set model slots
        registry.set_slot(
            ModelSlot(
                role="classification",
                provider="openrouter",
                model=settings.openrouter_model,
            )
        )
        registry.set_slot(
            ModelSlot(
                role="drafting",
                provider="openrouter",
                model=settings.openrouter_model,
            )
        )
    else:
        # Use fallback provider when no API keys configured
        fallback = FallbackProvider()
        registry.register(fallback)

        registry.set_slot(
            ModelSlot(
                role="classification",
                provider="fallback",
                model="fallback-deterministic",
            )
        )
        registry.set_slot(
            ModelSlot(
                role="drafting",
                provider="fallback",
                model="fallback-deterministic",
            )
        )

    return registry
