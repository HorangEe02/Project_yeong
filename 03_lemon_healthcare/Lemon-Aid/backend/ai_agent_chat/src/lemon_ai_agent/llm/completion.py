from __future__ import annotations

from dataclasses import dataclass

from lemon_ai_agent.llm.base import LLMRequest, LocalLLMClient


@dataclass(frozen=True)
class LLMCompletionResult:
    text: str
    provider: str
    model: str | None
    fallback_reason: str | None = None
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.fallback_reason is None


class LLMCompletion:
    """Normalizes local LLM adapter outcomes for agent callers."""

    def __init__(self, client: LocalLLMClient | None) -> None:
        self._client = client

    def complete(self, request: LLMRequest) -> LLMCompletionResult:
        if self._client is None:
            return LLMCompletionResult(
                text="",
                provider="deterministic",
                model=None,
                fallback_reason="llm_client_unavailable",
            )

        try:
            response = self._client.generate(request)
        except Exception as exc:
            return LLMCompletionResult(
                text="",
                provider="deterministic",
                model=getattr(self._client, "model", None),
                fallback_reason="llm_generation_failed",
                warnings=(f"LLM generation failed: {exc.__class__.__name__}",),
            )

        text = response.text.strip()
        if not text:
            return LLMCompletionResult(
                text="",
                provider="deterministic",
                model=response.model,
                fallback_reason="llm_empty_response",
                warnings=("LLM response text was empty",),
            )

        return LLMCompletionResult(
            text=text,
            provider=response.provider,
            model=response.model,
        )
