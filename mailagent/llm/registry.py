"""Provider registry with safe model-slot selection."""

from dataclasses import dataclass
from typing import Dict, Optional

from mailagent.llm.base import LLMProvider


@dataclass(frozen=True)
class ModelSlot:
    """One of the two user-configurable model roles."""

    role: str
    provider: str
    model: str


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, LLMProvider] = {}
        self._slots: Dict[str, ModelSlot] = {}

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.provider_name] = provider

    def set_slot(self, slot: ModelSlot) -> None:
        if slot.role not in {"classification", "drafting"}:
            raise ValueError("model role must be classification or drafting")
        if slot.provider not in self._providers:
            raise KeyError(f"provider is not registered: {slot.provider}")
        if not slot.model.strip():
            raise ValueError("model cannot be empty")
        self._slots[slot.role] = slot

    def get(self, role: str) -> tuple[LLMProvider, str]:
        try:
            slot = self._slots[role]
            return self._providers[slot.provider], slot.model
        except KeyError as exc:
            raise KeyError(f"no configured model slot for: {role}") from exc

    def configured_slots(self) -> Dict[str, ModelSlot]:
        return dict(self._slots)
