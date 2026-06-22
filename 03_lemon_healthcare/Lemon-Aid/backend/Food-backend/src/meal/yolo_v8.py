"""YOLOv8 음식 탐지 어댑터 (MVP Mock + Beta ABC).

dev-guide 16 §"3. yolo_v8.py" 명세를 따른다. MVP는 fixture JSON에서 사전
계산된 detection을 조회하고, Beta는 ultralytics.YOLO 모델을 호출한다.
양쪽 모두 동일 ABC(`YoloV8MealDetector`)를 충족하므로 fusion 이후 단계는
구현 차이를 알 필요가 없다.

Reference:
    docs/dev-guides/16-meal-recognition.md §"구현 명세 / 3. yolo_v8.py"
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from src.meal.base import BoundingBox, MealDetection
from src.meal.exceptions import MealParseError

_BBOX_COORD_COUNT = 4
"""bbox_xyxy는 [x_min, y_min, x_max, y_max] 4-tuple."""


class _MockDetectionRaw(BaseModel):
    """mock_predictions.json의 detection 항목 내부 표현.

    fixture 스키마 검증 전용 DTO이며, public DTO인 `MealDetection`과 분리한다.
    `class_id` 등 사용하지 않는 필드는 `extra="ignore"`로 무시한다.
    """

    model_config = ConfigDict(extra="ignore")

    class_name_ko: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox_xyxy: list[float] = Field(..., min_length=_BBOX_COORD_COUNT, max_length=_BBOX_COORD_COUNT)


class _MockEntryRaw(BaseModel):
    """mock_predictions.json의 단일 entry 내부 표현 (YOLO 부분만).

    `gcv_hints` 필드는 GCV mock(A2.2)에서 별도로 파싱하므로 본 DTO에서는 무시한다.
    """

    model_config = ConfigDict(extra="ignore")

    detections: list[_MockDetectionRaw] = Field(default_factory=list)


_FIXTURE_ADAPTER: TypeAdapter[dict[str, _MockEntryRaw]] = TypeAdapter(dict[str, _MockEntryRaw])
"""fixture JSON 루트 타입 검증 adapter."""


class YoloV8MealDetector(ABC):
    """음식 탐지 어댑터 추상 인터페이스.

    실 구현(Beta)은 `ultralytics.YOLO` 모델을 호출하고, Mock 구현(MVP)은
    fixture JSON에서 사전 계산된 detection을 조회한다. 양쪽 모두 본 ABC를
    충족하므로 호출처는 구현 차이를 알 필요가 없다.

    Examples:
        >>> detector: YoloV8MealDetector = MockYoloV8MealDetector(fixture_path)
        >>> detections = await detector.detect(image_bytes)
    """

    @abstractmethod
    async def detect(
        self,
        image_bytes: bytes,
        *,
        min_confidence: float = 0.0,
    ) -> list[MealDetection]:
        """이미지 바이트에서 음식 후보를 탐지한다.

        Args:
            image_bytes: 입력 이미지 원본 바이트.
            min_confidence: 사전 필터링 최소 신뢰도 (0.0~1.0). 기본값 0.0은
                모든 detection을 반환한다. 신뢰도 정책 3구간(≥0.70 자동 후보 /
                0.40~0.69 검토 필요 / <0.40 보관만) 분류는 fusion 단계에서
                적용되며, 본 인자는 ultralytics `conf`와 동일한 의미의 옵셔널
                사전 필터다.

        Returns:
            탐지된 `MealDetection` 리스트. 매칭이 없으면 빈 리스트.

        Raises:
            MealApiError: 외부 모델 호출이 실패한 경우 (Beta 구현에서 사용).
        """
        ...


class MockYoloV8MealDetector(YoloV8MealDetector):
    """fixture JSON 기반 MVP용 mock 탐지기.

    `detect(image_bytes)`는 `SHA256(image_bytes)`를 fixture key로 사용한다.
    fixture JSON의 키는 SHA256 또는 임의의 식별자(예: 파일명)일 수 있으며,
    `detect_by_key`는 테스트와 파이프라인이 식별자를 직접 전달할 때 사용한다.

    Examples:
        >>> from pathlib import Path
        >>> detector = MockYoloV8MealDetector(Path("data/meal_vision/mock_predictions.json"))
        >>> [d.class_name_ko for d in detector.detect_by_key("sample_bibimbap_solo.jpg")]
        ['비빔밥']
    """

    def __init__(self, fixture_path: Path) -> None:
        """fixture JSON 파일을 로드한다.

        Args:
            fixture_path: fixture JSON 경로.

        Raises:
            MealParseError: 파일을 읽을 수 없거나 스키마 검증이 실패한 경우.
        """
        try:
            raw = fixture_path.read_text(encoding="utf-8")
        except OSError as e:
            raise MealParseError(f"fixture file not readable: {fixture_path}") from e
        try:
            self._fixtures: dict[str, _MockEntryRaw] = _FIXTURE_ADAPTER.validate_json(raw)
        except ValidationError as e:
            raise MealParseError(f"fixture JSON invalid: {fixture_path}") from e

    @property
    def available_keys(self) -> list[str]:
        """fixture에 등록된 키의 정렬된 리스트."""
        return sorted(self._fixtures.keys())

    async def detect(
        self,
        image_bytes: bytes,
        *,
        min_confidence: float = 0.0,
    ) -> list[MealDetection]:
        """`SHA256(image_bytes)`로 fixture를 조회한다.

        Args:
            image_bytes: 입력 이미지 원본 바이트.
            min_confidence: 사전 필터링 최소 신뢰도.

        Returns:
            탐지된 `MealDetection` 리스트. 키가 없거나 detection이 없으면 빈 리스트.
        """
        key = hashlib.sha256(image_bytes).hexdigest()
        return self.detect_by_key(key, min_confidence=min_confidence)

    def detect_by_key(
        self,
        fixture_key: str,
        *,
        min_confidence: float = 0.0,
    ) -> list[MealDetection]:
        """fixture_key로 직접 조회한다.

        실 구현(`ultralytics.YOLO`)에서는 사용되지 않으며, Mock 단계에서
        image_bytes가 아닌 식별자(예: 파일명)로 fixture를 찾을 때 사용한다.

        Args:
            fixture_key: fixture JSON의 최상위 키.
            min_confidence: 사전 필터링 최소 신뢰도.

        Returns:
            탐지된 `MealDetection` 리스트. 키가 없으면 빈 리스트.
        """
        entry = self._fixtures.get(fixture_key)
        if entry is None:
            return []
        return [
            MealDetection(
                class_name_ko=d.class_name_ko,
                confidence=d.confidence,
                bbox=BoundingBox(
                    x_min=d.bbox_xyxy[0],
                    y_min=d.bbox_xyxy[1],
                    x_max=d.bbox_xyxy[2],
                    y_max=d.bbox_xyxy[3],
                ),
                source="yolo_v8",
            )
            for d in entry.detections
            if d.confidence >= min_confidence
        ]
