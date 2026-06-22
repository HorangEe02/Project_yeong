from __future__ import annotations

from typing import Any

from lemon_ai_agent.engines.health_trend import HealthTrendEngine
from lemon_ai_agent.schemas import HealthTrend, PersonalizationContext, UserProfile


class PersonalizationAgent:
    def __init__(self, trend_engine: HealthTrendEngine | None = None) -> None:
        self._trend_engine = trend_engine or HealthTrendEngine()

    def build_context(
        self,
        profile: UserProfile,
        trends: list[HealthTrend],
        agent_memory: dict[str, Any] | None = None,
    ) -> PersonalizationContext:
        caution_tags = list(profile.chronic_conditions)
        medication_notes = [
            f"Medication context present: {medication}" for medication in profile.medications
        ]
        return PersonalizationContext(
            user_id=profile.user_id,
            goals=profile.goals,
            caution_tags=caution_tags,
            health_trend_notes=self._trend_engine.summarize(trends),
            medication_notes=medication_notes,
            agent_memory=agent_memory or {},
        )
