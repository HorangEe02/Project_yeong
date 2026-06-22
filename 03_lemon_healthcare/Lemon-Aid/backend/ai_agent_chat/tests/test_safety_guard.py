"""Safety guard regression tests for medical-boundary language."""

from __future__ import annotations

import pytest
from lemon_ai_agent.guards.safety import SafetyGuard


@pytest.mark.parametrize(
    "text",
    [
        "당뇨입니다. 이 식단으로 치료하세요.",
        "혈압약은 오늘부터 약을 중단하세요.",
        "이 영양제를 먹고 약을 끊으세요.",
        "복용량을 바꾸세요.",
        "현재 약 용량을 늘리세요.",
        "고혈압이 있으면 라면을 먹는 것은 안 돼요.",
        "고혈압이 있으면 라면을 먹지 않아야 합니다.",
        "Take more of this medicine.",
        "Stop taking your medicine.",
    ],
)
def test_safety_guard_blocks_diagnosis_treatment_and_medication_changes(text: str) -> None:
    """Verify user-facing LLM text cannot direct diagnosis or medication changes."""
    result = SafetyGuard().check_text(text)

    assert result.allowed is False
    assert "Forbidden medical expression detected" in result.warnings


def test_safety_guard_allows_professional_consult_boundary_language() -> None:
    """Verify safe professional-consult wording can mention medication boundaries."""
    result = SafetyGuard().check_text(
        "복용 중인 약이나 영양제 조정은 의사 또는 약사와 상담해 주세요."
    )

    assert result.allowed is True
    assert result.warnings == []


@pytest.mark.parametrize(
    "text",
    [
        "먹어도 되는지 여부는 약 종류와 상태에 따라 달라질 수 있습니다.",
        "제품 라벨의 마그네슘 함량을 확인하세요.",
    ],
)
def test_safety_guard_allows_actionable_caution_language(text: str) -> None:
    """Verify useful caution wording is not blocked as an allow/ban decision."""
    result = SafetyGuard().check_text(text)

    assert result.allowed is True
    assert result.warnings == []


@pytest.mark.parametrize(
    "text",
    [
        "혈압약과 함께 먹어도 됩니다.",
        "혈압약을 줄이세요.",
        "라면은 절대 먹지 마세요.",
    ],
)
def test_safety_guard_blocks_personal_allow_ban_and_med_change_language(text: str) -> None:
    """Verify personal co-use conclusions and medication changes are blocked."""
    result = SafetyGuard().check_text(text)

    assert result.allowed is False
    assert "Forbidden medical expression detected" in result.warnings


def test_safety_guard_blocks_unsupported_evidence_claims() -> None:
    """Verify evidence/effect claims must be present in the grounding context."""
    result = SafetyGuard().check_grounding(
        "연구에 따르면 오메가3는 혈압을 낮춥니다.",
        allowed_context="현재 입력 기준으로 나트륨 섭취가 높을 수 있습니다.",
    )

    assert result.allowed is False
    assert "Unsupported medical fact detected" in result.warnings


def test_safety_guard_blocks_unsupported_numeric_health_claims() -> None:
    """Verify LLM output cannot invent dosage or lab-value claims."""
    result = SafetyGuard().check_grounding(
        "Vitamin D 4000 IU is safe for everyone and LDL 130 mg/dL is high.",
        allowed_context="The user reported taking vitamin D but no dosage or lab values were supplied.",
    )

    assert result.allowed is False
    assert "Unsupported numeric medical claim detected" in result.warnings


def test_safety_guard_blocks_unsupported_numeric_ranges() -> None:
    """Verify invented range-style nutrient targets are treated as numeric claims."""
    result = SafetyGuard().check_grounding(
        "다음 끼니에서는 나트륨을 200-300mg으로 맞추세요.",
        allowed_context="Confirmed meal: lunch ramen sodium 2600mg.",
    )

    assert result.allowed is False
    assert "Unsupported numeric medical claim detected" in result.warnings


def test_safety_guard_allows_grounded_numbers_with_spacing_difference() -> None:
    """Verify supplied amounts can be repeated even when spacing differs."""
    result = SafetyGuard().check_grounding(
        "확인된 나트륨은 2600 mg입니다.",
        allowed_context="점심: 라면, 나트륨 2600mg",
    )

    assert result.allowed is True
    assert result.warnings == []


def test_safety_guard_allows_grounded_evidence_terms() -> None:
    """Verify evidence terms are allowed when already present in context."""
    result = SafetyGuard().check_grounding(
        "현재 메모에 따르면 임상시험 관련 자료는 사용하지 않습니다.",
        allowed_context="임상시험 관련 자료는 사용하지 않습니다.",
    )

    assert result.allowed is True
    assert result.warnings == []


def test_safety_guard_allows_grounded_numeric_health_claims() -> None:
    """Verify supplied amounts can be repeated when already present in context."""
    result = SafetyGuard().check_grounding(
        "The confirmed intake includes vitamin D 25 mcg.",
        allowed_context="Confirmed findings: vitamin D adequate 25 mcg.",
    )

    assert result.allowed is True
    assert result.warnings == []


def test_safety_guard_blocks_answer_card_must_not_say_phrases() -> None:
    """Verify card-specific blocked wording can be enforced after generation."""
    result = SafetyGuard().check_forbidden_phrases(
        "이 제품은 누구에게나 안전합니다.",
        forbidden_phrases=("누구에게나 안전합니다", "약 대신 드세요"),
    )

    assert result.allowed is False
    assert "Answer card forbidden phrase detected" in result.warnings
