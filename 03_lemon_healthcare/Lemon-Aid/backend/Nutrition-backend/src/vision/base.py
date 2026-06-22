"""Vision Adapter 추상 인터페이스 — Phase 3 게이트.

영양제 라벨 영역 검출(detection) 전용 인터페이스다. 분류(classification)나
의료 판단은 본 어댑터에서 제공하지 않는다. ``src.vision.yolo.YoloLabelDetector`` 는
안정적인 import 경로를 제공하는 fail-closed scaffold 이며, 실제 모델 추론은
Phase 3 게이트 통과 후 별도 PR 에서 연결한다.

활성화 조건(모두 동시 충족 시에만 실제 추론 활성화):
    1. ``docs/17 §8`` 게이트 #2 통과 (발주처 리뷰 + 의료법 검토)
    2. ``Settings.enable_vision_classifier=True``
    3. ``pip install ".[vision]"`` (``backend/pyproject.toml`` 의 vision extras)

검출 결과는 OCR 입력 전처리(라벨 영역 크롭)에만 사용한다. 의료 판단 출력에
직접 사용하지 않는다(CLAUDE.md Rule 1).

Reference:
    docs/Nutrition-docs/17-image-collection-consent-plan.md §7, §9
    docs/Nutrition-docs/15-regulated-feature-feasibility-and-compliance-plan.md §3.2~3.3
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
        label: 검출된 object class label. OCR 전처리용 metadata이며 제품명/성분명이 아니다.
        model: 검출에 사용된 모델 태그 또는 파일명.
    """

    x: int
    y: int
    width: int
    height: int
    confidence: float
    label: str | None = None
    model: str | None = None


class VisionAdapter(ABC):
    """비전 어댑터 추상 인터페이스.

    영양제 라벨 영역 검출만 담당한다. 호출처는 본 어댑터로부터 받은
    ``BoundingBox`` 를 OCR 입력 전처리(크롭)에만 사용해야 하며, 의료 판단
    출력에 직접 사용해서는 안 된다.

    Examples:
        >>> from src.config import Settings
        >>> from src.vision.yolo import YoloLabelDetector
        >>> detector: VisionAdapter = YoloLabelDetector(Settings(enable_vision_classifier=True))
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

    async def detect_regions(self, image_bytes: bytes) -> list[BoundingBox]:
        """이미지에서 OCR 전처리용 후보 영역 목록을 검출한다.

        기존 단일 ROI 어댑터와의 호환성을 위해 기본 구현은
        ``detect_label_region`` 결과 하나를 목록으로 감싼다. 다중 섹션
        detector는 이 메서드를 override하여 여러 후보를 반환한다.

        Args:
            image_bytes: 이미지 원본 바이트(JPEG/PNG, 10MB 이하).

        Returns:
            OCR 전처리 및 리뷰 UI에 사용할 후보 영역 목록.

        Raises:
            VisionError: 호출 실패 또는 라벨 영역 미검출 시.
        """
        return [await self.detect_label_region(image_bytes)]
