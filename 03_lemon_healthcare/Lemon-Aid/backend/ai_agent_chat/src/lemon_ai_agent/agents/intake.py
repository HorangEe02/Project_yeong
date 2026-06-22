from __future__ import annotations

from lemon_ai_agent.schemas import DailyIntake


class IntakeAgent:
    """Accepts already-structured OCR intake data for this workspace version."""

    def normalize(self, intake: DailyIntake) -> DailyIntake:
        return intake
