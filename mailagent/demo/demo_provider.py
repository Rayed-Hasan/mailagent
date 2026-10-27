"""Demo-specific AI provider setup using OpenRouter with fallback."""

from mailagent.llm.registry import ProviderRegistry, ModelSlot
from mailagent.llm.openrouter_provider import OpenRouterProvider
from mailagent.llm.fallback_provider import FallbackProvider
from mailagent.llm.claude_provider import ClaudeProvider
from mailagent.core.config import settings
from mailagent.llm.base import LLMResponse


async def complete_demo(
    messages,
    *,
    role: str,
    max_tokens: int = 512,
) -> tuple[LLMResponse, bool]:
    """Use optional OpenRouter inference with an explicit deterministic fallback."""
    registry = get_demo_provider_registry()
    provider, model = registry.get(role)
    if provider.provider_name == "fallback":
        return (
            await provider.complete(messages, model=model, max_tokens=max_tokens),
            True,
        )

    try:
        return (
            await provider.complete(messages, model=model, max_tokens=max_tokens),
            False,
        )
    except Exception:
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
