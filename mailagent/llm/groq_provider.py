"""Groq provider adapter implementing the LLMProvider interface.

Groq provides an OpenAI-compatible API with fast inference on Llama models.
"""

import httpx
import json
import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

from mailagent.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMTool,
    ProviderCapabilities,
)

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """Groq provider adapter for accessing Llama models with fast inference."""

    provider_name = "groq"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=True,
            supports_json_mode=True,
            context_window=128000,  # Llama 3.1 context window
        )

    @staticmethod
    def _extract_text_content(content: Any) -> str:
        """Normalize OpenAI-compatible string and multimodal text-part outputs."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and part.get("type") in ("text", "output_text"):
                    text = part.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
            return "".join(text_parts)
        if content is None:
            return ""
        raise ValueError("Groq returned unsupported message content")

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str,
        tools: Sequence[LLMTool] = (),
        response_schema: Optional[Dict[str, Any]] = None,
        json_mode: bool = False,
        max_tokens: int = 512,
        timeout_seconds: float = 30,
    ) -> LLMResponse:
        """Complete a prompt using Groq API with retry logic for rate limiting."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        # Handle JSON mode via response_schema if provided
        if response_schema:
            # Use simpler JSON mode instead of strict schema for better compatibility
            payload["response_format"] = {"type": "json_object"}
        elif json_mode:
            payload["response_format"] = {"type": "json_object"}

        # Handle tool calls if provided
        elif tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]

        # Retry logic with exponential backoff for rate limiting (429)
        max_retries = 3
        base_delay = 2.0  # seconds

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    response = await client.post(self.api_url, headers=headers, json=payload)

                    # Handle rate limiting (429)
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(
                                "Groq rate limited (429). Retrying in %s seconds (attempt %d/%d)",
                                delay,
                                attempt + 1,
                                max_retries
                            )
                            await asyncio.sleep(delay)
                            continue
                        else:
                            # After max retries, raise the error
                            response.raise_for_status()

                    response.raise_for_status()
                    data = response.json()

                # Extract content from response
                if not isinstance(data, dict) or not isinstance(data.get("choices"), list) or not data["choices"]:
                    raise ValueError("Groq returned no choices")

                choice = data["choices"][0]
                message = choice.get("message") if isinstance(choice, dict) else None
                if not isinstance(message, dict):
                    raise ValueError("Groq returned a malformed assistant message")
                text = self._extract_text_content(message.get("content"))

                # Parse tool calls if present
                tool_calls = []
                if message.get("tool_calls"):
                    for tool_call in message["tool_calls"]:
                        tool_calls.append(
                            {
                                "name": tool_call.get("function", {}).get("name"),
                                "arguments": json.loads(tool_call.get("function", {}).get("arguments", "{}")),
                            }
                        )

                # Extract token usage
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

                return LLMResponse(
                    text=text,
                    tool_calls=tool_calls,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=model,
                    provider=self.provider_name,
                    raw=data,
                )

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    # Already handled above, but double-check
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "Groq HTTP error 429. Retrying in %s seconds (attempt %d/%d)",
                        delay,
                        attempt + 1,
                        max_retries
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Re-raise non-429 errors or after max retries
                    raise

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """Stream completion using Groq API (non-streaming fallback)."""

        response = await self.complete(messages, model=model, max_tokens=max_tokens)
        yield response.text
