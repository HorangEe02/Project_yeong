"""MealPipeline 1차 조립 단위 테스트.

dev-guide 16 §"입력 방식"과 A2.5 조립 정책을 검증한다.

검증 범위:
    - 생성자 input validation (default_serving_g, image_area, engine_name).
    - recognize_from_image: SHA256 hex raw_input, 모든 하위 메서드 호출.
    - recognize_from_fixture_key: fixture_key raw_input, *_by_key 사용.
    - fusion + portion 결과 RecognizedMeal로 조립.
    - OCR 텍스트는 fusion에 그대로 전달.
    - food_code는 None 유지 (A3 RDA matcher 책임).
    - MealParseError 무손상 전파.
    - 모듈 구조: rda_matcher / text_parser / FastAPI / ml 미참조.

Reference:
    docs/dev-guides/16-meal-recognition.md
    docs/superpowers/plans/2026-05-11-meal-recognition-gcv-yolov8.md §"A2"
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest
from src.meal import pipeline as pipeline_module
from src.meal.base import MealDetection, RecognizedMeal, RecognizedMealItem
from src.meal.exceptions import MealParseError, MealRecognitionError
from src.meal.fusion import MealFusionEngine
from src.meal.google_vision import (
    GoogleVisionMealHintAdapter,
    MockGoogleVisionMealHintAdapter,
)
from src.meal.pipeline import MealPipeline
from src.meal.portion_estimator import PortionEstimator
from src.meal.yolo_v8 import MockYoloV8MealDetector, YoloV8MealDetector

REPO_ROOT = Path(__file__).resolve().parents[5]
"""tests/unit/meal/test_pipeline.py → 5단계 위가 repo root."""

MOCK_FIXTURES = REPO_ROOT / "data" / "meal_vision" / "mock_predictions.json"

BIBIMBAP_SOLO_KEY = "sample_bibimbap_solo.jpg"

IMAGE_AREA_TEST = 10_000.0
CUSTOM_ENGINE_NAME = "test_engine_v1"

ALIASES_WITH_GCV_BRIDGE: dict[str, str] = {
    "비빔밥": "F003",
    "bibimbap": "F003",
}
"""테스트용 aliases: 영문 GCV 라벨을 한국어 YOLO 이름과 같은 food_code로."""

ALIASES_REAL_PARTIAL: dict[str, str] = {
    "비빔밥": "F003",
    "공기밥": "F001",
    "김치찌개": "F009",
}
"""실 food_aliases.json과 같은 한국어만 매핑 — GCV 영문 라벨은 orphan."""


def _build_real_pipeline(
    *,
    aliases: dict[str, str] | None = None,
    image_area: float | None = IMAGE_AREA_TEST,
    engine_name: str = CUSTOM_ENGINE_NAME,
) -> MealPipeline:
    """A2.1~A2.4 실 mock 구현체로 조립된 pipeline."""
    return MealPipeline(
        yolo_detector=MockYoloV8MealDetector(MOCK_FIXTURES),
        gcv_adapter=MockGoogleVisionMealHintAdapter(MOCK_FIXTURES),
        fusion_engine=MealFusionEngine(aliases=aliases),
        portion_estimator=PortionEstimator(),
        image_area=image_area,
        engine_name=engine_name,
    )


# ── Fakes for unit isolation ─────────────────────────────────────────────


class _EmptyYoloDetector(YoloV8MealDetector):
    """detect → 빈 리스트. *_by_key 없음."""

    async def detect(
        self, image_bytes: bytes, *, min_confidence: float = 0.0
    ) -> list[MealDetection]:
        del image_bytes, min_confidence
        return []


class _EmptyGcvAdapter(GoogleVisionMealHintAdapter):
    """extract_hints → [], extract_ocr_text → ''. *_by_key 없음."""

    async def extract_hints(self, image_bytes: bytes) -> list[MealDetection]:
        del image_bytes
        return []

    async def extract_ocr_text(self, image_bytes: bytes) -> str:
        del image_bytes
        return ""


class _RaisingYoloDetector(YoloV8MealDetector):
    """모든 호출에서 MealParseError."""

    async def detect(
        self, image_bytes: bytes, *, min_confidence: float = 0.0
    ) -> list[MealDetection]:
        del image_bytes, min_confidence
        raise MealParseError("yolo parse error (test)")


class _RaisingGcvAdapter(GoogleVisionMealHintAdapter):
    """extract_hints에서 MealParseError."""

    async def extract_hints(self, image_bytes: bytes) -> list[MealDetection]:
        del image_bytes
        raise MealParseError("gcv parse error (test)")

    async def extract_ocr_text(self, image_bytes: bytes) -> str:
        del image_bytes
        return ""


class _SpyYoloDetector(YoloV8MealDetector):
    """detect 호출 횟수와 인자를 기록."""

    def __init__(self) -> None:
        self.detect_calls = 0
        self.last_image_bytes: bytes | None = None

    async def detect(
        self, image_bytes: bytes, *, min_confidence: float = 0.0
    ) -> list[MealDetection]:
        del min_confidence
        self.detect_calls += 1
        self.last_image_bytes = image_bytes
        return []


class _SpyGcvAdapter(GoogleVisionMealHintAdapter):
    """hint/OCR 호출 기록. OCR은 고정 문자열 반환."""

    def __init__(self, ocr_value: str = "테이블 메뉴: 비빔밥") -> None:
        self.hints_calls = 0
        self.ocr_calls = 0
        self._ocr_value = ocr_value
        self.last_hints_image_bytes: bytes | None = None
        self.last_ocr_image_bytes: bytes | None = None

    async def extract_hints(self, image_bytes: bytes) -> list[MealDetection]:
        self.hints_calls += 1
        self.last_hints_image_bytes = image_bytes
        return []

    async def extract_ocr_text(self, image_bytes: bytes) -> str:
        self.ocr_calls += 1
        self.last_ocr_image_bytes = image_bytes
        return self._ocr_value


class _SpyFusion(MealFusionEngine):
    """fuse 호출 인자(특히 ocr_text)를 기록."""

    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        super().__init__(aliases)
        self.fuse_calls = 0
        self.last_yolo: list[MealDetection] | None = None
        self.last_gcv: list[MealDetection] | None = None
        self.last_ocr: str | None = None

    def fuse(
        self,
        *,
        yolo_detections: list[MealDetection],
        gcv_hints: list[MealDetection],
        ocr_text: str = "",
    ) -> list[RecognizedMealItem]:
        self.fuse_calls += 1
        self.last_yolo = yolo_detections
        self.last_gcv = gcv_hints
        self.last_ocr = ocr_text
        return super().fuse(
            yolo_detections=yolo_detections,
            gcv_hints=gcv_hints,
            ocr_text=ocr_text,
        )


# ── Tests ────────────────────────────────────────────────────────────────


class TestConstruction:
    """생성자 input validation."""

    def test_default_serving_zero_raises(self) -> None:
        """default_serving_g=0 → ValueError."""
        with pytest.raises(ValueError, match="default_serving_g"):
            MealPipeline(
                yolo_detector=_EmptyYoloDetector(),
                gcv_adapter=_EmptyGcvAdapter(),
                fusion_engine=MealFusionEngine(),
                portion_estimator=PortionEstimator(),
                default_serving_g=0.0,
            )

    def test_default_serving_negative_raises(self) -> None:
        """default_serving_g<0 → ValueError."""
        with pytest.raises(ValueError, match="default_serving_g"):
            MealPipeline(
                yolo_detector=_EmptyYoloDetector(),
                gcv_adapter=_EmptyGcvAdapter(),
                fusion_engine=MealFusionEngine(),
                portion_estimator=PortionEstimator(),
                default_serving_g=-1.0,
            )

    def test_image_area_zero_raises(self) -> None:
        """image_area=0 → ValueError."""
        with pytest.raises(ValueError, match="image_area"):
            MealPipeline(
                yolo_detector=_EmptyYoloDetector(),
                gcv_adapter=_EmptyGcvAdapter(),
                fusion_engine=MealFusionEngine(),
                portion_estimator=PortionEstimator(),
                image_area=0,
            )

    def test_image_area_negative_raises(self) -> None:
        """image_area<0 → ValueError."""
        with pytest.raises(ValueError, match="image_area"):
            MealPipeline(
                yolo_detector=_EmptyYoloDetector(),
                gcv_adapter=_EmptyGcvAdapter(),
                fusion_engine=MealFusionEngine(),
                portion_estimator=PortionEstimator(),
                image_area=-100.0,
            )

    def test_image_area_none_allowed(self) -> None:
        """image_area=None은 허용 (모든 item이 fallback)."""
        pipeline = MealPipeline(
            yolo_detector=_EmptyYoloDetector(),
            gcv_adapter=_EmptyGcvAdapter(),
            fusion_engine=MealFusionEngine(),
            portion_estimator=PortionEstimator(),
            image_area=None,
        )
        assert pipeline is not None

    def test_engine_name_empty_raises(self) -> None:
        """engine_name="" → ValueError (DTO ValidationError 전에 명시 가드)."""
        with pytest.raises(ValueError, match="engine_name"):
            MealPipeline(
                yolo_detector=_EmptyYoloDetector(),
                gcv_adapter=_EmptyGcvAdapter(),
                fusion_engine=MealFusionEngine(),
                portion_estimator=PortionEstimator(),
                engine_name="",
            )


class TestRecognizeFromFixtureKey:
    """recognize_from_fixture_key 통합 동작 (real A2.1~A2.4 조합)."""

    async def test_returns_recognized_meal(self) -> None:
        """RecognizedMeal 인스턴스 반환."""
        pipeline = _build_real_pipeline()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        assert isinstance(meal, RecognizedMeal)

    async def test_raw_input_is_fixture_key(self) -> None:
        """raw_input에 fixture_key 그대로 보존."""
        pipeline = _build_real_pipeline()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        assert meal.raw_input == BIBIMBAP_SOLO_KEY

    async def test_engine_name_set(self) -> None:
        """engine에 engine_name 그대로 설정."""
        pipeline = _build_real_pipeline(engine_name="custom_engine")
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        assert meal.engine == "custom_engine"

    async def test_meal_type_preserved(self) -> None:
        """meal_type 인자가 그대로 결과에 반영."""
        pipeline = _build_real_pipeline()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY, meal_type="dinner")
        assert meal.meal_type == "dinner"

    async def test_items_include_yolo_food(self) -> None:
        """fixture의 YOLO 음식이 items에 등장."""
        pipeline = _build_real_pipeline()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        names = {item.name_ko for item in meal.items}
        assert "비빔밥" in names

    async def test_all_items_have_yolo_source(self) -> None:
        """모든 item은 yolo_v8를 source로 가진다."""
        pipeline = _build_real_pipeline()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        assert meal.items  # 빈 리스트가 아님 검증
        for item in meal.items:
            assert "yolo_v8" in item.sources

    async def test_food_code_remains_none(self) -> None:
        """food_code는 A2.5에서 채우지 않는다 (A3 RDA matcher 책임)."""
        pipeline = _build_real_pipeline()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        for item in meal.items:
            assert item.food_code is None

    async def test_portion_applied_to_items(self) -> None:
        """portion 추정이 적용되어 estimated_amount/portion_confidence가 채워진다."""
        pipeline = _build_real_pipeline()
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        for item in meal.items:
            assert item.estimated_amount  # non-empty (소량/1인분/많음 추정)
            assert item.portion_confidence > 0

    async def test_orphan_gcv_triggers_review(self) -> None:
        """real food_aliases와 같은 한국어만 매핑이면 GCV 영문 라벨은 orphan → review=True."""
        pipeline = _build_real_pipeline(aliases=ALIASES_REAL_PARTIAL)
        meal = await pipeline.recognize_from_fixture_key(BIBIMBAP_SOLO_KEY)
        assert meal.items
        top = max(meal.items, key=lambda i: i.confidence)
        assert top.needs_user_review is True


class TestGcvAliasBridge:
    """aliases mapping으로 GCV와 YOLO를 같은 food_code로 묶는 경로."""

    async def test_matched_gcv_label_adds_google_vision_source(self, tmp_path: Path) -> None:
        """custom fixture에 GCV 영문 라벨만 → aliases bridge로 매칭."""
        fixture_data = {
            "clean.jpg": {
                "detections": [
                    {
                        "class_id": 2,
                        "class_name_ko": "비빔밥",
                        "confidence": 0.94,
                        "bbox_xyxy": [10, 10, 90, 90],
                    }
                ],
                "gcv_hints": {
                    "labels": ["bibimbap"],
                    "ocr_text": "",
                },
            }
        }
        fx = tmp_path / "clean.json"
        fx.write_text(json.dumps(fixture_data, ensure_ascii=False), encoding="utf-8")
        pipeline = MealPipeline(
            yolo_detector=MockYoloV8MealDetector(fx),
            gcv_adapter=MockGoogleVisionMealHintAdapter(fx),
            fusion_engine=MealFusionEngine(aliases=ALIASES_WITH_GCV_BRIDGE),
            portion_estimator=PortionEstimator(),
            image_area=IMAGE_AREA_TEST,
        )
        meal = await pipeline.recognize_from_fixture_key("clean.jpg")
        assert len(meal.items) == 1
        item = meal.items[0]
        assert "google_vision" in item.sources
        assert "yolo_v8" in item.sources
        # 모든 GCV가 매칭되었으므로 orphan 없음 + conf 0.94 high → review=False
        assert item.needs_user_review is False


class TestEmptyYolo:
    """YOLO 결과 빈 경우 처리."""

    async def test_empty_yolo_returns_empty_items(self) -> None:
        """YOLO=[]이면 items=[]이지만 RecognizedMeal 자체는 유효."""
        pipeline = MealPipeline(
            yolo_detector=_EmptyYoloDetector(),
            gcv_adapter=_EmptyGcvAdapter(),
            fusion_engine=MealFusionEngine(),
            portion_estimator=PortionEstimator(),
        )
        meal = await pipeline.recognize_from_image(b"any bytes")
        assert meal.items == []
        assert meal.engine
        assert meal.raw_input


class TestRecognizeFromImage:
    """image_bytes 경로 동작."""

    async def test_raw_input_is_sha256_hex(self) -> None:
        """raw_input은 image_bytes의 SHA256 hex digest."""
        pipeline = _build_real_pipeline()
        image_bytes = b"some test bytes"
        expected_hash = hashlib.sha256(image_bytes).hexdigest()
        meal = await pipeline.recognize_from_image(image_bytes)
        assert meal.raw_input == expected_hash

    async def test_calls_all_three_adapter_methods(self) -> None:
        """detect / extract_hints / extract_ocr_text 모두 정확히 1회 호출."""
        spy_yolo = _SpyYoloDetector()
        spy_gcv = _SpyGcvAdapter()
        pipeline = MealPipeline(
            yolo_detector=spy_yolo,
            gcv_adapter=spy_gcv,
            fusion_engine=MealFusionEngine(),
            portion_estimator=PortionEstimator(),
        )
        await pipeline.recognize_from_image(b"x")
        assert spy_yolo.detect_calls == 1
        assert spy_gcv.hints_calls == 1
        assert spy_gcv.ocr_calls == 1

    async def test_all_adapters_receive_same_image_bytes(self) -> None:
        """동일한 image_bytes가 3개 어댑터에 모두 전달된다."""
        spy_yolo = _SpyYoloDetector()
        spy_gcv = _SpyGcvAdapter()
        pipeline = MealPipeline(
            yolo_detector=spy_yolo,
            gcv_adapter=spy_gcv,
            fusion_engine=MealFusionEngine(),
            portion_estimator=PortionEstimator(),
        )
        payload = b"specific payload"
        await pipeline.recognize_from_image(payload)
        assert spy_yolo.last_image_bytes == payload
        assert spy_gcv.last_hints_image_bytes == payload
        assert spy_gcv.last_ocr_image_bytes == payload


class TestOcrPassthrough:
    """OCR text가 fusion에 그대로 전달되는지."""

    async def test_ocr_text_forwarded_to_fusion(self) -> None:
        """GCV adapter의 OCR 결과가 fusion.fuse(ocr_text=...)에 그대로 전달."""
        ocr_value = "메뉴: 비빔밥 9,000원"
        spy_gcv = _SpyGcvAdapter(ocr_value=ocr_value)
        spy_fusion = _SpyFusion()
        pipeline = MealPipeline(
            yolo_detector=_EmptyYoloDetector(),
            gcv_adapter=spy_gcv,
            fusion_engine=spy_fusion,
            portion_estimator=PortionEstimator(),
        )
        await pipeline.recognize_from_image(b"x")
        assert spy_fusion.last_ocr == ocr_value


class TestFixtureKeyValidation:
    """fixture_key 인자 검증."""

    async def test_empty_fixture_key_raises_value_error(self) -> None:
        """fixture_key="" → ValueError."""
        pipeline = _build_real_pipeline()
        with pytest.raises(ValueError, match="fixture_key"):
            await pipeline.recognize_from_fixture_key("")


class TestByKeyUnsupported:
    """*_by_key를 지원하지 않는 어댑터일 때 fixture_key 경로 차단."""

    async def test_yolo_without_by_key_raises_meal_recognition_error(self) -> None:
        """detect_by_key 없는 YOLO 어댑터 → MealRecognitionError."""
        pipeline = MealPipeline(
            yolo_detector=_EmptyYoloDetector(),  # detect_by_key 없음
            gcv_adapter=MockGoogleVisionMealHintAdapter(MOCK_FIXTURES),
            fusion_engine=MealFusionEngine(),
            portion_estimator=PortionEstimator(),
        )
        with pytest.raises(MealRecognitionError, match="by_key"):
            await pipeline.recognize_from_fixture_key("any_key")

    async def test_gcv_without_by_key_raises_meal_recognition_error(self) -> None:
        """extract_*_by_key 없는 GCV 어댑터 → MealRecognitionError."""
        pipeline = MealPipeline(
            yolo_detector=MockYoloV8MealDetector(MOCK_FIXTURES),
            gcv_adapter=_EmptyGcvAdapter(),
            fusion_engine=MealFusionEngine(),
            portion_estimator=PortionEstimator(),
        )
        with pytest.raises(MealRecognitionError, match="by_key"):
            await pipeline.recognize_from_fixture_key("any_key")


class TestErrorPropagation:
    """MealParseError는 pipeline에서 감싸지 않고 그대로 전파."""

    async def test_yolo_meal_parse_error_propagates(self) -> None:
        """YOLO에서 MealParseError → 그대로 전파 (감싸지 않음)."""
        pipeline = MealPipeline(
            yolo_detector=_RaisingYoloDetector(),
            gcv_adapter=_EmptyGcvAdapter(),
            fusion_engine=MealFusionEngine(),
            portion_estimator=PortionEstimator(),
        )
        with pytest.raises(MealParseError):
            await pipeline.recognize_from_image(b"x")

    async def test_gcv_meal_parse_error_propagates(self) -> None:
        """GCV에서 MealParseError → 그대로 전파."""
        pipeline = MealPipeline(
            yolo_detector=_EmptyYoloDetector(),
            gcv_adapter=_RaisingGcvAdapter(),
            fusion_engine=MealFusionEngine(),
            portion_estimator=PortionEstimator(),
        )
        with pytest.raises(MealParseError):
            await pipeline.recognize_from_image(b"x")


class TestModuleStructure:
    """A3 / FastAPI / ml 범위 비-침범 (코드 구조 보장)."""

    def test_does_not_import_rda_matcher(self) -> None:
        """nutrition.rda_matcher import 없음 (A3 책임)."""
        source = inspect.getsource(pipeline_module)
        assert "src.nutrition.rda_matcher" not in source
        assert "src.nutrition" not in source

    def test_does_not_import_text_parser(self) -> None:
        """text_parser import 없음 (A3 책임)."""
        source = inspect.getsource(pipeline_module)
        assert "src.meal.text_parser" not in source

    def test_does_not_import_fastapi(self) -> None:
        """FastAPI / router import 없음 (별도 작업 범위)."""
        source = inspect.getsource(pipeline_module)
        assert "fastapi" not in source.lower()

    def test_does_not_import_ml_package(self) -> None:
        """ml/ 패키지 참조 없음 (Beta 범위)."""
        source = inspect.getsource(pipeline_module)
        assert "from ml" not in source
        assert "import ml\n" not in source
