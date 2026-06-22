"""Renderer boundary tests for the grounded chatbot."""

from __future__ import annotations

from lemon_ai_agent.chat_session import ChatbotRequest
from lemon_ai_agent.chat_turn import ChatTurnModule
from lemon_ai_agent.renderers import (
    BoundaryRenderer,
    CardAnswerRenderer,
    UnknownRenderer,
)


def _turn(message: str):
    return ChatTurnModule().plan(
        ChatbotRequest(
            request_id="renderer-test",
            user_id="local-dev-user",
            message=message,
        )
    )


def test_boundary_renderer_escalates_emergency_without_sources() -> None:
    """Emergency boundary rendering is outside normal card/LLM generation."""
    warnings: list[str] = []
    response = BoundaryRenderer().render(_turn("가슴이 아프고 숨이 차"), warnings)

    assert response is not None
    assert response.provider == "deterministic"
    assert response.answerability == "urgent_escalation"
    assert "119" in response.message
    assert "Emergency escalation boundary applied" in response.safety_warnings


def test_boundary_renderer_uses_drug_safety_source_without_allow_or_ban_language() -> None:
    """P0 interaction rendering stays sourced without personal co-use conclusions."""
    warnings: list[str] = []
    response = BoundaryRenderer().render(
        _turn("고지혈증 약 먹는데 자몽주스 마셔도 돼?"),
        warnings,
    )

    assert response is not None
    assert response.answerability == "medical_decision_boundary"
    assert "위험 이유" in response.message
    assert "자몽" in response.message
    assert "먹어도 됩니다" not in response.message
    assert "안전합니다" not in response.message
    assert response.sources
    assert response.sources[0]["source_id"] == "mfds-drug-safety"
    assert "Drug interaction boundary applied" in response.safety_warnings


def test_boundary_renderer_explains_nitrate_pde5_risk_without_llm_style_conclusion() -> None:
    """High-risk nitrate/PDE5 combinations get a reason without co-use approval."""
    response = BoundaryRenderer().render(
        _turn("협심증약 먹는데 비아그라 같이 먹어도 돼?"),
        [],
    )

    assert response is not None
    assert "PDE5" in response.message
    assert "혈압" in response.message
    assert "먹어도 됩니다" not in response.message
    assert "안전합니다" not in response.message


def test_boundary_renderer_uses_lithium_source_for_selenium_supplement_question() -> None:
    """Lithium supplement co-use questions use the reviewed lithium source boundary."""
    response = BoundaryRenderer().render(
        _turn("리튬 약을 먹는데 셀레늄 영양제 같이 먹어도 돼?"),
        [],
    )

    assert response is not None
    assert response.answerability == "medical_decision_boundary"
    assert "리튬" in response.message
    assert "셀레늄" in response.message
    assert "혈중 농도" in response.message
    assert "먹어도 됩니다" not in response.message
    assert "안전합니다" not in response.message
    assert response.sources
    assert response.sources[0]["source_id"] == "medlineplus-lithium"


def test_unknown_renderer_returns_privacy_safe_unknown_message() -> None:
    """Unknown rendering does not include the original question or raw context."""
    warnings = ["no_reviewed_answer_card"]
    response = UnknownRenderer().render(
        _turn("리튬 약과 타우린 영양제 같이 먹어도 돼?"),
        warnings,
    )

    assert response.provider == "deterministic"
    assert response.answerability == "unknown_no_reviewed_source"
    assert "현재 검수된 지식 안에서 답할 수 없습니다" in response.message
    assert "리튬" not in response.message
    assert "타우린" not in response.message


def test_card_renderer_selects_sodium_actions_without_fixed_food_lists() -> None:
    """Sodium rendering stays concrete without always listing protein/vegetables."""
    response = CardAnswerRenderer().render_sodium_meal(
        _turn("오늘 저녁 나트륨을 줄이려면 어떤 음식으로 바꾸면 좋아?"),
        [],
        safe_summary="",
        confirmed_foods="",
        source_basis="KDRIs 영양 기준",
    )

    assert "국물" in response.message
    assert "소스" in response.message
    assert "김치" in response.message
    assert "두부" not in response.message
    assert "달걀" not in response.message
    assert "브로콜리" not in response.message
    assert "KDRIs 영양 기준" in response.message
