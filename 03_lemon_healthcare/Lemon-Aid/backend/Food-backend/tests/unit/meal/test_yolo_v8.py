"""MockYoloV8MealDetector + ABC 단위 테스트.

dev-guide 16 §"3. yolo_v8.py" 명세와 A2.1 contract를 검증한다.

Reference:
    docs/dev-guides/16-meal-recognition.md
    docs/superpowers/plans/2026-05-11-meal-recognition-gcv-yolov8.md §"A2"
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from src.meal.base import MealDetection
from src.meal.exceptions import MealParseError
from src.meal.yolo_v8 import MockYoloV8MealDetector, YoloV8MealDetector

REPO_ROOT = Path(__file__).resolve().parents[5]
"""tests/unit/meal/test_yolo_v8.py → 5단계 위가 repo root."""

MOCK_FIXTURES = REPO_ROOT / "data" / "meal_vision" / "mock_predictions.json"

KIMCHI_STEW_RICE = "sample_kimchi_stew_rice.jpg"
BIBIMBAP_SOLO = "sample_bibimbap_solo.jpg"
LOW_CONF_BLURRY = "sample_low_conf_blurry.jpg"
BULGOGI_SET = "sample_bulgogi_set.jpg"
DUPLICATE_DISH = "sample_duplicate_dish.jpg"

KIMCHI_STEW_RICE_DETECTION_COUNT = 2
DUPLICATE_DISH_DETECTION_COUNT = 2
BULGOGI_SET_DETECTION_COUNT = 3

BIBIMBAP_BBOX_X_MIN = 80
BIBIMBAP_BBOX_Y_MIN = 60
BIBIMBAP_BBOX_X_MAX = 720
BIBIMBAP_BBOX_Y_MAX = 700

LOW_CONFIDENCE_VALUE = 0.32
HIGH_FILTER = 0.9
MID_FILTER = 0.5


class TestYoloV8MealDetectorABC:
    """ABC contract 검증."""

    def test_cannot_instantiate_abc(self) -> None:
        """ABC는 직접 인스턴스화할 수 없다."""
        with pytest.raises(TypeError):
            YoloV8MealDetector()  # type: ignore[abstract]


class TestMockLoading:
    """fixture JSON 로딩 동작."""

    def test_loads_real_fixture(self) -> None:
        """실 fixture 경로로 정상 로드된다."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        assert KIMCHI_STEW_RICE in detector.available_keys

    def test_missing_file_raises_meal_parse_error(self, tmp_path: Path) -> None:
        """파일이 없으면 MealParseError를 raise한다."""
        with pytest.raises(MealParseError):
            MockYoloV8MealDetector(tmp_path / "missing.json")

    def test_malformed_json_raises_meal_parse_error(self, tmp_path: Path) -> None:
        """JSON 파싱 실패 시 MealParseError로 변환된다."""
        bad = tmp_path / "bad.json"
        bad.write_text("not json {{{", encoding="utf-8")
        with pytest.raises(MealParseError):
            MockYoloV8MealDetector(bad)

    def test_schema_violation_raises_meal_parse_error(self, tmp_path: Path) -> None:
        """스키마 위반(빈 class_name_ko, 신뢰도 범위 초과 등)도 MealParseError로 변환된다."""
        bad = tmp_path / "bad.json"
        bad.write_text(
            json.dumps(
                {
                    "key1": {
                        "detections": [
                            {
                                "class_id": 0,
                                "class_name_ko": "",
                                "confidence": 2.0,
                                "bbox_xyxy": [0, 0, 10, 10],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(MealParseError):
            MockYoloV8MealDetector(bad)


class TestDetectByKey:
    """fixture_key 직접 조회 동작."""

    def test_known_key_returns_all_detections(self) -> None:
        """등록된 key는 fixture의 모든 detection을 반환한다."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        results = detector.detect_by_key(KIMCHI_STEW_RICE)
        assert len(results) == KIMCHI_STEW_RICE_DETECTION_COUNT
        names = {r.class_name_ko for r in results}
        assert names == {"김치찌개", "공기밥"}

    def test_unknown_key_returns_empty(self) -> None:
        """미등록 key는 빈 리스트를 반환한다."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        assert detector.detect_by_key("nonexistent.jpg") == []

    def test_all_detections_source_is_yolo_v8(self) -> None:
        """모든 detection의 source는 'yolo_v8'이다."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        for key in detector.available_keys:
            for d in detector.detect_by_key(key):
                assert d.source == "yolo_v8"

    def test_returned_items_are_meal_detection(self) -> None:
        """반환 타입은 MealDetection이다."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        for d in detector.detect_by_key(KIMCHI_STEW_RICE):
            assert isinstance(d, MealDetection)

    def test_bbox_xyxy_parsed_to_bounding_box(self) -> None:
        """bbox_xyxy 4-tuple이 BoundingBox로 매핑된다."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        results = detector.detect_by_key(BIBIMBAP_SOLO)
        assert len(results) == 1
        bbox = results[0].bbox
        assert bbox is not None
        assert bbox.x_min == BIBIMBAP_BBOX_X_MIN
        assert bbox.y_min == BIBIMBAP_BBOX_Y_MIN
        assert bbox.x_max == BIBIMBAP_BBOX_X_MAX
        assert bbox.y_max == BIBIMBAP_BBOX_Y_MAX

    def test_low_confidence_detection_still_returned(self) -> None:
        """conf < 0.40인 detection도 detector는 그대로 반환한다 (신뢰도 정책은 fusion 책임)."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        results = detector.detect_by_key(LOW_CONF_BLURRY)
        assert len(results) == 1
        assert results[0].confidence == LOW_CONFIDENCE_VALUE

    def test_multiple_detections_preserved(self) -> None:
        """다중 detection이 모두 보존된다."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        results = detector.detect_by_key(BULGOGI_SET)
        assert len(results) == BULGOGI_SET_DETECTION_COUNT

    def test_duplicate_class_preserved(self) -> None:
        """같은 클래스가 여러 bbox로 탐지되어도 모두 반환된다 (대표 선정은 fusion)."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        results = detector.detect_by_key(DUPLICATE_DISH)
        assert len(results) == DUPLICATE_DISH_DETECTION_COUNT
        assert all(r.class_name_ko == "계란말이" for r in results)


class TestDetectAsync:
    """SHA256 기반 detect(bytes) 비동기 인터페이스."""

    async def test_unknown_bytes_returns_empty(self) -> None:
        """SHA256가 매칭되지 않으면 빈 리스트."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        assert await detector.detect(b"random bytes that do not match") == []

    async def test_sha256_keyed_fixture_resolves(self, tmp_path: Path) -> None:
        """SHA256 hash 키로 등록된 fixture는 detect(bytes)가 찾는다."""
        img_bytes = b"\x89PNG\r\n\x1a\nfakebytes-deterministic"
        sha = hashlib.sha256(img_bytes).hexdigest()
        fixture_data = {
            sha: {
                "detections": [
                    {
                        "class_id": 0,
                        "class_name_ko": "공기밥",
                        "confidence": 0.91,
                        "bbox_xyxy": [10, 20, 100, 200],
                    }
                ],
                "gcv_hints": {"labels": [], "ocr_text": ""},
            }
        }
        fixture = tmp_path / "fixture.json"
        fixture.write_text(json.dumps(fixture_data), encoding="utf-8")
        detector = MockYoloV8MealDetector(fixture)
        results = await detector.detect(img_bytes)
        assert len(results) == 1
        assert results[0].class_name_ko == "공기밥"


class TestConfidenceFilter:
    """min_confidence 옵셔널 사전 필터."""

    def test_default_threshold_returns_all(self) -> None:
        """기본 threshold=0.0이면 모든 detection 반환."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        assert len(detector.detect_by_key(LOW_CONF_BLURRY)) == 1

    def test_min_confidence_excludes_below_threshold(self) -> None:
        """min_confidence보다 낮은 detection은 제외된다."""
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        results = detector.detect_by_key(LOW_CONF_BLURRY, min_confidence=MID_FILTER)
        assert results == []

    def test_min_confidence_keeps_above_threshold(self) -> None:
        """threshold 이상 detection은 유지된다.

        sample_kimchi_stew_rice: 0.86 (김치찌개) / 0.91 (공기밥).
        HIGH_FILTER=0.9 적용 → 공기밥만 통과.
        """
        detector = MockYoloV8MealDetector(MOCK_FIXTURES)
        results = detector.detect_by_key(KIMCHI_STEW_RICE, min_confidence=HIGH_FILTER)
        assert len(results) == 1
        assert results[0].class_name_ko == "공기밥"
