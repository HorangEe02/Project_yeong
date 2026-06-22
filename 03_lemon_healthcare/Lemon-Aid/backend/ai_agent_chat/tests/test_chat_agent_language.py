"""Chat agent Korean response behavior tests."""

from __future__ import annotations

from lemon_ai_agent.agents.chat import ChatAgent
from lemon_ai_agent.llm import LLMRequest, LLMResponse
from lemon_ai_agent.schemas import (
    CoachingRecommendation,
    DailyCoachingResult,
    FindingLevel,
    NutrientFinding,
)


class _CapturingLLMClient:
    provider = "fake"

    def __init__(
        self,
        text: str = (
            "오늘의 요약: 현재 입력 기준으로 비타민 D 섭취량을 확인했습니다. "
            "권장 행동: 섭취량을 조정해 주세요. "
            "참고 및 주의: 전문가와 상담해 주세요."
        ),
    ) -> None:
        self.request: LLMRequest | None = None
        self.text = text

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.request = request
        return LLMResponse(
            text=self.text,
            provider=self.provider,
            model="fake-ko",
        )


def _result() -> DailyCoachingResult:
    return DailyCoachingResult(
        user_id="local-dev-user",
        date="2026-05-21",
        findings=[
            NutrientFinding(
                nutrient="vitamin d",
                total_amount=25,
                unit="mcg",
                ratio_to_target=1.667,
                level=FindingLevel.HIGH,
                message="vitamin d intake is above the target range.",
            )
        ],
        recommendations=[
            CoachingRecommendation(
                category="reduce",
                title="Reduce vitamin d",
                rationale="vitamin d intake is above the target range.",
                priority=8,
            )
        ],
        actions=[],
        safety_warnings=[],
        trace=["supplement totals: vitamin d=25.0mcg"],
    )


def test_deterministic_fallback_answers_in_korean() -> None:
    """Verify fallback coaching text is Korean even without a live LLM."""
    message = ChatAgent().answer("오늘 코칭 내용을 요약해 주세요.", _result())

    assert "확인된 입력" in message
    assert "비타민 D" in message
    assert "전문가와 상담" in message
    assert "오늘의 요약" in message
    assert "권장 행동" in message
    assert "참고 및 주의" in message
    assert "supplement totals" not in message
    assert "nutrition findings" not in message
    assert "Trace" not in message
    assert "For your question" not in message


def test_llm_prompt_requires_korean_answer_and_hides_internal_logs() -> None:
    """Verify live LLM prompts request Korean output and hide internal logs."""
    client = _CapturingLLMClient()
    message = ChatAgent(llm_client=client).answer(
        "오늘 코칭 내용을 요약해 주세요.",
        _result(),
    )

    assert message.startswith("오늘의 요약")
    assert client.request is not None
    system_prompt = client.request.messages[0].content
    user_prompt = client.request.messages[1].content
    assert "Answer only in Korean" in system_prompt
    assert "오늘의 요약" in system_prompt
    assert "권장 행동" in system_prompt
    assert "참고 및 주의" in system_prompt
    assert "전문가와 상담해 주세요" in system_prompt
    assert "Do not mention or quote internal calculation logs" in system_prompt
    assert (
        "Do not create new health judgments beyond the supplied findings and recommendations"
        in system_prompt
    )
    assert "supplement totals" in system_prompt
    assert "nutrition findings" in system_prompt
    assert "Trace summary" not in user_prompt
    assert "Internal notes for grounding only" in user_prompt


def test_unsafe_llm_output_falls_back_to_safe_korean_message() -> None:
    """Verify unsafe LLM output is blocked and deterministic fallback is returned."""
    client = _CapturingLLMClient(text="당뇨입니다. 이 제품을 구매하세요.")
    agent = ChatAgent(llm_client=client)

    message = agent.answer("오늘 코칭 내용을 요약해 주세요.", _result())

    assert agent.last_provider == "deterministic"
    assert "오늘의 요약" in message
    assert "비타민 D" in message
    assert "당뇨입니다" not in message
    assert "구매하세요" not in message
    assert "Forbidden medical expression detected" in agent.last_llm_warnings


def test_unsupported_evidence_claim_falls_back_to_deterministic_message() -> None:
    """Verify daily coaching LLM output cannot add unsupported evidence claims."""
    client = _CapturingLLMClient(text="임상시험에서 비타민 D가 혈압을 낮춥니다.")
    agent = ChatAgent(llm_client=client)

    message = agent.answer("오늘 코칭 내용을 요약해 주세요.", _result())

    assert agent.last_provider == "deterministic"
    assert "임상시험" not in message
    assert "혈압을 낮춥니다" not in message
    assert "Unsupported medical fact detected" in agent.last_llm_warnings


def test_empty_llm_output_falls_back_to_deterministic_message() -> None:
    """Verify empty model text is handled before safety checks."""
    client = _CapturingLLMClient(text=" ")
    agent = ChatAgent(llm_client=client)

    message = agent.answer("오늘 코칭 내용을 요약해 주세요.", _result())

    assert agent.last_provider == "deterministic"
    assert agent.last_llm_error == "llm_empty_response"
    assert "LLM response text was empty" in agent.last_llm_warnings
    assert "오늘의 요약" in message
