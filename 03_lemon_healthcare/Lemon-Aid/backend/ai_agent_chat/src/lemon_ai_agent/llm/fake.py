from __future__ import annotations

from lemon_ai_agent.llm.base import LLMRequest, LLMResponse


class FakeLLMClient:
    """Deterministic LLM test double with no network behavior."""

    def __init__(self, response_text: str = "현재 입력된 정보 기준으로 설명합니다.") -> None:
        self.response_text = response_text
        self.provider = "fake"
        self.model = "fake-local-llm"

    def generate(self, _request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=self.response_text,
            provider=self.provider,
            model=self.model,
        )
