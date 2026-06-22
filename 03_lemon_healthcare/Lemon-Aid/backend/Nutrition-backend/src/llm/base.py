"""LLM Adapter 추상 인터페이스 (Phase 2 후반 도입 예정).

본 모듈은 **현재 런타임에 연결되지 않은** 도입 예정 인터페이스다. 영양제 라벨
OCR 텍스트 파싱은 ``src/llm/ollama.py`` 의 ``OllamaSupplementParser`` 가 단독으로
수행하며, ``src/services/supplement_parser.py`` 가 그 파서를 직접 호출한다.

향후 ``OllamaSupplementParser`` 는 ``LLMAdapter`` 구현체(예: ``OllamaTextAdapter``)
에 위임하는 구조로 분리되고, Gemma 4 등 멀티모달 채널은 별도 어댑터로 추가된다.
실제 마이그레이션 PR 은 Phase 2 후반 게이트 #1(``enable_multimodal_llm=true``)
통과 후 진행한다.

운영 활성화 조건:
    - ``Settings.enable_multimodal_llm`` 이 ``True`` 일 때만 멀티모달 호출 허용
    - ``docs/17 §9`` 게이트 #1 통과
    - ``Settings.allow_external_llm`` 은 비식별 환경 외 사용 금지

Reference:
    docs/Nutrition-docs/12-local-llm-ollama-migration.md §3.1
    docs/Nutrition-docs/17-image-collection-consent-plan.md §9
    backend/CLAUDE.md Pattern 3
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMError(RuntimeError):
    """LLM 호출 실패 또는 응답 검증 실패를 나타낸다."""


@dataclass(frozen=True)
class LLMResult:
    """LLM 응답 컨테이너.

    Attributes:
        text: 모델이 생성한 최종 텍스트(또는 직렬화된 JSON 문자열).
        model: 사용된 모델 식별자(예: ``"ollama/qwen3.5:9b"``).
        latency_ms: 호출 응답 시간(ms).
    """

    text: str
    model: str
    latency_ms: int


class LLMAdapter(ABC):
    """LLM 엔진의 추상 인터페이스.

    모든 호출처는 본 추상 클래스에만 의존한다. 구현체 교체 시 DI 한 곳만
    변경하면 된다.

    Examples:
        >>> from src.llm.base import LLMAdapter
        >>> def requires_adapter(adapter: LLMAdapter) -> LLMAdapter:
        ...     return adapter
    """

    @abstractmethod
    async def analyze_text(self, prompt: str) -> LLMResult:
        """텍스트 프롬프트만으로 응답을 생성한다.

        Args:
            prompt: 모델 호출 프롬프트. JSON 스키마 지시를 포함할 수 있다.

        Returns:
            ``LLMResult`` — 모델이 생성한 텍스트와 메타데이터.

        Raises:
            LLMError: 호출 실패 또는 응답 검증 실패 시.
        """
        ...

    async def analyze_multimodal(
        self,
        prompt: str,
        image_bytes: bytes,
    ) -> LLMResult:
        """이미지와 텍스트 프롬프트를 함께 사용해 응답을 생성한다.

        텍스트 전용 어댑터는 본 메서드를 구현하지 않으므로 기본 동작으로
        ``NotImplementedError`` 를 발생시킨다. Gemma 4 등 멀티모달 가능 어댑터는
        본 메서드를 재정의한다. 운영 활성화 조건은 ``docs/17 §9`` 의 게이트 #1
        통과와 ``enable_multimodal_llm=True`` 설정을 동시에 만족해야 한다.

        Args:
            prompt: 라벨 파싱 지시 프롬프트. JSON 스키마를 포함할 수 있다.
            image_bytes: JPEG/PNG 이미지(최대 10MB, 2048px 이하 권장).

        Returns:
            ``LLMResult`` — 모델이 생성한 텍스트와 메타데이터.

        Raises:
            NotImplementedError: 텍스트 전용 어댑터에서 호출된 경우.
            LLMError: 호출 실패 또는 응답 검증 실패 시.
        """
        raise NotImplementedError(
            "This adapter does not support multimodal inputs. "
            "Use an adapter that supports analyze_multimodal."
        )
