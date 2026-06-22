"""Tests for the Agent/LLM merge response smoke runner."""

from __future__ import annotations

from scripts import run_agent_llm_merge_smoke as smoke


def test_merge_smoke_cases_cover_answerable_boundary_unknown_and_urgent() -> None:
    """Verify the merge gate covers the response classes a teammate must inspect."""
    case_ids = {case.case_id for case in smoke.MERGE_SMOKE_CASES}

    assert {
        "answerable_sodium",
        "p0_grapefruit_statin",
        "urgent_chest_pain",
        "unknown_creatine_sleep",
    }.issubset(case_ids)


def test_merge_smoke_summarizes_safe_contract_fields_only() -> None:
    """Verify smoke output can be shared without raw prompt or full answer text."""
    result = smoke._run_case(
        smoke.SmokeCase(
            case_id="unknown-creatine",
            message="크레아틴을 먹으면 수면 질이 좋아져?",
            expected_answerability="unknown_no_reviewed_source",
            expected_provider="deterministic",
            expect_sources=False,
        ),
        llm_client=None,
    )

    assert result["case_id"] == "unknown-creatine"
    assert result["passed"] is True
    assert result["provider"] == "deterministic"
    assert result["answerability"] == "unknown_no_reviewed_source"
    assert result["source_ids"] == []
    rendered = str(result)
    assert "크레아틴" not in rendered
    assert "raw_prompt" not in rendered
    assert "message" not in result


def test_merge_smoke_fails_when_boundary_uses_llm_provider() -> None:
    """Boundary and unknown cases must fail if they route through an LLM provider."""
    result = smoke._evaluate_case_result(
        case=smoke.SmokeCase(
            case_id="bad-boundary",
            message="고지혈증 약 먹는데 자몽주스 마셔도 돼?",
            expected_answerability="medical_decision_boundary",
            expected_provider="deterministic",
        ),
        provider="sglang",
        answerability="medical_decision_boundary",
        source_ids=["mfds-drug-safety"],
        safety_warnings=["boundary_code:p0_grapefruit_statin"],
    )

    assert result["passed"] is False
    assert "provider:expected=deterministic:actual=sglang" in result["failures"]


def test_merge_smoke_strict_answerable_provider_catches_live_fallback() -> None:
    """Live SGLang checks should fail if answerable polish falls back silently."""
    result = smoke._evaluate_case_result(
        case=smoke.SmokeCase(
            case_id="answerable-sodium",
            message="오늘 나트륨을 줄이려면 어떻게 해?",
            expected_answerability="answerable",
            expect_sources=True,
            required_source_ids=("kdris-2025",),
        ),
        provider="deterministic",
        answerability="answerable",
        source_ids=["kdris-2025"],
        safety_warnings=[],
        strict_answerable_provider="sglang",
    )

    assert result["passed"] is False
    assert "provider:expected=sglang:actual=deterministic" in result["failures"]
