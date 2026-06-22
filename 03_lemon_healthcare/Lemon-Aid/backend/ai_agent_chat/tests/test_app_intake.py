"""App Intake Module behavior tests."""

from __future__ import annotations

from lemon_ai_agent.adapters import AgentInput
from lemon_ai_agent.app_intake import AppIntakeModule
from lemon_ai_agent.schemas import ReferenceRange


def test_app_intake_maps_route_payload_to_internal_agent_objects() -> None:
    request = AgentInput(
        request_id="app-intake-test",
        user_id="local-dev-user",
        context={
            "profile": {
                "age": 42,
                "gender": "female",
                "goals": ["meal_management"],
                "chronic_conditions": ["hypertension"],
                "medications": ["blood_pressure_medication"],
            },
            "agent_memory": {"summaries": [{"memory_type": "daily_coaching"}]},
        },
        payload={
            "date": "2026-05-28",
            "sources": [{"source_type": "manual", "user_confirmed": True}],
            "foods": [
                {
                    "name": "라면",
                    "meal_type": "lunch",
                    "nutrients": [{"name": "sodium", "amount": "2600", "unit": "mg"}],
                }
            ],
            "supplements": [
                {
                    "product_name": "비타민 D",
                    "ingredients": [{"name": "vitamin d", "amount": 25, "unit": "mcg"}],
                    "times_per_day": "1",
                }
            ],
            "health_trends": [
                {
                    "metric": "meal_score",
                    "direction": "down",
                    "severity": "watch",
                    "summary": "down",
                }
            ],
            "reference_ranges": [{"nutrient": "sodium", "target": 2000, "unit": "mg"}],
        },
    )

    plan = AppIntakeModule().parse(request)

    assert plan.profile.user_id == "local-dev-user"
    assert plan.profile.chronic_conditions == ["hypertension"]
    assert plan.intake.date == "2026-05-28"
    assert plan.intake.foods[0].nutrients[0].amount == 2600
    assert plan.intake.supplements[0].times_per_day == 1
    assert plan.trends[0].metric == "meal_score"
    assert plan.references[0].nutrient == "sodium"
    assert plan.agent_memory["summaries"][0]["memory_type"] == "daily_coaching"


def test_app_intake_uses_default_references_when_payload_omits_ranges() -> None:
    default_references = [ReferenceRange("protein", 60, "g")]
    request = AgentInput(
        request_id="app-intake-default-reference",
        user_id="local-dev-user",
        payload={
            "date": "2026-05-28",
            "sources": [{"source_type": "manual", "user_confirmed": True}],
            "foods": [],
        },
    )

    plan = AppIntakeModule(default_references).parse(request)

    assert plan.references == default_references
