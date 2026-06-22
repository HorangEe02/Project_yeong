"""Action proposal boundary tests."""

from __future__ import annotations

from lemon_ai_agent.agents.action import ActionAgent
from lemon_ai_agent.schemas import CoachingRecommendation


def test_reminder_recommendation_proposes_user_approved_action() -> None:
    """Verify reminder suggestions never enable reminders without approval."""
    actions = ActionAgent().propose_actions(
        [
            CoachingRecommendation(
                category="reminder",
                title="영양제 기록 시간 확인",
                rationale="사용자가 승인하면 알림으로 전환할 수 있습니다.",
                priority=4,
            )
        ]
    )

    assert len(actions) == 1
    assert actions[0].action_type == "supplement_reminder"
    assert actions[0].requires_user_approval is True
    assert actions[0].payload["source"] == "영양제 기록 시간 확인"
