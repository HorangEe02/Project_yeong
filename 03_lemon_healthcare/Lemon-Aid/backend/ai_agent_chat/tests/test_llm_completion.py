"""LLM completion Module behavior tests."""

from __future__ import annotations

from lemon_ai_agent.llm import (
    LLMCompletion,
    LLMMessage,
    LLMRequest,
    LLMResponse,
)


class _WorkingClient:
    provider = "fake"
    model = "fake-model"

    def generate(self, _request: LLMRequest) -> LLMResponse:
        return LLMResponse(text="  safe answer  ", provider=self.provider, model=self.model)


class _FailingClient:
    provider = "fake"
    model = "fake-model"

    def generate(self, _request: LLMRequest) -> LLMResponse:
        raise RuntimeError("raw provider detail")


class _EmptyClient:
    provider = "fake"
    model = "fake-model"

    def generate(self, _request: LLMRequest) -> LLMResponse:
        return LLMResponse(text="  ", provider=self.provider, model=self.model)


def _request() -> LLMRequest:
    return LLMRequest(messages=[LLMMessage(role="user", content="안전하게 요약해줘.")])


def test_completion_returns_normalized_success() -> None:
    result = LLMCompletion(_WorkingClient()).complete(_request())

    assert result.ok is True
    assert result.text == "safe answer"
    assert result.provider == "fake"
    assert result.model == "fake-model"
    assert result.fallback_reason is None
    assert result.warnings == ()


def test_completion_handles_missing_client_without_caller_branching() -> None:
    result = LLMCompletion(None).complete(_request())

    assert result.ok is False
    assert result.provider == "deterministic"
    assert result.fallback_reason == "llm_client_unavailable"
    assert result.warnings == ()


def test_completion_concentrates_generation_errors() -> None:
    result = LLMCompletion(_FailingClient()).complete(_request())

    assert result.ok is False
    assert result.provider == "deterministic"
    assert result.model == "fake-model"
    assert result.fallback_reason == "llm_generation_failed"
    assert result.warnings == ("LLM generation failed: RuntimeError",)
    assert "raw provider detail" not in str(result)


def test_completion_rejects_empty_text() -> None:
    result = LLMCompletion(_EmptyClient()).complete(_request())

    assert result.ok is False
    assert result.provider == "deterministic"
    assert result.fallback_reason == "llm_empty_response"
    assert result.warnings == ("LLM response text was empty",)
