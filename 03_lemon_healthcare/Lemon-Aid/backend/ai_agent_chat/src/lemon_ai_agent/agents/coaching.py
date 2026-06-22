from __future__ import annotations

from lemon_ai_agent.schemas import (
    CoachingRecommendation,
    FindingLevel,
    NutrientFinding,
    PersonalizationContext,
)

FOOD_FIRST_SUGGESTIONS = {
    "protein": "Add protein-rich foods such as tofu, eggs, fish, or chicken.",
    "fiber": "Add fiber-rich foods such as vegetables, beans, oats, or seaweed.",
    "vitamin d": "Consider vitamin D-rich foods such as eggs or fortified foods.",
    "magnesium": "Add magnesium-rich foods such as nuts, beans, or leafy vegetables.",
}

SUPPLEMENT_INGREDIENT_ALLOWED = {
    "vitamin d",
    "magnesium",
    "omega-3",
    "iron",
    "calcium",
}
REPEATED_PATTERN_THRESHOLD = 2


class CoachingAgent:
    def recommend(
        self,
        findings: list[NutrientFinding],
        context: PersonalizationContext,
    ) -> list[CoachingRecommendation]:
        recommendations: list[CoachingRecommendation] = []
        memory_patterns = _memory_patterns(context.agent_memory)

        for finding in findings:
            nutrient_key = finding.nutrient.lower()
            repeat_count = memory_patterns.get(nutrient_key, 0)
            repeat_prefix = (
                f" This pattern has appeared {repeat_count} times in recent confirmed records."
                if repeat_count >= REPEATED_PATTERN_THRESHOLD
                else ""
            )
            if finding.level in {FindingLevel.HIGH, FindingLevel.RISKY}:
                recommendations.append(
                    CoachingRecommendation(
                        category="reduce",
                        title=f"Reduce {finding.nutrient}",
                        rationale=f"{finding.message}{repeat_prefix}",
                        priority=min(
                            10,
                            (10 if finding.level == FindingLevel.RISKY else 8)
                            + min(repeat_count, 2),
                        ),
                        requires_professional_consult=finding.level == FindingLevel.RISKY,
                    )
                )
            elif finding.level == FindingLevel.LOW:
                food_text = FOOD_FIRST_SUGGESTIONS.get(
                    nutrient_key,
                    f"Add foods that provide {finding.nutrient}.",
                )
                recommendations.append(
                    CoachingRecommendation(
                        category="add_food",
                        title=f"Add {finding.nutrient} from food first",
                        rationale=f"{finding.message} {food_text}{repeat_prefix}",
                        priority=min(10, 7 + min(repeat_count, 2)),
                    )
                )
                if nutrient_key in SUPPLEMENT_INGREDIENT_ALLOWED:
                    recommendations.append(
                        CoachingRecommendation(
                            category="consider_ingredient",
                            title=f"Consider {finding.nutrient} ingredient support",
                            rationale=(
                                "If food intake is difficult, consider this ingredient "
                                "with professional review when medication or chronic "
                                "condition context exists."
                            ),
                            priority=5,
                            requires_professional_consult=bool(
                                context.medication_notes or context.caution_tags
                            ),
                        )
                    )

        if context.health_trend_notes:
            recommendations.append(
                CoachingRecommendation(
                    category="mission",
                    title="Follow a small meal-management mission today",
                    rationale="Recent trend signals need attention: "
                    + " / ".join(context.health_trend_notes),
                    priority=6,
                )
            )

        return sorted(recommendations, key=lambda item: item.priority, reverse=True)


def _memory_patterns(agent_memory: dict[str, object]) -> dict[str, int]:
    """Return repeated nutrient pattern counters from injected Agent memory."""
    summaries = agent_memory.get("summaries", [])
    if not isinstance(summaries, list):
        return {}

    counters: dict[str, int] = {}
    for item in summaries:
        if not isinstance(item, dict):
            continue
        summary = item.get("summary_json", {})
        if not isinstance(summary, dict):
            continue
        patterns = summary.get("repeated_nutrient_patterns", {})
        if not isinstance(patterns, dict):
            continue
        for nutrient, count in patterns.items():
            if not isinstance(nutrient, str):
                continue
            try:
                repeat_count = int(count)
            except (TypeError, ValueError):
                continue
            key = _canonical_memory_nutrient_key(nutrient)
            counters[key] = max(counters.get(key, 0), repeat_count)
    return counters


def _canonical_memory_nutrient_key(nutrient: str) -> str:
    normalized = " ".join(nutrient.strip().lower().replace("_", " ").split())
    aliases = {
        "vitamin-d": "vitamin d",
        "vitamin d": "vitamin d",
    }
    return aliases.get(normalized, normalized)
