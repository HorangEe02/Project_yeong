"""Tests for local chatbot QA helper presets."""

from __future__ import annotations

from lemon_ai_agent.agents.chatbot import ChatbotAgent
from lemon_ai_agent.chat_session import ChatbotRequest

from scripts import ask_chatbot_agent as ask


def test_ask_chatbot_agent_presets_are_readable_korean_scenarios() -> None:
    """Preset prompts should remain useful for manual Korean chatbot QA."""
    assert "당뇨" in ask.PRESETS["diabetes-high-carb"]["message"]
    assert "운동" in ask.PRESETS["exercise-dizziness"]["message"]
    assert "고혈압" in ask.PRESETS["hypertension-kimchi-stew"]["message"]
    assert "김치찌개" in ask.PRESETS["hypertension-kimchi-stew"]["message"]
    assert "마그네슘" in ask.PRESETS["supplement-drug-boundary"]["message"]
    assert "나트륨" in ask.PRESETS["hypertension-sodium-dinner"]["message"]
    assert "자몽" in ask.PRESETS["p0-grapefruit-lipid-med"]["message"]
    assert "신장질환" in ask.PRESETS["kidney-vegetable-fruit-potassium"]["message"]
    assert "칼륨" in ask.PRESETS["kidney-vegetable-fruit-potassium"]["message"]
    assert "당뇨" in ask.PRESETS["diabetes-overeating-next-meal"]["message"]
    assert "초콜릿" in ask.PRESETS["diabetes-overeating-next-meal"]["message"]
    assert "리튬" in ask.PRESETS["unknown-lithium-selenium"]["message"]
    assert "가슴" in ask.PRESETS["urgent-chest-pain"]["message"]
    assert "LDL" in ask.PRESETS["ldl-treatment"]["message"]


def test_ask_chatbot_agent_key_presets_keep_expected_answerability() -> None:
    """Manual QA presets should keep routing to the intended chatbot behavior."""
    expectations = {
        "hypertension-kimchi-stew": "answerable",
        "hypertension-sodium-dinner": "answerable",
        "supplement-drug-boundary": "answerable_with_caution",
        "magnesium-blood-pressure-med": "answerable_with_caution",
        "p0-grapefruit-lipid-med": "medical_decision_boundary",
        "kidney-vegetable-fruit-potassium": "answerable",
        "diabetes-overeating-next-meal": "answerable",
        "unknown-lithium-selenium": "medical_decision_boundary",
        "exercise-dizziness-red-flags": "urgent_escalation",
        "urgent-chest-pain": "urgent_escalation",
        "ldl-treatment": "medical_decision_boundary",
    }

    for preset_name, expected_answerability in expectations.items():
        preset = ask.PRESETS[preset_name]
        response = ChatbotAgent().answer(
            ChatbotRequest(
                request_id=f"preset-contract-{preset_name}",
                user_id="preset-contract-user",
                message=str(preset["message"]),
                context=dict(preset["context"]),
            )
        )

        assert response.answerability == expected_answerability
