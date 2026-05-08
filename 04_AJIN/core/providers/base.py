from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import ClassVar

from core.llm_types import LLMMode, StreamEvent, StreamRequest


class LLMProvider(ABC):
    """모든 LLM 프로바이더 (Gemini / Ollama / LM Studio) 의 공통 인터페이스."""

    name: ClassVar[str]

    @abstractmethod
    async def health_check(self) -> bool:
        """프로바이더 endpoint 가 응답하는지 검사. 실패는 False, 예외 던지지 않음."""

    @abstractmethod
    def stream(
        self,
        req: StreamRequest,
        model: str,
    ) -> AsyncIterator[StreamEvent]:
        """프롬프트 → 토큰 단위 StreamEvent 를 yield 하는 async generator.

        주의: 이 메서드 자체는 `async def` 가 아닌 일반 메서드이며, 반환값이
        `AsyncIterator[StreamEvent]` 인 async generator 다. 구현 측에서는
        `async def stream(...): ... yield ...` 로 작성한다.
        """

    @abstractmethod
    async def embed(self, text: str, model: str) -> list[float]:
        """단일 텍스트를 벡터로 인코딩. 임베딩 미지원 프로바이더는 NotImplementedError."""

    def supports_mode(self, mode: LLMMode) -> bool:
        """기본은 모든 모드 지원. 임베딩 전용 / 비전 미지원 프로바이더가 오버라이드."""
        return True
