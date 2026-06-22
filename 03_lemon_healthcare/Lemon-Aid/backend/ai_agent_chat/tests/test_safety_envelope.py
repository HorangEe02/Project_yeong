"""Safety Envelope Module behavior tests."""

from __future__ import annotations

from lemon_ai_agent.guards.safety import SafetyEnvelope


def test_safety_envelope_screens_text_and_grounding_together() -> None:
    result = SafetyEnvelope().screen_llm_output(
        "임상시험에서 이 영양제가 혈압을 낮춥니다.",
        grounding_context="영양제 라벨을 확인하세요.",
    )

    assert result.allowed is False
    assert result.text == ""
    assert "Unsupported medical fact detected" in result.warnings


def test_safety_envelope_allows_grounded_numeric_claim() -> None:
    result = SafetyEnvelope().screen_llm_output(
        "현재 입력 기준으로 나트륨 2600mg이 확인됩니다.",
        grounding_context="점심: 라면, 나트륨 2600mg",
    )

    assert result.allowed is True
    assert result.text == "현재 입력 기준으로 나트륨 2600mg이 확인됩니다."
    assert result.warnings == ()


def test_safety_envelope_screens_plain_text_with_replacement() -> None:
    result = SafetyEnvelope().screen_text("당뇨입니다. 이 제품을 구매하세요.")

    assert result.allowed is False
    assert result.text == "text withheld by policy guard"
    assert "Forbidden medical expression detected" in result.warnings


def test_safety_envelope_screens_trace() -> None:
    trace, warnings = SafetyEnvelope().screen_trace(["safe trace", "diabetes diagnosis"])

    assert trace == ["safe trace", "trace item withheld by policy guard"]
    assert "Trace text blocked: Forbidden medical expression detected" in warnings
