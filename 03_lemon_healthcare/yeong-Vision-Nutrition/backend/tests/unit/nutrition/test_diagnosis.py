"""``src.nutrition.diagnosis`` 단위 테스트."""

from __future__ import annotations

from src.models.schemas.nutrition import (
    NutrientIntake,
    NutrientStatus,
    UserKDRIsContext,
)
from src.nutrition.diagnosis import diagnose
from src.safety.forbidden_terms import find_forbidden_terms


def _intake(code: str, amount: float, unit: str = "mg") -> NutrientIntake:
    return NutrientIntake(code=code, amount=amount, unit=unit, source="supplement")


def _male30() -> UserKDRIsContext:
    return UserKDRIsContext(age=30, sex="male")


def _female30_pregnant() -> UserKDRIsContext:
    return UserKDRIsContext(age=30, sex="female", is_pregnant=True)


class TestDiagnoseStatusBuckets:
    def test_deficient_below_35pct(self) -> None:
        """vitamin C 20mg / RDA 100 → ratio 0.2 → DEFICIENT."""
        result = diagnose([_intake("vitamin_c_mg", 20)], _male30())
        diag = next(d for d in result.diagnoses if d.code == "vitamin_c_mg")
        assert diag.status == NutrientStatus.DEFICIENT
        assert diag.ratio == 0.2

    def test_low_band(self) -> None:
        """vitamin C 50mg / 100 → 0.5 → LOW."""
        result = diagnose([_intake("vitamin_c_mg", 50)], _male30())
        diag = next(d for d in result.diagnoses if d.code == "vitamin_c_mg")
        assert diag.status == NutrientStatus.LOW

    def test_adequate_band(self) -> None:
        """vitamin C 80mg / 100 → 0.8 → ADEQUATE."""
        result = diagnose([_intake("vitamin_c_mg", 80)], _male30())
        diag = next(d for d in result.diagnoses if d.code == "vitamin_c_mg")
        assert diag.status == NutrientStatus.ADEQUATE

    def test_excessive_band(self) -> None:
        """vitamin C 140mg / 100 → 1.4 → EXCESSIVE (UL 2000 안전)."""
        result = diagnose([_intake("vitamin_c_mg", 140)], _male30())
        diag = next(d for d in result.diagnoses if d.code == "vitamin_c_mg")
        assert diag.status == NutrientStatus.EXCESSIVE

    def test_risky_when_above_ul(self) -> None:
        """vitamin A 5000 μg RAE / UL 3000 → RISKY."""
        result = diagnose([_intake("vitamin_a_ug_rae", 5000, unit="ug rae")], _male30())
        diag = next(d for d in result.diagnoses if d.code == "vitamin_a_ug_rae")
        assert diag.status == NutrientStatus.RISKY


class TestDiagnoseSkipsUndefined:
    def test_skip_code_not_in_kdris(self) -> None:
        result = diagnose([_intake("unknown_code_xyz", 100)], _male30())
        assert result.diagnoses == []

    def test_no_reference_value_skipped(self) -> None:
        """potassium은 AI만 있고 RDA/EAR 없음 — AI를 reference로 사용 → ADEQUATE 가능."""
        # potassium AI = 3500, intake 3500 → ratio 1.0 → ADEQUATE
        result = diagnose([_intake("potassium_mg", 3500)], _male30())
        diag = next(d for d in result.diagnoses if d.code == "potassium_mg")
        assert diag.status == NutrientStatus.ADEQUATE


class TestDiagnosePregnantContext:
    def test_pregnant_folate_uses_higher_rda(self) -> None:
        """임신부 엽산 400 μg DFE → 일반 ratio 1.0 이지만 임신부 RDA 620 기준 ratio 0.65 → LOW."""
        result = diagnose(
            [_intake("vitamin_b9_ug_dfe", 400, unit="ug dfe")],
            _female30_pregnant(),
        )
        diag = next(d for d in result.diagnoses if d.code == "vitamin_b9_ug_dfe")
        assert diag.status == NutrientStatus.LOW
        assert diag.rda == 620


class TestDiagnoseSummary:
    def test_empty_intakes_returns_zero_counts(self) -> None:
        result = diagnose([], _male30())
        assert result.diagnoses == []
        assert result.deficient_count == 0
        assert result.risky_count == 0
        assert result.adequate_count == 0

    def test_counts_accurate(self) -> None:
        result = diagnose(
            [
                _intake("vitamin_c_mg", 20),  # DEFICIENT
                _intake("calcium_mg", 600),  # ADEQUATE
                _intake("vitamin_a_ug_rae", 5000),  # RISKY
            ],
            _male30(),
        )
        assert result.deficient_count == 1
        assert result.risky_count == 1
        assert result.adequate_count == 1


class TestDiagnoseMessagesArePolicyCompliant:
    """모든 진단·요약 메시지는 의료법 금지표현을 포함하지 않는다."""

    def test_all_diagnosis_messages_pass_forbidden_term_scanner(self) -> None:
        result = diagnose(
            [
                _intake("vitamin_c_mg", 20),  # DEFICIENT
                _intake("vitamin_c_mg", 80),  # ADEQUATE — but only first counted
                _intake("vitamin_a_ug_rae", 5000),  # RISKY
                _intake("calcium_mg", 1500),  # EXCESSIVE
            ],
            _male30(),
        )
        for d in result.diagnoses:
            assert (
                find_forbidden_terms(d.message_ko) == []
            ), f"forbidden term in {d.code}: {d.message_ko}"

    def test_summary_message_passes_forbidden_term_scanner(self) -> None:
        result = diagnose([_intake("vitamin_c_mg", 50)], _male30())
        assert find_forbidden_terms(result.summary_message_ko) == []

    def test_summary_includes_expert_consultation_phrase(self) -> None:
        result = diagnose([_intake("vitamin_c_mg", 20)], _male30())
        assert "전문가" in result.summary_message_ko
