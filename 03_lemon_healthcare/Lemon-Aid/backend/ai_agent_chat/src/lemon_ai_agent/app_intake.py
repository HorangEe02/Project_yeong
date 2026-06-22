from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lemon_ai_agent.schemas import (
    DailyIntake,
    FoodIntake,
    HealthTrend,
    IntakeSource,
    NutrientAmount,
    ReferenceRange,
    SupplementIntake,
    UserProfile,
)


@dataclass(frozen=True)
class AppIntakePlan:
    profile: UserProfile
    intake: DailyIntake
    references: list[ReferenceRange]
    trends: list[HealthTrend]
    agent_memory: dict[str, Any]


class AppIntakeModule:
    """Maps app-owned request dictionaries to internal agent input objects."""

    def __init__(self, default_references: list[ReferenceRange] | None = None) -> None:
        self._default_references = default_references or []

    def parse(self, agent_input: Any) -> AppIntakePlan:
        return AppIntakePlan(
            profile=self._build_profile(agent_input),
            intake=self._build_intake(agent_input),
            references=self._build_references(agent_input.payload),
            trends=self._build_trends(agent_input.payload),
            agent_memory=self._build_agent_memory(agent_input),
        )

    def _build_profile(self, agent_input: Any) -> UserProfile:
        profile = agent_input.context.get("profile", agent_input.context)
        return UserProfile(
            user_id=agent_input.user_id,
            age=int(profile.get("age", 0)),
            gender=profile.get("gender", "other"),
            goals=list(profile.get("goals", [])),
            chronic_conditions=list(profile.get("chronic_conditions", [])),
            medications=list(profile.get("medications", [])),
        )

    def _build_intake(self, agent_input: Any) -> DailyIntake:
        payload = agent_input.payload
        return DailyIntake(
            user_id=agent_input.user_id,
            date=str(payload["date"]),
            sources=[self._build_source(item) for item in payload.get("sources", [])],
            foods=[self._build_food(item) for item in payload.get("foods", [])],
            supplements=[self._build_supplement(item) for item in payload.get("supplements", [])],
        )

    def _build_references(self, payload: dict[str, Any]) -> list[ReferenceRange]:
        if "reference_ranges" not in payload:
            return self._default_references

        return [
            ReferenceRange(
                nutrient=str(item["nutrient"]),
                target=float(item["target"]),
                unit=str(item["unit"]),
                upper_limit=(
                    None if item.get("upper_limit") is None else float(item["upper_limit"])
                ),
            )
            for item in payload.get("reference_ranges", [])
        ]

    def _build_trends(self, payload: dict[str, Any]) -> list[HealthTrend]:
        return [
            HealthTrend(
                metric=str(item["metric"]),
                direction=item.get("direction", "unknown"),
                severity=item.get("severity", "info"),
                summary=str(item.get("summary", "")),
            )
            for item in payload.get("health_trends", [])
        ]

    def _build_agent_memory(self, agent_input: Any) -> dict[str, Any]:
        memory = agent_input.context.get("agent_memory", {})
        return memory if isinstance(memory, dict) else {}

    def _build_source(self, item: dict[str, Any]) -> IntakeSource:
        return IntakeSource(
            source_type=item["source_type"],
            image_id=item.get("image_id"),
            raw_ocr_text=item.get("raw_ocr_text"),
            user_confirmed=bool(item.get("user_confirmed", False)),
        )

    def _build_food(self, item: dict[str, Any]) -> FoodIntake:
        return FoodIntake(
            name=str(item["name"]),
            meal_type=item["meal_type"],
            serving_label=str(item.get("serving_label", "")),
            nutrients=[self._build_nutrient(nutrient) for nutrient in item.get("nutrients", [])],
        )

    def _build_supplement(self, item: dict[str, Any]) -> SupplementIntake:
        return SupplementIntake(
            product_name=str(item["product_name"]),
            ingredients=[
                self._build_nutrient(ingredient) for ingredient in item.get("ingredients", [])
            ],
            times_per_day=int(item.get("times_per_day", 1)),
        )

    def _build_nutrient(self, item: dict[str, Any]) -> NutrientAmount:
        return NutrientAmount(
            name=str(item["name"]),
            amount=float(item["amount"]),
            unit=str(item["unit"]),
        )
