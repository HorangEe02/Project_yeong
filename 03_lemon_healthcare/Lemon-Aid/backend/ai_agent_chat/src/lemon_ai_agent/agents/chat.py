from __future__ import annotations

from lemon_ai_agent.guards.safety import SafetyEnvelope, SafetyGuard
from lemon_ai_agent.llm import LLMCompletion, LLMMessage, LLMRequest, LocalLLMClient
from lemon_ai_agent.schemas import DailyCoachingResult


class ChatAgent:
    """Explains computed coaching results without exposing internal traces."""

    def __init__(self, llm_client: LocalLLMClient | None = None) -> None:
        self._completion = LLMCompletion(llm_client)
        self._has_llm_client = llm_client is not None
        self._safety_guard = SafetyGuard()
        self._safety_envelope = SafetyEnvelope(self._safety_guard)
        self.last_llm_warnings: list[str] = []
        self.last_llm_error: str | None = None
        self.last_provider = "deterministic"

    def answer(self, question: str, result: DailyCoachingResult) -> str:
        self.last_llm_warnings = []
        self.last_llm_error = None
        self.last_provider = "deterministic"
        fallback = self._deterministic_answer(result)

        if not self._has_llm_client:
            return fallback

        completion = self._completion.complete(self._build_llm_request(question, result))
        if not completion.ok:
            self.last_llm_error = completion.fallback_reason
            self.last_llm_warnings.extend(completion.warnings)
            return fallback

        safety = self._safety_envelope.screen_llm_output(
            completion.text,
            self._grounding_context(result),
        )
        self.last_llm_warnings.extend(safety.warnings)
        if not safety.allowed:
            return fallback

        self.last_provider = completion.provider
        return safety.text

    def _deterministic_answer(self, result: DailyCoachingResult) -> str:
        recommendation_titles = ", ".join(
            _ko_recommendation_title(recommendation.title)
            for recommendation in result.recommendations[:3]
        )
        _, warnings = self._safety_envelope.screen_trace(result.trace[:4])
        self.last_llm_warnings.extend(warnings)

        if not recommendation_titles:
            recommendation_titles = "오늘 우선 실행할 코칭 항목은 크지 않습니다"

        return (
            "오늘의 요약: "
            f"{result.date}에 확인된 입력과 최근 기록을 기준으로 코칭을 정리했습니다. "
            "권장 행동: "
            f"{recommendation_titles}을 먼저 확인해 주세요. "
            "참고 및 주의: "
            "이 내용은 건강 관리를 위한 참고 자료이며, 의학적 판단이 필요한 경우 "
            "자격을 갖춘 전문가와 상담해 주세요."
        )

    def _build_llm_request(
        self,
        question: str,
        result: DailyCoachingResult,
    ) -> LLMRequest:
        findings = "; ".join(
            (f"{finding.nutrient}: {finding.level.value}, " f"{finding.total_amount}{finding.unit}")
            for finding in result.findings[:3]
        )
        recommendations = "; ".join(
            f"{item.title}: {item.rationale}" for item in result.recommendations[:3]
        )
        trace_lines, warnings = self._safety_envelope.screen_trace(result.trace[:4])
        self.last_llm_warnings.extend(warnings)
        internal_notes = " / ".join(trace_lines)

        return LLMRequest(
            messages=[
                LLMMessage(
                    role="system",
                    content=(
                        "You explain Lemon Aid health-management coaching in Korean. "
                        "Answer only in Korean. Use the structure '오늘의 요약', "
                        "'권장 행동', and '참고 및 주의'. Do not diagnose, treat, "
                        "prescribe, guarantee effects, or promote buying a specific product. "
                        "Use cautious phrasing such as '현재 입력 기준', "
                        "'주의가 필요할 수 있습니다', and '전문가와 상담해 주세요'. "
                        "Do not mention or quote internal calculation logs, trace, "
                        "tool names, 'supplement totals', or 'nutrition findings'. "
                        "Do not create new health judgments beyond the supplied "
                        "findings and recommendations."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=(
                        f"Question: {question.strip()}\n"
                        f"Date: {result.date}\n"
                        f"Confirmed findings: {findings or 'none'}\n"
                        f"Recommended actions: {recommendations or 'none'}\n"
                        "Internal notes for grounding only; do not quote or mention "
                        f"them in the answer: {internal_notes or 'none'}"
                    ),
                ),
            ]
        )

    def _grounding_context(self, result: DailyCoachingResult) -> str:
        findings = "\n".join(
            f"{finding.nutrient} {finding.level.value} {finding.total_amount}{finding.unit}"
            for finding in result.findings
        )
        recommendations = "\n".join(
            f"{item.title} {item.rationale}" for item in result.recommendations
        )
        return "\n".join((findings, recommendations))


def _ko_recommendation_title(title: str) -> str:
    lowered = title.lower()
    if lowered.startswith("reduce "):
        return f"{_ko_nutrient_label(title[7:])} 섭취를 줄이는 방향"
    if lowered.startswith("add ") and " from food first" in lowered:
        nutrient = lowered.removeprefix("add ").removesuffix(" from food first")
        return f"{_ko_nutrient_label(nutrient)}을 음식으로 먼저 보완하는 방향"
    if lowered.startswith("consider ") and " ingredient support" in lowered:
        nutrient = lowered.removeprefix("consider ").removesuffix(" ingredient support")
        return f"{_ko_nutrient_label(nutrient)} 보충 필요성을 신중히 확인하는 방향"
    return title


def _ko_nutrient_label(nutrient: str) -> str:
    normalized = " ".join(nutrient.strip().lower().replace("_", " ").split())
    labels = {
        "vitamin d": "비타민 D",
        "sodium": "나트륨",
        "protein": "단백질",
        "fiber": "식이섬유",
        "magnesium": "마그네슘",
        "calcium": "칼슘",
        "iron": "철분",
        "omega-3": "오메가-3",
    }
    return labels.get(normalized, nutrient.strip())
