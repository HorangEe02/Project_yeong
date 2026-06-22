from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMRequest:
    messages: list[LLMMessage]
    temperature: float = 0.2
    max_tokens: int = 500
    response_format: dict[str, Any] | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str


class LocalLLMClient(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate explanatory text from a local or self-hosted LLM."""
        ...
