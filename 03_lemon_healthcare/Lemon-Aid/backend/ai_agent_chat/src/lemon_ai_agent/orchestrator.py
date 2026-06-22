from __future__ import annotations

from typing import Any

from lemon_ai_agent.agents.action import ActionAgent
from lemon_ai_agent.agents.coaching import CoachingAgent
from lemon_ai_agent.agents.intake import IntakeAgent
from lemon_ai_agent.agents.personalization import PersonalizationAgent
from lemon_ai_agent.engines.nutrition import NutritionEngine
from lemon_ai_agent.engines.supplement import SupplementEngine
from lemon_ai_agent.guards.safety import SafetyGuard
from lemon_ai_agent.schemas import (
    DailyCoachingResult,
    DailyIntake,
    HealthTrend,
    ReferenceRange,
    UserProfile,
)


class DailyHealthAgent:
    """Coordinates deterministic engines, Agent logic, and safety checks."""

    def __init__(self, references: list[ReferenceRange]) -> None:
        self._intake_agent = IntakeAgent()
        self._nutrition_engine = NutritionEngine(references)
        self._supplement_engine = SupplementEngine()
        self._personalization_agent = PersonalizationAgent()
        self._coaching_agent = CoachingAgent()
        self._action_agent = ActionAgent()
        self._safety_guard = SafetyGuard()

    def run(
        self,
        profile: UserProfile,
        intake: DailyIntake,
        trends: list[HealthTrend] | None = None,
        agent_memory: dict[str, Any] | None = None,
    ) -> DailyCoachingResult:
        normalized = self._intake_agent.normalize(intake)
        if self._requires_confirmation(normalized):
            trace, trace_warnings = self._safety_guard.sanitize_trace(
                [
                    (
                        "intake requires user confirmation: "
                        f"unconfirmed OCR source records: "
                        f"{self._unconfirmed_ocr_source_count(normalized)}"
                    )
                ]
            )
            return DailyCoachingResult(
                user_id=profile.user_id,
                date=normalized.date,
                findings=[],
                recommendations=[],
                actions=[],
                safety_warnings=trace_warnings,
                sources=normalized.sources,
                supplement_totals=[],
                trace=trace,
                approval_status="requires_confirmation",
            )

        supplement_totals = self._supplement_engine.evaluate(normalized)
        findings = self._nutrition_engine.evaluate(normalized)
        context = self._personalization_agent.build_context(
            profile,
            trends or [],
            agent_memory=agent_memory,
        )
        recommendations = self._coaching_agent.recommend(findings, context)

        safety_warnings: list[str] = []
        checked_recommendations = []
        for recommendation in recommendations:
            check = self._safety_guard.check_text(
                f"{recommendation.title} {recommendation.rationale}"
            )
            safety_warnings.extend(check.warnings)
            checked_recommendations.append((recommendation, check))

        safe_recommendations = [
            recommendation for recommendation, check in checked_recommendations if check.allowed
        ]
        actions = self._action_agent.propose_actions(safe_recommendations)
        trace = self._build_trace(
            normalized=normalized,
            findings=findings,
            context=context,
            supplement_totals=supplement_totals,
            safety_warnings=safety_warnings,
        )
        trace, trace_warnings = self._safety_guard.sanitize_trace(trace)
        safety_warnings.extend(trace_warnings)

        return DailyCoachingResult(
            user_id=profile.user_id,
            date=normalized.date,
            findings=findings,
            recommendations=safe_recommendations,
            actions=actions,
            safety_warnings=safety_warnings,
            sources=normalized.sources,
            supplement_totals=supplement_totals,
            trace=trace,
        )

    def _requires_confirmation(self, intake: DailyIntake) -> bool:
        return self._unconfirmed_ocr_source_count(intake) > 0

    def _unconfirmed_ocr_source_count(self, intake: DailyIntake) -> int:
        return sum(
            1
            for source in intake.sources
            if source.source_type in {"food_ocr", "supplement_ocr"} and not source.user_confirmed
        )

    def _build_trace(
        self,
        normalized: DailyIntake,
        findings,
        context,
        supplement_totals,
        safety_warnings: list[str],
    ) -> list[str]:
        confirmed_sources = sum(1 for source in normalized.sources if source.user_confirmed)
        finding_summary = ", ".join(
            f"{finding.nutrient}={finding.level.value}" for finding in findings
        )
        supplement_summary = ", ".join(
            f"{item.ingredient}={item.total_amount}{item.unit}" for item in supplement_totals
        )
        trend_summary = ", ".join(context.health_trend_notes)

        return [
            (
                "intake normalized: "
                f"foods={len(normalized.foods)}, supplements={len(normalized.supplements)}, "
                f"confirmed source records: {confirmed_sources}"
            ),
            f"supplement totals: {supplement_summary or 'none'}",
            f"nutrition findings: {finding_summary or 'none'}",
            (
                "user context: "
                f"cautions={len(context.caution_tags)}, "
                f"medications={len(context.medication_notes)}, "
                f"trends={trend_summary or 'none'}"
            ),
            f"policy guard warnings: {len(safety_warnings)}",
        ]
