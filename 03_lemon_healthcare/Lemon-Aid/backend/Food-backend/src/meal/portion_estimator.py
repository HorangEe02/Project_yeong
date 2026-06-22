"""bbox 면적 비율 기반 portion 추정기.

dev-guide 16 §"5. portion_estimator.py" 명세를 따른다. fusion(A2.3)이
산출한 `RecognizedMealItem`의 `estimated_grams` / `estimated_amount` /
`portion_confidence`를 이미지 대비 bbox 면적 비율로 보정한다.

A2.4 정책:
    - bbox 또는 image_area가 없으면 `default_serving_g`를 그대로 사용 (fallback).
    - `image_area` ≤ 0은 `ValueError`.
    - 비율 = `bbox.area / image_area`:
        - < 0.15 → x0.7, "소량 추정"
        - 0.15 ~ 0.45 → x1.0, "1인분 추정"
        - > 0.45 → x1.2, "많음 추정"
    - bbox 보정 시 `portion_confidence=0.6`, fallback은 0.3.
    - `food_code`, `confidence`, `sources`, `alternatives`, `needs_user_review`는
      변경하지 않는다. PortionEstimator는 `estimated_grams` /
      `estimated_amount` / `portion_confidence` 3필드만 갱신한다.

본 모듈은 파일 I/O 없음 — 생성자 인자 없음. `food_aliases.json`,
`korean_foods.csv` 등 외부 데이터는 호출자(파이프라인)가 lookup해서
`default_serving_g`로 전달한다. fusion / pipeline / rda_matcher를 import하지
않는다.

본 로직은 MVP heuristic이며, 실제 중량 추정 모델은 Future/Beta 이후 도입.

Reference:
    docs/dev-guides/16-meal-recognition.md §"구현 명세 / 5. portion_estimator.py"
"""

from __future__ import annotations

from src.meal.base import BoundingBox, MealDetection, RecognizedMealItem

_RATIO_SMALL_THRESHOLD = 0.15
"""bbox.area / image_area < 본 값이면 '소량'(x0.7) 구간."""

_RATIO_LARGE_THRESHOLD = 0.45
"""bbox.area / image_area > 본 값이면 '많음'(x1.2) 구간."""

_MULTIPLIER_SMALL = 0.7
_MULTIPLIER_MEDIUM = 1.0
_MULTIPLIER_LARGE = 1.2

_FALLBACK_PORTION_CONFIDENCE = 0.3
"""bbox 또는 image_area가 없을 때 portion_confidence."""

_BBOX_PORTION_CONFIDENCE = 0.6
"""bbox 면적 비율 보정이 적용됐을 때 portion_confidence."""

_AMOUNT_SMALL = "소량 추정"
_AMOUNT_MEDIUM = "1인분 추정"
_AMOUNT_LARGE = "많음 추정"


