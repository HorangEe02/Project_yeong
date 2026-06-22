"""Agent memory context behavior tests."""

from __future__ import annotations

from lemon_ai_agent.adapters import AgentInput, DailyHealthAgentAppAdapter
from lemon_ai_agent.app_intake import AppIntakeModule


def test_repeated_memory_pattern_prioritizes_matching_recommendation() -> None:
    """Verify injected memory can raise repeated nutrient patterns in coaching."""
    request = AgentInput(
        request_id="memory-context-test",
        user_id="local-dev-user",
        context={
            "profile": {"age": 42, "gender": "male"},
            "agent_memory": {
                "summaries": [
                    {
                        "memory_type": "daily_coaching",
                        "summary_json": {
                            "repeated_nutrient_patterns": {
                                "protein": 3,
                                "sodium": 1,
                            }
                        },
                    }
                ]
            },
        },
        payload={
            "date": "2026-05-19",
            "foods": [
                {
                    "name": "light lunch",
                    "meal_type": "lunch",
                    "nutrients": [
                        {"name": "protein", "amount": 20, "unit": "g"},
                        {"name": "sodium", "amount": 1800, "unit": "mg"},
                    ],
                }
            ],
            "sources": [{"source_type": "manual", "user_confirmed": True}],
            "reference_ranges": [
                {"nutrient": "protein", "target": 60, "unit": "g"},
                {"nutrient": "sodium", "target": 2000, "unit": "mg", "upper_limit": 2300},
            ],
        },
    )

    output = DailyHealthAgentAppAdapter().run(request)

    assert "agent_memory" in output.used_tools
    assert output.recommendations[0].title == "Add protein from food first"
    assert "appeared 3 times" in output.recommendations[0].rationale


def test_memory_pattern_accepts_canonicalized_nutrient_key() -> None:
    """Verify memory keys such as vitamin_d still match normalized findings."""
    request = AgentInput(
        request_id="memory-canonical-key-test",
        user_id="local-dev-user",
        context={
            "profile": {"age": 42, "gender": "male"},
            "agent_memory": {
                "summaries": [
                    {
                        "memory_type": "daily_coaching",
                        "summary_json": {
                            "repeated_nutrient_patterns": {
                                "vitamin_d": "2",
                            }
                        },
                    }
                ]
            },
        },
        payload={
            "date": "2026-05-19",
            "foods": [
                {
                    "name": "light breakfast",
                    "meal_type": "breakfast",
                    "nutrients": [
                        {"name": "Vitamin D", "amount": 2, "unit": "mcg"},
                    ],
                }
            ],
            "sources": [{"source_type": "manual", "user_confirmed": True}],
            "reference_ranges": [
                {"nutrient": "vitamin d", "target": 15, "unit": "mcg"},
            ],
        },
    )

    output = DailyHealthAgentAppAdapter().run(request)

    vitamin_d = next(
        item for item in output.recommendations if item.title == "Add vitamin d from food first"
    )
    assert "appeared 2 times" in vitamin_d.rationale
    assert vitamin_d.priority == 9


def test_app_intake_preserves_v2_memory_bundle_for_future_chat_context() -> None:
    """Verify v2 memory bundle survives app intake without replacing v0 summaries."""
    request = AgentInput(
        request_id="memory-bundle-test",
        user_id="local-dev-user",
        context={
            "agent_memory": {
                "schema_version": "agent-memory-summary-v1",
                "summaries": [
                    {
                        "memory_type": "daily_coaching",
                        "summary_json": {"repeated_nutrient_patterns": {"sodium": 2}},
                    }
                ],
                "memory_bundle": {
                    "profile_memory": [
                        {
                            "summary_json": {
                                "summary": "두부를 선호함.",
                                "raw_prompt": "must not be present after backend load",
                            }
                        }
                    ],
                    "behavior_memory": [],
                    "conversation_memory": [],
                    "safety_memory": [{"summary_json": {"summary": "혈압약 복용을 언급함."}}],
                },
            },
        },
        payload={
            "date": "2026-06-05",
            "foods": [],
            "sources": [{"source_type": "manual", "user_confirmed": True}],
        },
    )

    plan = AppIntakeModule().parse(request)

    assert plan.agent_memory["summaries"][0]["memory_type"] == "daily_coaching"
    assert (
        plan.agent_memory["memory_bundle"]["profile_memory"][0]["summary_json"]["summary"]
        == "두부를 선호함."
    )
    assert (
        plan.agent_memory["memory_bundle"]["safety_memory"][0]["summary_json"]["summary"]
        == "혈압약 복용을 언급함."
    )
