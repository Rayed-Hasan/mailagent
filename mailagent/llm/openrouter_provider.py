"""OpenRouter provider adapter implementing the LLMProvider interface."""

import httpx
import json
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

from mailagent.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMTool,
    ProviderCapabilities,
)


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider adapter for accessing multiple LLM models."""

    provider_name = "openrouter"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=True,
            supports_json_mode=True,
            context_window=32000,  # Conservative default, varies by model
        )

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
        """Complete a prompt using OpenRouter API."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mailagent-demo.local",
            "X-Title": "MailAgent Demo",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        # Handle JSON mode via response_schema if provided
        if response_schema:
            payload["response_format"] = {"type": "json_object", "schema": response_schema}

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

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        # Extract content from response
        if "choices" not in data or not data["choices"]:
            raise ValueError("OpenRouter returned no choices")

        choice = data["choices"][0]
        message = choice.get("message", {})
        text = message.get("content", "")

        # Parse tool calls if present
        tool_calls = []
        if "tool_calls" in message:
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

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """Stream completion using OpenRouter API (non-streaming fallback)."""

        response = await self.complete(messages, model=model, max_tokens=max_tokens)
        yield response.text
