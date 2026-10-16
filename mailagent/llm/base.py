"""Provider-neutral LLM contract used by the agent pipeline.

The pipeline only speaks this interface. Provider adapters may use native tools,
JSON mode, or a plain completion internally, but never leak those details into
classification, drafting, or safety decisions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMTool:
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_tools: bool = False
    supports_json_mode: bool = False
    context_window: int = 0


@dataclass(frozen=True)
class LLMResponse:
    """Normalized response returned by every adapter."""

    text: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = ""
    used_json_fallback: bool = False
    raw: Optional[Dict[str, Any]] = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMProvider(ABC):
    """Minimal async contract for Claude, GPT, Gemini, and compatible APIs."""

    provider_name: str

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        response = await self.complete(
            messages,
            model=model,
            max_tokens=max_tokens,
        )
        yield response.text
