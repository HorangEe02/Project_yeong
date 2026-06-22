"""MealFusionEngine 단위 테스트.

dev-guide 16 §"4. fusion.py"와 A2.3 fusion 규칙을 검증한다.

규칙 요약:
    1. YOLO primary — 모든 RecognizedMealItem은 YOLO에서 시작.
    2. GCV alias 보강 — 같은 canonical key면 sources에 google_vision 추가.
    3. 충돌(orphan GCV) — 최고 confidence YOLO item을 review로 표시.
    4. 동일 음식 다중 bbox — 최고 confidence 1개 + 나머지 alternatives.
    5. 신뢰도 정책 — ≥0.70 → review=False, 그 외 → review=True (보존).
    6. YOLO 비면 빈 리스트.

Reference:
    docs/dev-guides/16-meal-recognition.md
    docs/superpowers/plans/2026-05-11-meal-recognition-gcv-yolov8.md §"A2"
"""

from __future__ import annotations

from src.meal.base import BoundingBox, MealDetection
from src.meal.fusion import (
    AUTO_CANDIDATE_THRESHOLD,
    DEFAULT_ESTIMATED_GRAMS,
    MealFusionEngine,
)

HIGH_CONF = 0.85
MID_CONF = 0.55
LOW_CONF = 0.32
EXACT_THRESHOLD = 0.70
JUST_BELOW_THRESHOLD = 0.69

DUP_REP_CONF = 0.91
DUP_ALT_CONF = 0.65

ALIAS_HIGHER_CONF = 0.92
ALIAS_LOWER_CONF = 0.85

CONFLICT_TOP_CONF = 0.85
CONFLICT_OTHER_CONF = 0.75

EXPECTED_TWO_ITEMS = 2
EXPECTED_ONE_ALTERNATIVE = 1

ALIASES_RICE_BIBIMBAP = {
    "공기밥": "F001",
    "쌀밥": "F001",
    "비빔밥": "F003",
    "bibimbap": "F003",
}


def _yolo_det(name: str, conf: float) -> MealDetection:
    """YOLO MealDetection 팩토리 (bbox 포함)."""
    return MealDetection(
        class_name_ko=name,
        confidence=conf,
        bbox=BoundingBox(x_min=0, y_min=0, x_max=100, y_max=100),
        source="yolo_v8",
    )


def _gcv_det(name: str, conf: float = 0.5) -> MealDetection:
    """GCV MealDetection 팩토리 (bbox=None, label hint 가정)."""
    return MealDetection(
        class_name_ko=name,
        confidence=conf,
        bbox=None,
        source="google_vision",
    )


class TestEmptyInput:
    """yolo_detections가 비어있는 경우."""

    def test_empty_yolo_returns_empty(self) -> None:
        """YOLO 비어있으면 빈 리스트."""
        engine = MealFusionEngine()
        assert engine.fuse(yolo_detections=[], gcv_hints=[]) == []

    def test_empty_yolo_with_gcv_still_returns_empty(self) -> None:
        """GCV hint만 있어도 YOLO가 없으면 item을 만들지 않는다."""
        engine = MealFusionEngine()
        gcv = [_gcv_det("food"), _gcv_det("rice")]
        assert engine.fuse(yolo_detections=[], gcv_hints=gcv) == []


