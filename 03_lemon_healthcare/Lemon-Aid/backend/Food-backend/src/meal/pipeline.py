"""mock 식단 인식 pipeline 1차 조립.

dev-guide 16 §"입력 방식" + A2.5 정책을 따른다. YOLO/GCV mock 어댑터,
fusion 엔진, portion 추정기를 조립하여 `image_bytes` 또는 `fixture_key`를
입력으로 받아 `RecognizedMeal`을 반환한다.

A2.5 정책:
    - 하위 컴포넌트는 모두 생성자 의존성 주입으로 받는다 (파일 I/O 없음).
    - `food_code`는 None을 유지한다 (A3 RDA matcher 책임).
    - OCR 텍스트는 토큰화·정규화 없이 fusion에 그대로 전달한다.
    - aliases mapping은 `MealFusionEngine` 생성 시 이미 주입된 것으로 본다 —
      pipeline에서 `food_aliases.json`을 재로딩하지 않는다.
    - 외부 입력(`default_serving_g`, `image_area`, `engine_name`,
      `fixture_key`)은 entry에서 `ValueError`로 가드한다.
    - 하위 어댑터의 `MealParseError`는 감싸지 않고 그대로 전파한다.
    - YOLO 결과가 비어도 정상 `RecognizedMeal(items=[])`를 반환한다.
    - `recognize_from_fixture_key`는 mock 테스트 편의용이며, 실 Beta
      어댑터(`ultralytics.YOLO`, Cloud Vision SDK)는 `*_by_key`를 지원하지
      않으므로 본 메서드 호출 시 `MealRecognitionError`로 실패한다.

Reference:
    docs/dev-guides/16-meal-recognition.md §"입력 방식"
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from src.meal.base import MealDetection, MealType, RecognizedMeal, RecognizedMealItem
from src.meal.exceptions import MealRecognitionError
from src.meal.fusion import MealFusionEngine
from src.meal.google_vision import GoogleVisionMealHintAdapter
from src.meal.portion_estimator import PortionEstimator
from src.meal.yolo_v8 import YoloV8MealDetector


@runtime_checkable
class _SupportsYoloByKey(Protocol):
    """fixture_key 직접 조회를 지원하는 YOLO 어댑터 Protocol.

    Mock 어댑터(`MockYoloV8MealDetector`)만 충족한다. 실 Beta
    `ultralytics.YOLO` 래퍼는 SHA256 lookup만 지원할 예정이므로 본 Protocol을
    충족하지 않는다.
    """

    def detect_by_key(self, fixture_key: str) -> list[MealDetection]: ...


@runtime_checkable
class _SupportsGcvByKey(Protocol):
    """fixture_key 직접 조회를 지원하는 GCV 어댑터 Protocol."""

    def extract_hints_by_key(self, fixture_key: str) -> list[MealDetection]: ...

    def extract_ocr_text_by_key(self, fixture_key: str) -> str: ...


class MealPipeline:
    """mock 식단 인식 pipeline 1차 조립.

    조립 순서: YOLO 탐지 → GCV hint 추출 → fusion 결합 → portion 보정 →
    `RecognizedMeal` 빌드. 두 entry 메서드(`recognize_from_image`,
    `recognize_from_fixture_key`)가 공유하는 후처리는 내부 헬퍼
    `_build_meal`에 모아 둔다.

    `recognize_from_image`는 실 어댑터 인터페이스(`detect(bytes)`,
    `extract_hints(bytes)`, `extract_ocr_text(bytes)`)만 사용하므로 Beta
    어댑터 swap이 가능하다. `recognize_from_fixture_key`는 어댑터가
    `*_by_key` Protocol을 충족할 때만 사용 가능한 mock 테스트 편의 메서드다.

    Examples:
        >>> pipeline = MealPipeline(
        ...     yolo_detector=MockYoloV8MealDetector(fixture_path),
        ...     gcv_adapter=MockGoogleVisionMealHintAdapter(fixture_path),
        ...     fusion_engine=MealFusionEngine(aliases=aliases),
        ...     portion_estimator=PortionEstimator(),
        ...     image_area=1280 * 720,
        ... )
        >>> meal = await pipeline.recognize_from_image(image_bytes)
    """

    def __init__(
        self,
        *,
        yolo_detector: YoloV8MealDetector,
        gcv_adapter: GoogleVisionMealHintAdapter,
        fusion_engine: MealFusionEngine,
        portion_estimator: PortionEstimator,
        image_area: float | None = None,
        default_serving_g: float = 100.0,
        engine_name: str = "mock_yolo_gcv_fusion_v1",
    ) -> None:
        """파이프라인 컴포넌트와 호출당 설정값을 받는다.

        Args:
            yolo_detector: YOLO 어댑터 (Mock 또는 Beta).
            gcv_adapter: GCV hint 어댑터 (Mock 또는 Beta).
            fusion_engine: aliases가 이미 주입된 fusion 엔진.
            portion_estimator: portion 보정기.
            image_area: 입력 이미지 면적 (픽셀 제곱). None이면 모든 item이
                portion fallback 경로를 탄다.
            default_serving_g: 호출당 단일 기본 1회 제공량 (g). A3 이후
                음식별 per-item으로 확장될 예정이며, 현 단계는 단일 값.
            engine_name: `RecognizedMeal.engine`에 들어갈 식별자.

        Raises:
            ValueError: `default_serving_g`<=0 이거나 `image_area`<=0 이거나
                `engine_name`이 빈 문자열인 경우.
        """
        if default_serving_g <= 0:
            raise ValueError(f"default_serving_g must be > 0, got {default_serving_g}")
        if image_area is not None and image_area <= 0:
            raise ValueError(f"image_area must be > 0, got {image_area}")
        if not engine_name:
            raise ValueError("engine_name must be non-empty")

        self._yolo = yolo_detector
        self._gcv = gcv_adapter
        self._fusion = fusion_engine
        self._portion = portion_estimator
        self._image_area = image_area
        self._default_serving_g = default_serving_g
        self._engine_name = engine_name

    async def recognize_from_image(
        self,
        image_bytes: bytes,
        *,
        meal_type: MealType = "lunch",
    ) -> RecognizedMeal:
        """image_bytes로 식단 인식 pipeline을 실행한다.

        실 Beta 어댑터에서도 그대로 동작하는 메서드. `raw_input`은
        `image_bytes`의 SHA256 hex digest로 들어간다 — 이미지 자체를 저장하지
        않으므로 audit / dedup용 식별자로 사용 가능.

        Args:
            image_bytes: 입력 이미지 원본 바이트.
            meal_type: 식사 종류 (`RecognizedMeal.meal_type`).

        Returns:
            `RecognizedMeal`. items가 비어 있어도 정상 인스턴스를 반환한다.

        Raises:
            MealApiError: 하위 어댑터 호출 실패 (Beta 구현).
            MealParseError: 하위 어댑터 fixture 파싱 실패.
        """
        sha256_hex = hashlib.sha256(image_bytes).hexdigest()
        yolo_detections = await self._yolo.detect(image_bytes)
        gcv_hints = await self._gcv.extract_hints(image_bytes)
        ocr_text = await self._gcv.extract_ocr_text(image_bytes)
        return self._build_meal(
            yolo_detections=yolo_detections,
            gcv_hints=gcv_hints,
            ocr_text=ocr_text,
            meal_type=meal_type,
            raw_input=sha256_hex,
        )

    async def recognize_from_fixture_key(
        self,
        fixture_key: str,
        *,
        meal_type: MealType = "lunch",
    ) -> RecognizedMeal:
        """fixture_key 기반 mock pipeline을 실행한다 (테스트 편의 메서드).

        실 Beta 어댑터는 `*_by_key`를 지원하지 않으므로 본 메서드는 mock 어댑터
        조합에서만 사용 가능하다. Mock 어댑터의 `_by_key` 메서드를 직접
        호출하므로 SHA256 lookup을 우회한다 — 실제 이미지 fixture 파일이
        없어도 fixture JSON 키만 알면 테스트할 수 있다.

        Args:
            fixture_key: fixture JSON의 최상위 키 (예: 파일명).
            meal_type: 식사 종류.

        Returns:
            `RecognizedMeal`. `raw_input`은 `fixture_key` 그대로.

        Raises:
            ValueError: `fixture_key`가 빈 문자열인 경우.
            MealRecognitionError: 주입된 어댑터가 `*_by_key` Protocol을
                충족하지 않는 경우 (Beta 어댑터로 본 메서드를 호출한 경우).
        """
        if not fixture_key:
            raise ValueError("fixture_key must be non-empty")
        if not isinstance(self._yolo, _SupportsYoloByKey):
            raise MealRecognitionError(
                "yolo_detector does not support detect_by_key; "
                "use a mock adapter or call recognize_from_image instead",
            )
        if not isinstance(self._gcv, _SupportsGcvByKey):
            raise MealRecognitionError(
                "gcv_adapter does not support *_by_key; "
                "use a mock adapter or call recognize_from_image instead",
            )
        yolo_detections = self._yolo.detect_by_key(fixture_key)
        gcv_hints = self._gcv.extract_hints_by_key(fixture_key)
        ocr_text = self._gcv.extract_ocr_text_by_key(fixture_key)
        return self._build_meal(
            yolo_detections=yolo_detections,
            gcv_hints=gcv_hints,
            ocr_text=ocr_text,
            meal_type=meal_type,
            raw_input=fixture_key,
        )

    def _build_meal(
        self,
        *,
        yolo_detections: list[MealDetection],
        gcv_hints: list[MealDetection],
        ocr_text: str,
        meal_type: MealType,
        raw_input: str,
    ) -> RecognizedMeal:
        """fusion + portion → RecognizedMeal 빌드 공통 경로.

        YOLO/GCV 호출 방식(`detect(bytes)` vs `detect_by_key`)과 무관한
        후처리만 담당한다. fusion이 빈 items를 반환해도 정상
        `RecognizedMeal`을 만든다.

        Args:
            yolo_detections: YOLO 어댑터 출력.
            gcv_hints: GCV 어댑터 출력.
            ocr_text: GCV OCR 원문 (fusion에 그대로 전달).
            meal_type: `RecognizedMeal.meal_type`.
            raw_input: `RecognizedMeal.raw_input` (SHA256 hex 또는 fixture_key).

        Returns:
            조립된 `RecognizedMeal`.
        """
        items: list[RecognizedMealItem] = self._fusion.fuse(
            yolo_detections=yolo_detections,
            gcv_hints=gcv_hints,
            ocr_text=ocr_text,
        )
        items = self._portion.estimate_items(
            items,
            detections=yolo_detections,
            image_area=self._image_area,
            default_serving_g=self._default_serving_g,
        )
        return RecognizedMeal(
            meal_type=meal_type,
            items=items,
            engine=self._engine_name,
            raw_input=raw_input,
        )
