"""Vision Adapter 추상 인터페이스 — Phase 3 게이트.

영양제 라벨 영역 검출(detection) 전용 인터페이스. 분류(classification)나
의료 판단은 본 어댑터에서 제공하지 않는다. ``docs/17 §8`` 게이트 #2 통과 및
``enable_vision_classifier=True`` 설정 후에만 실제 구현체를 활성화한다.

Phase 00 수리 사항 (D1):
    기존 ``detect_label_region(...) -> BoundingBox`` 는 라벨에서 단일 영역만
    반환하는 시그니처였다. 사용자 의도는 "브랜드 / 성분표 / 용법 / 주의사항 등
    각 영역의 bbox"이므로, ``detect_regions(...) -> list[LabeledBoundingBox]``
    로 다중 영역 + 종류 라벨을 반환하도록 변경한다.

Reference:
    /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.1 D1
    /Users/yeong/.claude/plans/lemon-track-b/phase-00-bootstrap.md Step 4
    docs/17-image-collection-consent-plan.md §7, §9
    docs/15-regulated-feature-feasibility-and-compliance-plan.md §3.2~3.3
    backend/CLAUDE.md Pattern 3
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

LabelRegionKind = Literal[
    "brand",
    "ingredients_table",
    "dosage",
    "warning",
    "expiry",
    "other",
]
"""라벨 영역의 의미 분류.

- ``brand``: 제품명 / 제조사 영역.
- ``ingredients_table``: 영양정보 / 함량 표.
- ``dosage``: 1회 제공량 / 섭취 방법.
- ``warning``: 주의사항 / 보관 방법.
- ``expiry``: 유통기한 / 제조일자.
- ``other``: 위 분류에 들지 않는 텍스트 블록.
"""


class VisionError(RuntimeError):
    """비전 어댑터 호출 실패 또는 입력 검증 실패를 나타낸다."""


@dataclass(frozen=True)
class LabeledBoundingBox:
    """의미 라벨이 부여된 라벨 영역 경계 상자.

    좌표계는 입력 이미지 픽셀 기준이며 원점은 좌상단이다.

    Attributes:
        x: 좌상단 x 좌표(px).
        y: 좌상단 y 좌표(px).
        width: 영역 너비(px, 양수).
        height: 영역 높이(px, 양수).
        confidence: 검출 신뢰도(0.0~1.0).
        kind: ``LabelRegionKind`` 중 하나의 의미 라벨.
    """

    x: int
    y: int
    width: int
    height: int
    confidence: float
    kind: LabelRegionKind


class VisionAdapter(ABC):
    """비전 어댑터 추상 인터페이스.

    영양제 라벨 영역 검출만 담당한다. 호출처는 본 어댑터로부터 받은
    ``LabeledBoundingBox`` 리스트를 OCR 입력 전처리(크롭)에만 사용해야 하며,
    의료 판단 출력에 직접 사용해서는 안 된다.

    Examples:
        >>> from src.vision.yolo import YoloLabelDetector
        >>> detector: VisionAdapter = YoloLabelDetector()  # doctest: +SKIP
        >>> regions = await detector.detect_regions(image_bytes)  # doctest: +SKIP
        >>> [r.kind for r in regions]                              # doctest: +SKIP
        ['brand', 'ingredients_table', 'dosage']
    """

    @abstractmethod
    async def detect_regions(self, image_bytes: bytes) -> list[LabeledBoundingBox]:
        """이미지에서 영양제 라벨의 의미 단위 영역을 모두 검출한다.

        Args:
            image_bytes: 이미지 원본 바이트(JPEG/PNG, 10MB 이하).

        Returns:
            검출된 ``LabeledBoundingBox`` 리스트. 0개 검출도 정상 반환값이며,
            호출처가 빈 리스트를 처리해야 한다.

        Raises:
            VisionError: 호출 자체 실패 또는 입력 검증 실패 시.
        """
        ...