class TestYoloPrimary:
    """YOLO가 RecognizedMealItem 주체."""

    def test_single_yolo_creates_one_item(self) -> None:
        """YOLO 1개 → item 1개."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[],
        )
        assert len(items) == 1

    def test_yolo_source_in_sources(self) -> None:
        """sources에 'yolo_v8' 포함."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[],
        )
        assert "yolo_v8" in items[0].sources

    def test_item_name_matches_yolo(self) -> None:
        """name_ko = YOLO class_name_ko."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[],
        )
        assert items[0].name_ko == "공기밥"

    def test_item_confidence_matches_yolo(self) -> None:
        """confidence = YOLO confidence."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[],
        )
        assert items[0].confidence == HIGH_CONF

    def test_food_code_is_none(self) -> None:
        """food_code는 A3 RDA matching까지 None."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[],
        )
        assert items[0].food_code is None

    def test_default_estimated_grams(self) -> None:
        """estimated_grams는 A2.4 도입 전 임시 기본값."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[],
        )
        assert items[0].estimated_grams == DEFAULT_ESTIMATED_GRAMS

    def test_portion_confidence_is_zero(self) -> None:
        """양 추정 전이므로 portion_confidence=0.0."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[],
        )
        assert items[0].portion_confidence == 0.0


class TestConfidencePolicy:
    """신뢰도 3구간 정책."""

    def test_high_confidence_no_review(self) -> None:
        """conf >= 0.70 → needs_user_review=False."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[],
        )
        assert items[0].needs_user_review is False

    def test_threshold_inclusive_at_070(self) -> None:
        """conf == 0.70 → review=False (>= 비교, boundary inclusive)."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", EXACT_THRESHOLD)],
            gcv_hints=[],
        )
        assert items[0].needs_user_review is False

    def test_just_below_threshold_review(self) -> None:
        """conf == 0.69 → review=True."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", JUST_BELOW_THRESHOLD)],
            gcv_hints=[],
        )
        assert items[0].needs_user_review is True

    def test_mid_confidence_review(self) -> None:
        """0.40~0.69 → review=True."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", MID_CONF)],
            gcv_hints=[],
        )
        assert items[0].needs_user_review is True

    def test_low_confidence_review(self) -> None:
        """conf < 0.40 → review=True."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", LOW_CONF)],
            gcv_hints=[],
        )
        assert items[0].needs_user_review is True

    def test_low_confidence_preserved_not_dropped(self) -> None:
        """낮은 confidence도 버리지 않고 보존한다."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", LOW_CONF)],
            gcv_hints=[],
        )
        assert len(items) == 1
        assert items[0].confidence == LOW_CONF


class TestGcvAugmentation:
    """GCV hint로 sources 보강."""

    def test_matching_name_adds_google_vision_source(self) -> None:
        """GCV가 YOLO와 같은 이름이면 sources에 google_vision 추가."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[_gcv_det("공기밥")],
        )
        assert "google_vision" in items[0].sources
        assert "yolo_v8" in items[0].sources

    def test_alias_match_via_food_code(self) -> None:
        """aliases mapping으로 같은 food_code면 raw name이 달라도 매칭된다."""
        engine = MealFusionEngine(aliases=ALIASES_RICE_BIBIMBAP)
        # YOLO=비빔밥, GCV=bibimbap, 둘 다 F003
        items = engine.fuse(
            yolo_detections=[_yolo_det("비빔밥", HIGH_CONF)],
            gcv_hints=[_gcv_det("bibimbap")],
        )
        assert len(items) == 1
        assert "google_vision" in items[0].sources

    def test_gcv_does_not_create_new_item_when_matched(self) -> None:
        """GCV 매칭은 item 수를 늘리지 않는다."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[_gcv_det("공기밥"), _gcv_det("공기밥")],
        )
        assert len(items) == 1

    def test_no_translation_bibimbap_not_matched_without_alias(self) -> None:
        """aliases 없으면 영문 'bibimbap'은 '비빔밥'과 매칭되지 않는다 (번역 금지)."""
        engine = MealFusionEngine()  # 빈 aliases
        items = engine.fuse(
            yolo_detections=[_yolo_det("비빔밥", HIGH_CONF)],
            gcv_hints=[_gcv_det("bibimbap")],
        )
        assert len(items) == 1
        assert "google_vision" not in items[0].sources
        # bibimbap이 orphan이 되어 review가 강제됨
        assert items[0].needs_user_review is True


class TestConflict:
    """orphan GCV 충돌 처리."""

    def test_orphan_gcv_marks_highest_conf_review(self) -> None:
        """orphan GCV가 있으면 최고 conf YOLO item을 review로 표시한다."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[
                _yolo_det("공기밥", CONFLICT_TOP_CONF),  # 최고
                _yolo_det("김치찌개", CONFLICT_OTHER_CONF),
            ],
            gcv_hints=[_gcv_det("pizza")],  # orphan
        )
        rice = next(i for i in items if i.name_ko == "공기밥")
        stew = next(i for i in items if i.name_ko == "김치찌개")
        assert rice.needs_user_review is True  # orphan-induced
        assert stew.needs_user_review is False  # not affected

    def test_orphan_gcv_does_not_create_new_item(self) -> None:
        """orphan GCV는 별도 item을 만들지 않는다."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[_gcv_det("pizza"), _gcv_det("burger")],
        )
        assert len(items) == 1
        assert items[0].name_ko == "공기밥"


class TestDuplicates:
    """동일 음식 다중 detection."""

    def test_same_name_aggregated_to_one_item(self) -> None:
        """같은 이름 YOLO 2개 → item 1개."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[
                _yolo_det("공기밥", DUP_REP_CONF),
                _yolo_det("공기밥", DUP_ALT_CONF),
            ],
            gcv_hints=[],
        )
        assert len(items) == 1

    def test_representative_is_highest_confidence(self) -> None:
        """대표 item은 confidence 최고 detection."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[
                _yolo_det("공기밥", DUP_ALT_CONF),  # 입력 순서가 낮은 게 먼저
                _yolo_det("공기밥", DUP_REP_CONF),
            ],
            gcv_hints=[],
        )
        assert items[0].confidence == DUP_REP_CONF

    def test_alternatives_contains_non_representative(self) -> None:
        """비대표 detection은 alternatives에 보존된다."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[
                _yolo_det("공기밥", DUP_REP_CONF),
                _yolo_det("공기밥", DUP_ALT_CONF),
            ],
            gcv_hints=[],
        )
        assert len(items[0].alternatives) == EXPECTED_ONE_ALTERNATIVE
        assert items[0].alternatives[0].confidence == DUP_ALT_CONF

    def test_alias_same_food_code_aggregated(self) -> None:
        """aliases로 같은 food_code면 raw name이 달라도 하나로 묶인다."""
        engine = MealFusionEngine(aliases=ALIASES_RICE_BIBIMBAP)
        items = engine.fuse(
            yolo_detections=[
                _yolo_det("공기밥", ALIAS_LOWER_CONF),
                _yolo_det("쌀밥", ALIAS_HIGHER_CONF),  # 같은 F001, 더 높은 conf
            ],
            gcv_hints=[],
        )
        assert len(items) == 1
        # 쌀밥이 conf 높으므로 대표
        assert items[0].name_ko == "쌀밥"
        assert len(items[0].alternatives) == EXPECTED_ONE_ALTERNATIVE
        assert items[0].alternatives[0].class_name_ko == "공기밥"


