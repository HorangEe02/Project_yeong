"""OCR Adapter 추상 인터페이스 + 결과 DTO.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 2
    docs/dev-guides/07-ocr-pipeline.md §2
    backend/CLAUDE.md Pattern 3
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Final

CONFIDENCE_HIGH_THRESHOLD: Final[float] = 0.85
"""``OCRResult.is_high_confidence`` 임계값.

해당 임계 이상이면 OCRPipeline이 보조 엔진을 호출하지 않는다.
"""


@dataclass(frozen=True)
class OCRResult:
    """OCR 결과 컨테이너.

    Attributes:
        text: 추출된 전체 텍스트.
        confidence: 평균 신뢰도 (0.0~1.0).
        engine: 사용된 OCR 엔진 식별자 (예: ``"google_vision_v1"``).
        words: 단어 단위 결과. 각 항목은 ``{"text": str, "confidence": float}``.
        elapsed_ms: 호출 소요 시간 (ms).
    """

    text: str
    confidence: float
    engine: str
    words: list[dict[str, Any]] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def is_high_confidence(self) -> bool:
        """신뢰도가 ``CONFIDENCE_HIGH_THRESHOLD`` 이상인지."""
        return self.confidence >= CONFIDENCE_HIGH_THRESHOLD


class OCRAdapter(ABC):
    """OCR 엔진의 추상 인터페이스.

    모든 OCR 구현체는 본 클래스를 상속한다. 호출처는 본 추상 클래스에만 의존하므로
    엔진 교체 시 DI 한 곳만 변경하면 된다.

    Examples:
        >>> from src.ocr.google_vision import GoogleVisionOCR
        >>> ocr: OCRAdapter = GoogleVisionOCR()  # doctest: +SKIP
        >>> result = await ocr.extract_text(image_bytes)  # doctest: +SKIP
    """

    @abstractmethod
    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """이미지에서 텍스트를 추출한다.

        Args:
            image_bytes: 전처리된 이미지 바이트 (JPEG, 5MB 이하).

        Returns:
            ``OCRResult``.

        Raises:
            OCRApiError: API 호출 실패.
            OCRImageError: 이미지 자체 문제.
            OCRTimeoutError: 타임아웃.
        """
        ...

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """엔진 식별자 문자열 (예: ``"google_vision_v1"``)."""
        ...
