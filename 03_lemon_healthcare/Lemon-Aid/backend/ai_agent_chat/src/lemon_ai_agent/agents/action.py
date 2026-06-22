from __future__ import annotations

from lemon_ai_agent.schemas import CoachingRecommendation, ProposedAction


class ActionAgent:
    def propose_actions(
        self, recommendations: list[CoachingRecommendation]
    ) -> list[ProposedAction]:
        actions: list[ProposedAction] = []
        for recommendation in recommendations:
            if recommendation.requires_professional_consult:
                actions.append(
                    ProposedAction(
                        action_type="professional_consult",
                        title=f"Review with a professional: {recommendation.title}",
                        payload={"source": recommendation.title},
                    )
                )
            if recommendation.category in {"consider_ingredient", "reminder"}:
                actions.append(
                    ProposedAction(
                        action_type="supplement_reminder",
                        title=f"알림 제안: {recommendation.title}",
                        payload={"source": recommendation.title},
                    )
                )
            elif recommendation.category == "mission":
                actions.append(
                    ProposedAction(
                        action_type="daily_mission",
                        title=recommendation.title,
                        payload={"rationale": recommendation.rationale},
                    )
                )
        return actions
