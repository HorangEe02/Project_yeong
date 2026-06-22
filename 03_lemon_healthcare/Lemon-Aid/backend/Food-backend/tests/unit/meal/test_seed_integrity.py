"""시드 데이터 정합성 테스트.

`data/rda/korean_foods.csv`, `data/rda/food_aliases.json`,
`data/meal_vision/classes.yaml`, `data/meal_vision/mock_predictions.json`
4개 파일이 서로 정합성을 유지하는지 자동 검증한다.

Reference:
    docs/dev-guides/16-meal-recognition.md §"클래스 우선순위"
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[5]
"""tests/unit/meal/test_seed_integrity.py → 5단계 위가 repo root."""

EXPECTED_FOOD_COUNT = 100
FOOD_CODE_LENGTH = 4
MIN_ALIAS_COUNT = 100
MIN_MOCK_IMAGES = 10
BBOX_COORD_COUNT = 4
REVIEW_THRESHOLD = 0.40
AUTO_CANDIDATE_THRESHOLD = 0.70
MIN_POLICY_CASES = 1


KOREAN_FOODS_CSV = REPO_ROOT / "data" / "rda" / "korean_foods.csv"
FOOD_ALIASES_JSON = REPO_ROOT / "data" / "rda" / "food_aliases.json"
CLASSES_YAML = REPO_ROOT / "data" / "meal_vision" / "classes.yaml"
MOCK_PREDICTIONS_JSON = REPO_ROOT / "data" / "meal_vision" / "mock_predictions.json"


@pytest.fixture(scope="module")
def korean_foods() -> list[dict[str, str]]:
    """`korean_foods.csv` 파싱 결과."""
    with KOREAN_FOODS_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def food_codes(korean_foods: list[dict[str, str]]) -> set[str]:
    """CSV의 모든 food_code 집합."""
    return {row["food_code"] for row in korean_foods}


@pytest.fixture(scope="module")
def aliases() -> dict[str, str]:
    """`food_aliases.json` 파싱 결과."""
    return json.loads(FOOD_ALIASES_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def classes() -> dict[str, object]:
    """`classes.yaml` 파싱 결과."""
    return yaml.safe_load(CLASSES_YAML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def class_names(classes: dict[str, object]) -> set[str]:
    """classes.yaml의 names value 집합."""
    names = classes["names"]
    assert isinstance(names, dict)
    return set(names.values())


@pytest.fixture(scope="module")
def mock_predictions() -> dict[str, dict[str, object]]:
    """`mock_predictions.json` 파싱 결과."""
    return json.loads(MOCK_PREDICTIONS_JSON.read_text(encoding="utf-8"))


class TestKoreanFoodsCsv:
    """`korean_foods.csv` 단독 검증."""

    def test_100_rows(self, korean_foods: list[dict[str, str]]) -> None:
        """100개 음식 행이 있다."""
        assert len(korean_foods) == EXPECTED_FOOD_COUNT

    def test_food_code_unique(self, korean_foods: list[dict[str, str]]) -> None:
        """food_code는 중복 없음."""
        codes = [row["food_code"] for row in korean_foods]
        assert len(codes) == len(set(codes))

    def test_food_code_format(self, food_codes: set[str]) -> None:
        """food_code는 `F\\d{3}` 형식."""
        for code in food_codes:
            assert code.startswith("F"), code
            assert code[1:].isdigit(), code
            assert len(code) == FOOD_CODE_LENGTH, code

    def test_required_columns(self, korean_foods: list[dict[str, str]]) -> None:
        """필수 컬럼이 모든 행에 존재한다."""
        required = {
            "food_code",
            "name_ko",
            "name_en",
            "category",
            "unit_size_g",
            "kcal_per_unit",
        }
        for row in korean_foods:
            missing = required - row.keys()
            assert not missing, f"missing columns in row {row.get('food_code')}: {missing}"

    def test_unit_size_positive(self, korean_foods: list[dict[str, str]]) -> None:
        """unit_size_g는 양수."""
        for row in korean_foods:
            assert float(row["unit_size_g"]) > 0, row["food_code"]


class TestFoodAliasesJson:
    """`food_aliases.json` 단독 검증."""

    def test_non_empty(self, aliases: dict[str, str]) -> None:
        """alias 매핑이 비어있지 않다."""
        assert len(aliases) >= MIN_ALIAS_COUNT

    def test_keys_non_empty(self, aliases: dict[str, str]) -> None:
        """alias 키는 빈 문자열 아님."""
        for k in aliases:
            assert k.strip(), repr(k)

    def test_values_food_code_format(self, aliases: dict[str, str]) -> None:
        """모든 값이 `F\\d{3}` 형식."""
        for v in aliases.values():
            assert v.startswith("F"), v
            assert v[1:].isdigit(), v


class TestCrossReference:
    """파일 간 cross-reference 정합성."""

    def test_alias_values_all_in_csv(self, aliases: dict[str, str], food_codes: set[str]) -> None:
        """alias.json의 모든 food_code가 csv에 존재."""
        invalid = {k: v for k, v in aliases.items() if v not in food_codes}
        assert not invalid, f"존재하지 않는 food_code 참조: {invalid}"

    def test_all_food_codes_referenced(self, aliases: dict[str, str], food_codes: set[str]) -> None:
        """모든 food_code가 alias에서 최소 한 번 등장."""
        referenced = set(aliases.values())
        unreferenced = food_codes - referenced
        assert not unreferenced, f"alias에 없는 food_code: {sorted(unreferenced)}"

    def test_classes_match_aliases_or_csv(
        self,
        class_names: set[str],
        aliases: dict[str, str],
        korean_foods: list[dict[str, str]],
    ) -> None:
        """classes.yaml의 names가 alias 키 또는 csv name_ko에 존재."""
        csv_names = {row["name_ko"] for row in korean_foods}
        alias_keys = set(aliases.keys())
        unknown = class_names - alias_keys - csv_names
        assert not unknown, f"classes.yaml에만 있는 음식: {sorted(unknown)}"

    def test_mock_classes_in_yaml(
        self,
        mock_predictions: dict[str, dict[str, object]],
        class_names: set[str],
    ) -> None:
        """mock_predictions.json의 class_name_ko가 classes.yaml에 정의."""
        mock_names: set[str] = set()
        for pred in mock_predictions.values():
            detections = pred["detections"]
            assert isinstance(detections, list)
            for d in detections:
                assert isinstance(d, dict)
                mock_names.add(str(d["class_name_ko"]))
        missing = mock_names - class_names
        assert not missing, f"classes.yaml에 없는 mock 클래스: {sorted(missing)}"

    def test_mock_class_id_matches_yaml(
        self,
        mock_predictions: dict[str, dict[str, object]],
        classes: dict[str, object],
    ) -> None:
        """mock detection의 class_id가 classes.yaml의 키와 일치."""
        names = classes["names"]
        assert isinstance(names, dict)
        for img_name, pred in mock_predictions.items():
            detections = pred["detections"]
            assert isinstance(detections, list)
            for d in detections:
                assert isinstance(d, dict)
                cid = int(d["class_id"])  # type: ignore[arg-type]
                expected = str(d["class_name_ko"])
                actual = names.get(cid)
                assert (
                    actual == expected
                ), f"{img_name}: class_id {cid} → '{actual}' but mock says '{expected}'"


class TestMockPredictionsShape:
    """`mock_predictions.json` 구조 검증."""

    def test_non_empty(self, mock_predictions: dict[str, dict[str, object]]) -> None:
        """최소 10장 이상."""
        assert len(mock_predictions) >= MIN_MOCK_IMAGES

    def test_each_entry_has_detections_and_hints(
        self, mock_predictions: dict[str, dict[str, object]]
    ) -> None:
        """각 항목은 detections + gcv_hints를 가진다."""
        for img_name, pred in mock_predictions.items():
            assert "detections" in pred, img_name
            assert "gcv_hints" in pred, img_name

    def test_bbox_xyxy_ordered(self, mock_predictions: dict[str, dict[str, object]]) -> None:
        """bbox_xyxy는 [x1, y1, x2, y2]이고 x1<x2, y1<y2."""
        for img_name, pred in mock_predictions.items():
            detections = pred["detections"]
            assert isinstance(detections, list)
            for d in detections:
                assert isinstance(d, dict)
                bbox = d["bbox_xyxy"]
                assert isinstance(bbox, list) and len(bbox) == BBOX_COORD_COUNT, img_name
                x1, y1, x2, y2 = bbox
                assert x1 < x2 and y1 < y2, f"{img_name}: 잘못된 bbox 순서 {bbox}"

    def test_confidence_distribution_covers_policy_bands(
        self, mock_predictions: dict[str, dict[str, object]]
    ) -> None:
        """신뢰도 정책 3구간을 모두 커버한다.

        dev-guide 16 §결과 신뢰도 정책:
            >=0.70: 자동 후보
            0.40 ~ 0.69: needs_user_review
            <0.40: 자동 확정 X
        """
        confs: list[float] = []
        for pred in mock_predictions.values():
            detections = pred["detections"]
            assert isinstance(detections, list)
            for d in detections:
                assert isinstance(d, dict)
                confs.append(float(d["confidence"]))  # type: ignore[arg-type]
        high = sum(1 for c in confs if c >= AUTO_CANDIDATE_THRESHOLD)
        mid = sum(1 for c in confs if REVIEW_THRESHOLD <= c < AUTO_CANDIDATE_THRESHOLD)
        low = sum(1 for c in confs if c < REVIEW_THRESHOLD)
        assert high >= MIN_POLICY_CASES, "고신뢰도(≥0.70) 케이스 필요"
        assert mid >= MIN_POLICY_CASES, "중간 신뢰도(0.40~0.69) 케이스 필요"
        assert low >= MIN_POLICY_CASES, "저신뢰도(<0.40) 케이스 필요"
