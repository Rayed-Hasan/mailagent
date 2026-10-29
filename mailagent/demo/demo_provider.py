"""Demo-specific AI provider setup using OpenRouter with fallback."""

import httpx
from mailagent.llm.registry import ProviderRegistry, ModelSlot
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
) -> tuple[LLMResponse, bool]:
    """Use optional OpenRouter inference with an explicit deterministic fallback.

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
            await provider.complete(messages, model=model, max_tokens=max_tokens),
            True,
        )

    # Try OpenRouter with detailed error logging
    try:
        logger.info("Attempting OpenRouter inference for %s with model %s", role, model)
        response = await provider.complete(messages, model=model, max_tokens=max_tokens)
        logger.info("OpenRouter inference successful for %s", role)
        return (response, False)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            logger.error("OpenRouter rate limited (429) for %s. Falling back to deterministic provider.", role)
        else:
            logger.error(
                "OpenRouter HTTP error %d for %s; falling back to deterministic provider",
                exc.response.status_code,
                role,
            )
    except Exception as exc:
        logger.error(
            "OpenRouter inference failed for %s (%s); falling back to deterministic provider",
            role,
            type(exc).__name__,
        )

    # Fallback to deterministic provider
    logger.warning("Using deterministic fallback provider for %s after OpenRouter failure", role)
    fallback = FallbackProvider()
    response = await fallback.complete(
        messages,
        model="fallback-deterministic",
        max_tokens=max_tokens,
    )
    return response, True


def get_demo_provider_registry() -> ProviderRegistry:
    """
    Get a provider registry configured for demo mode.

    In demo mode:
    - Use OpenRouter if API key is configured
    - Fall back to deterministic responses if no key or on error
    - Never use Claude in demo mode
    """
    registry = ProviderRegistry()

    # Register OpenRouter provider
    if settings.openrouter_api_key:
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
        # Use fallback provider when no OpenRouter key
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
