"""Google Cloud Vision 음식 hint 어댑터 (MVP Mock + Beta ABC).

dev-guide 16 §"2. google_vision.py" 명세와 A2.2 hint 매핑 정책에 따라
GCV의 label/object hint를 `MealDetection` 후보로, OCR 원문을 별도 메서드로
노출한다. label 번역, food_aliases 매칭, OCR 토큰화, 신뢰도 3구간 정책 적용은
본 모듈에서 하지 않으며 fusion(A2.3) 이후 단계의 책임이다.

A2.2 정책 요약:
    - label은 그대로 `MealDetection.class_name_ko`에 넣는다 (번역 X).
    - label hint의 bbox=None, confidence=`_DEFAULT_LABEL_CONFIDENCE`.
    - object hint에 `bbox_xyxy`가 있으면 `BoundingBox`로 변환.
    - OCR 원문은 별도 메서드(`extract_ocr_text`)로만 노출.

Reference:
    docs/dev-guides/16-meal-recognition.md §"구현 명세 / 2. google_vision.py"
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

_DEFAULT_LABEL_CONFIDENCE = 0.5
"""Mock GCV label hint의 기본 신뢰도.

실 GCV는 `LabelAnnotation.score`를 반환하지만 MVP mock fixture에는 score가
없다. 신뢰도 3구간 분류는 fusion 단계에서 YOLO confidence 기준으로
이뤄지므로, 본 값은 0.70 자동 후보 임계점 아래의 중립값으로 두어 GCV
detection이 YOLO를 덮지 않도록 한다.
"""


class _GcvObjectHintRaw(BaseModel):
    """gcv_hints.objects 항목 내부 표현 (선택)."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    score: float = Field(default=_DEFAULT_LABEL_CONFIDENCE, ge=0.0, le=1.0)
    bbox_xyxy: list[float] | None = Field(
        default=None,
        min_length=_BBOX_COORD_COUNT,
        max_length=_BBOX_COORD_COUNT,
    )


class _GcvHintsRaw(BaseModel):
    """gcv_hints 객체 내부 표현."""

    model_config = ConfigDict(extra="ignore")

    labels: list[str] = Field(default_factory=list)
    ocr_text: str = Field(default="")
    objects: list[_GcvObjectHintRaw] = Field(default_factory=list)


class _GcvEntryRaw(BaseModel):
    """mock_predictions.json의 단일 entry 내부 표현 (GCV 부분만).

    `detections`(YOLO) 필드는 본 모듈에서 무시한다.
    """

    model_config = ConfigDict(extra="ignore")

    gcv_hints: _GcvHintsRaw = Field(default_factory=_GcvHintsRaw)


_FIXTURE_ADAPTER: TypeAdapter[dict[str, _GcvEntryRaw]] = TypeAdapter(dict[str, _GcvEntryRaw])
"""fixture JSON 루트 타입 검증 adapter."""


class GoogleVisionMealHintAdapter(ABC):
    """Google Cloud Vision hint 어댑터 추상 인터페이스.

    실 구현(Beta)은 Cloud Vision SDK의 `label_detection` /
    `text_detection` / `localized_object_detection`을 호출하고, Mock 구현
    (MVP)은 fixture JSON에서 사전 정의된 hint를 조회한다. 양쪽 모두 본
    ABC를 충족하므로 fusion 이후 단계는 구현 차이를 알 필요가 없다.

    label/object hint는 `MealDetection`(source="google_vision")으로 노출하고,
    OCR 원문은 별도 메서드로 분리한다. GCV는 음식 확정의 주 엔진이 아니다 —
    label 번역, alias 매칭, OCR 토큰화는 fusion 또는 후속 단계의 책임이다.

    Examples:
        >>> adapter: GoogleVisionMealHintAdapter = MockGoogleVisionMealHintAdapter(fixture_path)
        >>> hints = await adapter.extract_hints(image_bytes)
        >>> ocr = await adapter.extract_ocr_text(image_bytes)
    """

    @abstractmethod
    async def extract_hints(self, image_bytes: bytes) -> list[MealDetection]:
        """이미지에서 GCV label/object hint를 후보로 추출한다.

        Args:
            image_bytes: 입력 이미지 원본 바이트.

        Returns:
            label/object hint를 표현하는 `MealDetection` 리스트.
            label hint는 bbox=None, object hint는 가능 시 bbox 포함.
            모든 항목의 source는 "google_vision".

        Raises:
            MealApiError: 외부 GCV 호출이 실패한 경우 (Beta 구현에서 사용).
        """
        ...

    @abstractmethod
    async def extract_ocr_text(self, image_bytes: bytes) -> str:
        """이미지에서 OCR 원문 텍스트를 추출한다.

        토큰화·정규화·alias 매칭은 본 메서드에서 수행하지 않는다.

        Args:
            image_bytes: 입력 이미지 원본 바이트.

        Returns:
            OCR 원문 전체. 텍스트가 없거나 미인식 시 빈 문자열.

        Raises:
            MealApiError: 외부 GCV 호출이 실패한 경우 (Beta 구현에서 사용).
        """
        ...


