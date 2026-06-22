from __future__ import annotations

from lemon_ai_agent.schemas import HealthTrend


class HealthTrendEngine:
    """Summarizes recent health trends without assuming specific device sources."""

    def summarize(self, trends: list[HealthTrend]) -> list[str]:
        notes: list[str] = []
        for trend in trends:
            if trend.severity == "attention":
                notes.append(f"{trend.metric}: attention needed - {trend.summary}")
            elif trend.severity == "watch":
                notes.append(f"{trend.metric}: watch - {trend.summary}")
        return notes
