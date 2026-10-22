"""Claude provider adapter implementing the LLMProvider interface."""

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


class ClaudeProvider(LLMProvider):
    """Claude (Anthropic) provider adapter."""

    provider_name = "claude"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.anthropic.com/v1/messages"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=True,
            supports_json_mode=True,
            context_window=200000,
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
        """Complete a prompt using Claude API."""

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        # Handle JSON mode via response_schema if provided
        if response_schema:
            payload["tools"] = [
                {
                    "name": "output_json",
                    "description": "Output structured JSON",
                    "input_schema": response_schema,
                }
            ]
            payload["tool_choice"] = {"type": "tool", "name": "output_json"}

        # Handle tool calls if provided
        elif tools:
            payload["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        # Extract content from response
        content_block = data["content"][0]
        text = content_block.get("text", "")

        # Parse tool calls if present
        tool_calls = []
        if content_block.get("type") == "tool_use":
            tool_calls = [
                {
                    "name": content_block["name"],
                    "arguments": content_block.get("input", {}),
                }
            ]

        # Extract token usage
        input_tokens = data.get("usage", {}).get("input_tokens", 0)
        output_tokens = data.get("usage", {}).get("output_tokens", 0)

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
        """Stream completion using Claude API (non-streaming fallback)."""

        response = await self.complete(messages, model=model, max_tokens=max_tokens)
        yield response.text
