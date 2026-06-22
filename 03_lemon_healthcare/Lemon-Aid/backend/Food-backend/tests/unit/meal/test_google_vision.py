"""MockGoogleVisionMealHintAdapter + ABC 단위 테스트.

dev-guide 16 §"2. google_vision.py"와 A2.2 hint 매핑 정책(사용자 합의)을 검증한다.

A2.2 정책:
- label은 그대로 `MealDetection.class_name_ko`에 들어가고 source="google_vision".
- label hint의 bbox=None, confidence=`_DEFAULT_LABEL_CONFIDENCE` (mock 기본값).
- label 번역 / food_aliases 매칭 / OCR 토큰화 / confidence 3구간 정책 → 본 모듈에서 금지.
- OCR 원문은 `extract_ocr_text` 별도 메서드로만 노출.
- object hint에 `bbox_xyxy`가 있으면 `BoundingBox`로 변환, 없으면 bbox=None.

Reference:
    docs/dev-guides/16-meal-recognition.md §"구현 명세 / 2. google_vision.py"
    docs/superpowers/plans/2026-05-11-meal-recognition-gcv-yolov8.md §"A2"
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from src.meal.base import MealDetection
from src.meal.exceptions import MealParseError
from src.meal.google_vision import (
    GoogleVisionMealHintAdapter,
    MockGoogleVisionMealHintAdapter,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
"""tests/unit/meal/test_google_vision.py → 5단계 위가 repo root."""

MOCK_FIXTURES = REPO_ROOT / "data" / "meal_vision" / "mock_predictions.json"

KIMCHI_STEW_RICE = "sample_kimchi_stew_rice.jpg"
BIBIMBAP_SOLO = "sample_bibimbap_solo.jpg"

KIMCHI_STEW_RICE_LABELS = ["food", "rice", "stew", "korean cuisine"]
KIMCHI_STEW_RICE_LABEL_COUNT = 4
DEFAULT_LABEL_CONFIDENCE = 0.5

OBJECT_BBOX_X_MIN = 50.0
OBJECT_BBOX_Y_MIN = 60.0
OBJECT_BBOX_X_MAX = 250.0
OBJECT_BBOX_Y_MAX = 260.0
OBJECT_SCORE = 0.82


class TestGoogleVisionMealHintAdapterABC:
    """ABC contract 검증."""

    def test_cannot_instantiate_abc(self) -> None:
        """ABC는 직접 인스턴스화할 수 없다."""
        with pytest.raises(TypeError):
            GoogleVisionMealHintAdapter()  # type: ignore[abstract]


class TestMockLoading:
    """fixture JSON 로딩 동작."""

    def test_loads_real_fixture(self) -> None:
        """실 fixture 경로로 정상 로드된다."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        assert KIMCHI_STEW_RICE in adapter.available_keys

    def test_missing_file_raises_meal_parse_error(self, tmp_path: Path) -> None:
        """파일이 없으면 MealParseError를 raise한다."""
        with pytest.raises(MealParseError):
            MockGoogleVisionMealHintAdapter(tmp_path / "missing.json")

    def test_malformed_json_raises_meal_parse_error(self, tmp_path: Path) -> None:
        """JSON 파싱 실패 시 MealParseError로 변환된다."""
        bad = tmp_path / "bad.json"
        bad.write_text("not json {{{", encoding="utf-8")
        with pytest.raises(MealParseError):
            MockGoogleVisionMealHintAdapter(bad)

    def test_schema_violation_raises_meal_parse_error(self, tmp_path: Path) -> None:
        """스키마 위반(labels 타입 오류 등)도 MealParseError로 변환된다."""
        bad = tmp_path / "bad.json"
        bad.write_text(
            json.dumps({"k1": {"gcv_hints": {"labels": "not-a-list"}}}),
            encoding="utf-8",
        )
        with pytest.raises(MealParseError):
            MockGoogleVisionMealHintAdapter(bad)

    def test_object_bbox_wrong_length_raises_meal_parse_error(self, tmp_path: Path) -> None:
        """object hint의 bbox_xyxy 길이가 4가 아니면 init 시 MealParseError로 변환된다.

        regression: bbox 길이를 detect 시점이 아닌 fixture 로드 시점에서 차단한다.
        """
        bad = tmp_path / "bad.json"
        bad.write_text(
            json.dumps(
                {
                    "k1": {
                        "gcv_hints": {
                            "labels": [],
                            "objects": [{"name": "Food", "bbox_xyxy": [1, 2, 3]}],
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(MealParseError):
            MockGoogleVisionMealHintAdapter(bad)


class TestExtractHintsByKey:
    """fixture_key로 hint 추출."""

    def test_known_key_returns_all_labels_as_detections(self) -> None:
        """등록된 key는 fixture의 모든 label을 detection으로 반환한다."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        results = adapter.extract_hints_by_key(KIMCHI_STEW_RICE)
        assert len(results) == KIMCHI_STEW_RICE_LABEL_COUNT
        names = [r.class_name_ko for r in results]
        assert names == KIMCHI_STEW_RICE_LABELS

    def test_unknown_key_returns_empty(self) -> None:
        """미등록 key는 빈 리스트를 반환한다."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        assert adapter.extract_hints_by_key("nonexistent.jpg") == []

    def test_all_detections_source_is_google_vision(self) -> None:
        """모든 detection의 source는 'google_vision'이다."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        for key in adapter.available_keys:
            for d in adapter.extract_hints_by_key(key):
                assert d.source == "google_vision"

    def test_label_bbox_is_none(self) -> None:
        """label hint는 위치 정보가 없으므로 bbox=None이다."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        results = adapter.extract_hints_by_key(KIMCHI_STEW_RICE)
        assert results
        for d in results:
            assert d.bbox is None

    def test_label_confidence_default(self) -> None:
        """real fixture에 score가 없으므로 기본 신뢰도 사용."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        for d in adapter.extract_hints_by_key(KIMCHI_STEW_RICE):
            assert d.confidence == DEFAULT_LABEL_CONFIDENCE

    def test_english_label_kept_as_is_no_translation(self) -> None:
        """label 번역 금지 — 영문 'bibimbap'이 그대로 유지된다."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        results = adapter.extract_hints_by_key(BIBIMBAP_SOLO)
        names = [r.class_name_ko for r in results]
        assert "bibimbap" in names
        assert "비빔밥" not in names

    def test_returned_items_are_meal_detection(self) -> None:
        """반환 타입은 MealDetection이다."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        for d in adapter.extract_hints_by_key(KIMCHI_STEW_RICE):
            assert isinstance(d, MealDetection)

    def test_object_hint_with_bbox_parsed(self, tmp_path: Path) -> None:
        """object hint에 bbox_xyxy가 있으면 BoundingBox로 변환된다."""
        fixture_data = {
            "with-object.jpg": {
                "gcv_hints": {
                    "labels": [],
                    "ocr_text": "",
                    "objects": [
                        {
                            "name": "Food",
                            "score": OBJECT_SCORE,
                            "bbox_xyxy": [
                                OBJECT_BBOX_X_MIN,
                                OBJECT_BBOX_Y_MIN,
                                OBJECT_BBOX_X_MAX,
                                OBJECT_BBOX_Y_MAX,
                            ],
                        }
                    ],
                }
            }
        }
        fx = tmp_path / "fx.json"
        fx.write_text(json.dumps(fixture_data), encoding="utf-8")
        adapter = MockGoogleVisionMealHintAdapter(fx)
        results = adapter.extract_hints_by_key("with-object.jpg")
        assert len(results) == 1
        d = results[0]
        assert d.class_name_ko == "Food"
        assert d.source == "google_vision"
        assert d.confidence == OBJECT_SCORE
        assert d.bbox is not None
        assert d.bbox.x_min == OBJECT_BBOX_X_MIN
        assert d.bbox.y_min == OBJECT_BBOX_Y_MIN
        assert d.bbox.x_max == OBJECT_BBOX_X_MAX
        assert d.bbox.y_max == OBJECT_BBOX_Y_MAX

    def test_object_hint_without_bbox_returns_none(self, tmp_path: Path) -> None:
        """object hint에 bbox_xyxy가 없으면 bbox=None."""
        fixture_data = {
            "obj-no-bbox.jpg": {
                "gcv_hints": {
                    "labels": [],
                    "ocr_text": "",
                    "objects": [{"name": "Plate"}],
                }
            }
        }
        fx = tmp_path / "fx.json"
        fx.write_text(json.dumps(fixture_data), encoding="utf-8")
        adapter = MockGoogleVisionMealHintAdapter(fx)
        results = adapter.extract_hints_by_key("obj-no-bbox.jpg")
        assert len(results) == 1
        assert results[0].bbox is None
        assert results[0].class_name_ko == "Plate"

    def test_labels_and_objects_both_emitted(self, tmp_path: Path) -> None:
        """labels와 objects가 모두 있으면 둘 다 detection으로 변환된다."""
        fixture_data = {
            "mixed.jpg": {
                "gcv_hints": {
                    "labels": ["food"],
                    "ocr_text": "",
                    "objects": [{"name": "Bowl"}],
                }
            }
        }
        fx = tmp_path / "fx.json"
        fx.write_text(json.dumps(fixture_data), encoding="utf-8")
        adapter = MockGoogleVisionMealHintAdapter(fx)
        results = adapter.extract_hints_by_key("mixed.jpg")
        names = [r.class_name_ko for r in results]
        assert "food" in names
        assert "Bowl" in names


class TestExtractOcrTextByKey:
    """fixture_key로 OCR 원문 조회."""

    def test_known_key_with_empty_ocr_returns_empty_string(self) -> None:
        """real fixture의 ocr_text=""이면 빈 문자열 반환."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        assert adapter.extract_ocr_text_by_key(KIMCHI_STEW_RICE) == ""

    def test_unknown_key_returns_empty_string(self) -> None:
        """미등록 key는 빈 문자열 반환."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        assert adapter.extract_ocr_text_by_key("nonexistent.jpg") == ""

    def test_non_empty_ocr_text_returned_verbatim(self, tmp_path: Path) -> None:
        """OCR 원문이 있으면 토큰화·정규화 없이 그대로 반환된다."""
        ocr_sample = "메뉴: 김치찌개 8,000원\n공기밥 1,000원"
        fixture_data = {
            "menu.jpg": {
                "gcv_hints": {
                    "labels": [],
                    "ocr_text": ocr_sample,
                }
            }
        }
        fx = tmp_path / "fx.json"
        fx.write_text(json.dumps(fixture_data, ensure_ascii=False), encoding="utf-8")
        adapter = MockGoogleVisionMealHintAdapter(fx)
        assert adapter.extract_ocr_text_by_key("menu.jpg") == ocr_sample


class TestExtractHintsAsync:
    """SHA256 기반 extract_hints(bytes) 비동기 인터페이스."""

    async def test_unknown_bytes_returns_empty(self) -> None:
        """SHA256가 매칭되지 않으면 빈 리스트."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        assert await adapter.extract_hints(b"random bytes that do not match") == []

    async def test_sha256_keyed_fixture_resolves(self, tmp_path: Path) -> None:
        """SHA256 hash 키로 등록된 fixture는 extract_hints(bytes)가 찾는다."""
        img_bytes = b"\x89PNG\r\n\x1a\nfakebytes-gcv"
        sha = hashlib.sha256(img_bytes).hexdigest()
        fixture_data = {
            sha: {
                "gcv_hints": {
                    "labels": ["food"],
                    "ocr_text": "",
                }
            }
        }
        fx = tmp_path / "fx.json"
        fx.write_text(json.dumps(fixture_data), encoding="utf-8")
        adapter = MockGoogleVisionMealHintAdapter(fx)
        results = await adapter.extract_hints(img_bytes)
        assert len(results) == 1
        assert results[0].class_name_ko == "food"
        assert results[0].source == "google_vision"


class TestExtractOcrTextAsync:
    """SHA256 기반 extract_ocr_text(bytes) 비동기 인터페이스."""

    async def test_unknown_bytes_returns_empty_string(self) -> None:
        """SHA256가 매칭되지 않으면 빈 문자열."""
        adapter = MockGoogleVisionMealHintAdapter(MOCK_FIXTURES)
        assert await adapter.extract_ocr_text(b"random bytes that do not match") == ""

    async def test_sha256_keyed_fixture_resolves_ocr(self, tmp_path: Path) -> None:
        """SHA256 hash 키로 등록된 fixture는 extract_ocr_text(bytes)가 찾는다."""
        img_bytes = b"\x89PNG\r\n\x1a\nfakebytes-ocr"
        sha = hashlib.sha256(img_bytes).hexdigest()
        ocr_sample = "테이블 메뉴 1번"
        fixture_data = {
            sha: {
                "gcv_hints": {
                    "labels": [],
                    "ocr_text": ocr_sample,
                }
            }
        }
        fx = tmp_path / "fx.json"
        fx.write_text(json.dumps(fixture_data, ensure_ascii=False), encoding="utf-8")
        adapter = MockGoogleVisionMealHintAdapter(fx)
        assert await adapter.extract_ocr_text(img_bytes) == ocr_sample
