"""Vision Adapter 추상 인터페이스 — Phase 3 게이트.

영양제 라벨 영역 검출(detection) 전용 인터페이스. 분류(classification)나
의료 판단은 본 어댑터에서 제공하지 않는다. ``docs/17 §8`` 게이트 #2 통과 및
``enable_vision_classifier=True`` 설정 후에만 실제 구현체를 활성화한다.

Reference:
    docs/17-image-collection-consent-plan.md §7, §9
    docs/15-regulated-feature-feasibility-and-compliance-plan.md §3.2~3.3
    backend/CLAUDE.md Pattern 3
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class VisionError(RuntimeError):
    """비전 어댑터 호출 실패 또는 입력 검증 실패를 나타낸다."""


@dataclass(frozen=True)
class BoundingBox:
    """라벨 영역 경계 상자.

    좌표계는 입력 이미지 픽셀 기준이며 원점은 좌상단이다.

    Attributes:
        x: 좌상단 x 좌표(px).
        y: 좌상단 y 좌표(px).
        width: 영역 너비(px, 양수).
        height: 영역 높이(px, 양수).
        confidence: 검출 신뢰도(0.0~1.0).
    """

    x: int
    y: int
    width: int
    height: int
    confidence: float


class VisionAdapter(ABC):
    """비전 어댑터 추상 인터페이스.

    영양제 라벨 영역 검출만 담당한다. 호출처는 본 어댑터로부터 받은
    ``BoundingBox`` 를 OCR 입력 전처리(크롭)에만 사용해야 하며, 의료 판단
    출력에 직접 사용해서는 안 된다.

    Examples:
        >>> from src.vision.yolo import YoloLabelDetector
        >>> detector: VisionAdapter = YoloLabelDetector()
        >>> box = await detector.detect_label_region(image_bytes)
        >>> print(box.confidence)
    """

    @abstractmethod
    async def detect_label_region(self, image_bytes: bytes) -> BoundingBox:
        """이미지에서 영양제 라벨로 추정되는 영역을 검출한다.

        Args:
            image_bytes: 이미지 원본 바이트(JPEG/PNG, 10MB 이하).

        Returns:
            ``BoundingBox`` — 검출된 라벨 영역. 검출 실패 시 ``VisionError``.

        Raises:
            VisionError: 호출 실패 또는 라벨 영역 미검출 시.
        """
        ...