class PortionEstimator:
    """bbox 면적 비율로 `RecognizedMealItem`의 portion 정보를 보정한다.

    상태 없음 — 생성자는 인자를 받지 않으며, 파일 I/O를 수행하지 않는다.
    `food_aliases.json` / `korean_foods.csv` 등 외부 데이터 lookup은 호출자가
    수행하고 `default_serving_g`로 주입한다.

    PortionEstimator는 `estimated_grams` / `estimated_amount` /
    `portion_confidence` 3필드만 갱신하고, 나머지 6필드(name_ko, food_code,
    confidence, needs_user_review, sources, alternatives)는 `model_copy`로
    그대로 보존한다.

    Examples:
        >>> estimator = PortionEstimator()
        >>> updated = estimator.estimate_item(
        ...     item,
        ...     bbox=detection.bbox,
        ...     image_area=image_w * image_h,
        ... )
    """

    def estimate_item(
        self,
        item: RecognizedMealItem,
        *,
        bbox: BoundingBox | None,
        image_area: float | None = None,
        default_serving_g: float = 100.0,
    ) -> RecognizedMealItem:
        """단일 item의 portion 정보를 갱신한 새 인스턴스를 반환한다.

        Args:
            item: 갱신할 `RecognizedMealItem` (frozen, 입력은 변경되지 않음).
            bbox: 음식 영역 bbox. None이면 fallback.
            image_area: 전체 이미지 면적 (픽셀 제곱). None이면 fallback.
            default_serving_g: 기본 1회 제공량 (g). A3 이후 음식별 per-item으로
                확장될 예정이며, 현 단계는 호출당 단일 값.

        Returns:
            `estimated_grams` / `estimated_amount` / `portion_confidence`만
            갱신된 새 `RecognizedMealItem`.

        Raises:
            ValueError: `default_serving_g`가 0 이하이거나 `image_area`가 0
                이하인 경우. `model_copy(update=...)`가 Pydantic validator를
                재실행하지 않아 `estimated_grams`의 `gt=0` 계약이 우회될 수
                있으므로 명시적으로 차단한다.
        """
        if default_serving_g <= 0:
            raise ValueError(f"default_serving_g must be > 0, got {default_serving_g}")
        if image_area is not None and image_area <= 0:
            raise ValueError(f"image_area must be > 0, got {image_area}")

        if bbox is None or image_area is None:
            return item.model_copy(
                update={
                    "estimated_grams": default_serving_g,
                    "estimated_amount": _AMOUNT_MEDIUM,
                    "portion_confidence": _FALLBACK_PORTION_CONFIDENCE,
                }
            )

        ratio = bbox.area / image_area
        if ratio < _RATIO_SMALL_THRESHOLD:
            multiplier = _MULTIPLIER_SMALL
            amount = _AMOUNT_SMALL
        elif ratio > _RATIO_LARGE_THRESHOLD:
            multiplier = _MULTIPLIER_LARGE
            amount = _AMOUNT_LARGE
        else:
            multiplier = _MULTIPLIER_MEDIUM
            amount = _AMOUNT_MEDIUM

        return item.model_copy(
            update={
                "estimated_grams": default_serving_g * multiplier,
                "estimated_amount": amount,
                "portion_confidence": _BBOX_PORTION_CONFIDENCE,
            }
        )

    def estimate_items(
        self,
        items: list[RecognizedMealItem],
        *,
        detections: list[MealDetection],
        image_area: float | None = None,
        default_serving_g: float = 100.0,
    ) -> list[RecognizedMealItem]:
        """여러 item을 일괄 추정한다.

        각 `item.name_ko`와 같은 `class_name_ko`를 가진 첫 번째 detection의
        bbox를 사용해 보정한다. 매칭되는 detection이 없거나 매칭된 detection의
        bbox가 None이면 fallback 처리한다. `item.alternatives`는 fusion이
        결정한 비대표 detection이므로 본 단계에서 변경하지 않는다 (model_copy로
        자동 보존).

        Args:
            items: 갱신할 item 리스트. 빈 리스트면 빈 리스트 반환.
            detections: `name_ko` 매칭에 사용할 detection 리스트.
            image_area: 전체 이미지 면적. None이면 모든 item이 fallback.
            default_serving_g: 모든 item에 uniform하게 쓰일 기본 1회 제공량.

        Returns:
            보정된 `RecognizedMealItem` 리스트 (입력 순서 보존).

        Raises:
            ValueError: `default_serving_g`가 0 이하이거나 `image_area`가 0
                이하인 경우. `estimate_item` 호출 시 첫 번째 위반에서 전파된다.
        """
        return [
            self.estimate_item(
                item,
                bbox=self._find_first_bbox(item.name_ko, detections),
                image_area=image_area,
                default_serving_g=default_serving_g,
            )
            for item in items
        ]

    @staticmethod
    def _find_first_bbox(
        name_ko: str,
        detections: list[MealDetection],
    ) -> BoundingBox | None:
        """이름이 일치하는 첫 번째 detection의 bbox를 반환한다.

        다중 bbox 대표 선정은 A2.3 fusion에서 이미 끝난 것으로 보고, 본
        단계에서는 동일 이름이 여러 개여도 첫 번째 detection을 사용한다.
        aliases / food_code 매칭은 본 단계 책임이 아니다.

        Args:
            name_ko: item의 한국어 음식명.
            detections: 매칭 후보.

        Returns:
            첫 번째 매칭 detection의 bbox. 매칭이 없거나 그 detection의 bbox가
            `None`이면 `None`.
        """
        for det in detections:
            if det.class_name_ko == name_ko:
                return det.bbox
        return None