class MockGoogleVisionMealHintAdapter(GoogleVisionMealHintAdapter):
    """fixture JSON 기반 MVP용 mock GCV hint 어댑터.

    `extract_hints(image_bytes)` / `extract_ocr_text(image_bytes)`는
    `SHA256(image_bytes)`를 fixture key로 사용한다. fixture JSON의 키는
    SHA256 또는 임의의 식별자(예: 파일명)일 수 있으며, `_by_key` 메서드는
    테스트와 파이프라인이 식별자를 직접 전달할 때 사용한다.

    Examples:
        >>> from pathlib import Path
        >>> adapter = MockGoogleVisionMealHintAdapter(
        ...     Path("data/meal_vision/mock_predictions.json")
        ... )
        >>> [d.class_name_ko for d in adapter.extract_hints_by_key("sample_bibimbap_solo.jpg")]
        ['bibimbap', 'rice', 'vegetable', 'korean food']
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
            self._fixtures: dict[str, _GcvEntryRaw] = _FIXTURE_ADAPTER.validate_json(raw)
        except ValidationError as e:
            raise MealParseError(f"fixture JSON invalid: {fixture_path}") from e

    @property
    def available_keys(self) -> list[str]:
        """fixture에 등록된 키의 정렬된 리스트."""
        return sorted(self._fixtures.keys())

    async def extract_hints(self, image_bytes: bytes) -> list[MealDetection]:
        """`SHA256(image_bytes)`로 hint를 조회한다.

        Args:
            image_bytes: 입력 이미지 원본 바이트.

        Returns:
            label/object hint의 `MealDetection` 리스트. 키가 없으면 빈 리스트.
        """
        key = hashlib.sha256(image_bytes).hexdigest()
        return self.extract_hints_by_key(key)

    async def extract_ocr_text(self, image_bytes: bytes) -> str:
        """`SHA256(image_bytes)`로 OCR 원문을 조회한다.

        Args:
            image_bytes: 입력 이미지 원본 바이트.

        Returns:
            OCR 원문 전체. 키가 없거나 텍스트가 없으면 빈 문자열.
        """
        key = hashlib.sha256(image_bytes).hexdigest()
        return self.extract_ocr_text_by_key(key)

    def extract_hints_by_key(self, fixture_key: str) -> list[MealDetection]:
        """fixture_key로 hint를 직접 조회한다.

        실 구현(Cloud Vision SDK)에서는 사용되지 않으며, Mock 단계에서
        image_bytes가 아닌 식별자(예: 파일명)로 fixture를 찾을 때 사용한다.

        Args:
            fixture_key: fixture JSON의 최상위 키.

        Returns:
            label/object hint의 `MealDetection` 리스트. 키가 없으면 빈 리스트.
        """
        entry = self._fixtures.get(fixture_key)
        if entry is None:
            return []
        results: list[MealDetection] = []
        for label in entry.gcv_hints.labels:
            if not label.strip():
                continue
            results.append(
                MealDetection(
                    class_name_ko=label,
                    confidence=_DEFAULT_LABEL_CONFIDENCE,
                    bbox=None,
                    source="google_vision",
                )
            )
        for obj in entry.gcv_hints.objects:
            bbox: BoundingBox | None = None
            if obj.bbox_xyxy is not None and len(obj.bbox_xyxy) == _BBOX_COORD_COUNT:
                bbox = BoundingBox(
                    x_min=obj.bbox_xyxy[0],
                    y_min=obj.bbox_xyxy[1],
                    x_max=obj.bbox_xyxy[2],
                    y_max=obj.bbox_xyxy[3],
                )
            results.append(
                MealDetection(
                    class_name_ko=obj.name,
                    confidence=obj.score,
                    bbox=bbox,
                    source="google_vision",
                )
            )
        return results

    def extract_ocr_text_by_key(self, fixture_key: str) -> str:
        """fixture_key로 OCR 원문을 직접 조회한다.

        Args:
            fixture_key: fixture JSON의 최상위 키.

        Returns:
            OCR 원문 전체. 키가 없거나 텍스트가 없으면 빈 문자열.
        """
        entry = self._fixtures.get(fixture_key)
        if entry is None:
            return ""
        return entry.gcv_hints.ocr_text