class TestAliasMapping:
    """aliases mapping 처리."""

    def test_default_no_aliases_uses_name_as_key(self) -> None:
        """aliases 미지정이면 이름이 그대로 canonical key."""
        engine = MealFusionEngine()
        items = engine.fuse(
            yolo_detections=[
                _yolo_det("공기밥", HIGH_CONF),
                _yolo_det("김치찌개", HIGH_CONF),
            ],
            gcv_hints=[],
        )
        assert len(items) == EXPECTED_TWO_ITEMS

    def test_none_aliases_param_treated_as_empty(self) -> None:
        """aliases=None을 명시해도 빈 매핑과 동일하게 동작한다."""
        engine = MealFusionEngine(aliases=None)
        items = engine.fuse(
            yolo_detections=[_yolo_det("공기밥", HIGH_CONF)],
            gcv_hints=[],
        )
        assert items[0].name_ko == "공기밥"

    def test_unmapped_name_uses_name_as_fallback(self) -> None:
        """aliases에 없는 이름은 이름 자체를 fallback key로 사용한다."""
        engine = MealFusionEngine(aliases=ALIASES_RICE_BIBIMBAP)
        # 김치찌개는 ALIASES_RICE_BIBIMBAP에 없음
        items = engine.fuse(
            yolo_detections=[_yolo_det("김치찌개", HIGH_CONF)],
            gcv_hints=[_gcv_det("김치찌개")],
        )
        assert len(items) == 1
        assert "google_vision" in items[0].sources


class TestModuleConstants:
    """모듈 상수 값 고정 검증 (A2.4 도입 시 변경 추적용)."""

    def test_default_estimated_grams_is_100(self) -> None:
        """DEFAULT_ESTIMATED_GRAMS = 100.0 (A2.4 전 임시)."""
        expected = 100.0
        assert expected == DEFAULT_ESTIMATED_GRAMS

    def test_auto_candidate_threshold_is_070(self) -> None:
        """AUTO_CANDIDATE_THRESHOLD = 0.70."""
        expected = 0.70
        assert expected == AUTO_CANDIDATE_THRESHOLD
