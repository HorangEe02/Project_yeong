"""Plan renderer tests for chatbot and analysis surfaces."""

from __future__ import annotations

from lemon_ai_agent.answer_plan import AnalysisPlan, AnswerPlan
from lemon_ai_agent.renderers import AnalysisRenderer, ChatRenderer


def test_chat_renderer_renders_six_plan_sections_without_filler() -> None:
    """Plan rendering is concrete and separated from fixed card text."""
    plan = AnswerPlan(
        intent="meal",
        personalization_level="app_context",
        problem_axes=("sodium_high",),
        food_first_actions=("grilled fish", "tofu"),
        behavior_actions=("check soup intake",),
        safety_boundaries=("medication changes require professional confirmation",),
        source_basis=({"source_id": "kdris-2025", "source_family": "nutrition_reference"},),
        ctas=("add_checklist_item",),
    )

    message = ChatRenderer().render(plan)

    assert "현재 기록/상황 요약" in message
    assert "핵심 건강축/영양축" in message
    assert "오늘 먹을 수 있는 음식 후보" in message
    assert "줄일 음식/습관" in message
    assert "오늘 행동" in message
    assert "위험/복약/검사수치 boundary" in message
    assert "grilled fish, tofu" in message
    assert "확인된 기록을 기준으로 답변드릴 수 있습니다" not in message


def test_chat_renderer_adds_expanded_followup_context_when_requested() -> None:
    plan = AnswerPlan(
        intent="meal",
        answer_depth="expanded",
        supplement_considerations=("Vitamin D: standard_nutrient", "Herbal blend: label_only"),
        behavior_actions=("check repeated sodium meals",),
        ctas=("ask_about_this_result",),
    )

    message = ChatRenderer().render(plan)

    assert "추가 확인 지점" in message
    assert "Vitamin D: standard_nutrient" in message
    assert "Herbal blend: label_only" in message
    assert "check repeated sodium meals" in message


def test_analysis_renderer_returns_ui_sections_from_analysis_plan() -> None:
    """Analysis rendering exposes UI-ready sections instead of chat prose."""
    plan = AnalysisPlan(
        score_status="analysis_pending",
        readiness_level="level_1_initial",
        strengths=("food_records_available",),
        priority_adjustments=("sodium_high",),
        nutrient_priorities=("sodium_high",),
        recommended_foods=("tofu",),
        checklist_actions=("add water",),
        missing_records=("supplement_check",),
        safety_boundaries=("lab interpretation boundary",),
        ctas=("complete_missing_record",),
    )

    rendered = AnalysisRenderer().render(plan)

    assert rendered["score_status"] == "analysis_pending"
    assert rendered["readiness_level"] == "level_1_initial"
    assert rendered["sections"]["strengths"] == ["food_records_available"]
    assert rendered["sections"]["missing_records"] == ["supplement_check"]
    assert rendered["ctas"] == ["complete_missing_record"]
