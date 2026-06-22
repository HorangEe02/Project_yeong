"""만성질환-영양제 매트릭스 로더 단위 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.models.schemas.chronic_disease_matrix import ChronicDiseaseSupplementMatrix
from src.utils.chronic_disease_matrix import (
    category_profile,
    category_to_conditions,
    conditions_to_categories,
    load_matrix,
    persona_priority_categories,
)


class TestLoadMatrix:
    """매트릭스 JSON 로딩 / schema 검증 테스트."""

    def test_load_default_matrix_passes_schema(self) -> None:
        """기본 매트릭스가 schema validation 을 통과한다."""
        matrix = load_matrix()
        assert isinstance(matrix, ChronicDiseaseSupplementMatrix)
        assert matrix.schema_version == "chronic-disease-supplement-matrix-v1"
        # 43개 카테고리 모두 entry 있어야 함
        assert len(matrix.categories) == 43

    def test_load_missing_path_raises(self, tmp_path: Path) -> None:
        """존재하지 않는 경로는 FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_matrix(tmp_path / "nonexistent.json")


class TestCategoryToConditions:
    """카테고리 → 만성질환 매핑 테스트."""

    def test_omega3_strong_evidence_includes_cardiovascular_and_dyslipidemia(self) -> None:
        """오메가3 의 strong 증거에는 심혈관·고지혈증이 포함된다."""
        targets = category_to_conditions("오메가3", min_evidence="strong")
        conditions = {t.condition for t in targets}
        assert "cardiovascular" in conditions
        assert "dyslipidemia" in conditions

    def test_omega3_moderate_or_above_includes_diabetes(self) -> None:
        """오메가3 의 moderate 이상에는 당뇨도 포함된다."""
        targets = category_to_conditions("오메가3", min_evidence="moderate")
        conditions = {t.condition for t in targets}
        assert "diabetes" in conditions

    def test_unknown_category_returns_empty(self) -> None:
        """알 수 없는 카테고리는 빈 리스트."""
        targets = category_to_conditions("__no_such_category__")
        assert targets == []

    def test_category_without_targets_returns_empty(self) -> None:
        """만성질환 매핑이 없는 카테고리(BCAA_EAA)는 빈 리스트."""
        targets = category_to_conditions("BCAA_EAA")
        assert targets == []


class TestConditionsToCategories:
    """만성질환 → 카테고리 매핑 테스트."""

    def test_dyslipidemia_strong_evidence_categories(self) -> None:
        """이상지질혈증 strong 증거 카테고리는 오메가3, 식이섬유, 혈관_낫토_폴리코사놀."""
        categories = conditions_to_categories("dyslipidemia", min_evidence="strong")
        assert "오메가3" in categories
        assert "식이섬유" in categories
        assert "혈관_낫토_폴리코사놀" in categories

    def test_cardiovascular_strong_evidence_categories(self) -> None:
        """심혈관 strong 증거 카테고리는 오메가3, 코엔자임Q10, 혈관_낫토_폴리코사놀."""
        categories = conditions_to_categories("cardiovascular", min_evidence="strong")
        assert "오메가3" in categories
        assert "코엔자임Q10" in categories
        assert "혈관_낫토_폴리코사놀" in categories

    def test_osteoporosis_strong_evidence_categories(self) -> None:
        """골다공증 strong 증거에는 칼슘과 비타민D 포함."""
        categories = conditions_to_categories("osteoporosis", min_evidence="strong")
        assert "칼슘" in categories
        assert "비타민D" in categories

    def test_result_sorted_alphabetically(self) -> None:
        """결과는 사전식 정렬되어 있다."""
        categories = conditions_to_categories("cardiovascular", min_evidence="moderate")
        assert categories == sorted(categories)


class TestPersonaPriorityCategories:
    """페르소나 권장 등급 필터 테스트."""

    def test_avoid_for_chronic_includes_caffeine_and_preworkout(self) -> None:
        """만성질환자 회피 권장에는 카페인, 프리워크아웃 등이 포함된다."""
        categories = persona_priority_categories("avoid_for_chronic")
        assert "카페인_각성" in categories
        assert "프리워크아웃" in categories
        assert "크레아틴" in categories

    def test_prioritize_for_chronic_includes_omega3_and_coq10(self) -> None:
        """만성질환자 우선 권장에는 오메가3, CoQ10 포함."""
        categories = persona_priority_categories("prioritize_for_chronic")
        assert "오메가3" in categories
        assert "코엔자임Q10" in categories
        assert "혈관_낫토_폴리코사놀" in categories


class TestCategoryProfile:
    """단일 카테고리 프로필 조회 테스트."""

    def test_omega3_profile_has_cautions(self) -> None:
        """오메가3 프로필은 cautions 가 비어있지 않다."""
        profile = category_profile("오메가3")
        assert profile is not None
        assert profile.persona_recommendation == "prioritize_for_chronic"
        assert len(profile.cautions) > 0

    def test_unknown_category_returns_none(self) -> None:
        """존재하지 않는 카테고리는 None."""
        assert category_profile("__no_such_category__") is None
