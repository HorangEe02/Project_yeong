"""AnswerPlan and AnalysisPlan contract tests."""

from __future__ import annotations

from lemon_ai_agent.answer_card import (
    AnswerCard,
    KnowledgeRetrievalResult,
)
from lemon_ai_agent.chat_session import ChatbotRequest
from lemon_ai_agent.chat_turn import ChatTurnModule


class _FakeRetriever:
    def __init__(self, card: AnswerCard) -> None:
        self._card = card

    def retrieve(self, _analysis: object) -> KnowledgeRetrievalResult:
        return KnowledgeRetrievalResult(
            cards=(self._card,),
            knowledge_items=(),
            missing_topics=(),
            warnings=(),
            retrieval_status="found",
        )


def _request(*, message: str = "What food after high sodium ramen meal?") -> ChatbotRequest:
    return ChatbotRequest(
        request_id="answer-plan-test",
        user_id="user-1",
        message=message,
        conversation=[],
        context={
            "user_health_context_snapshot": {
                "user_profile_summary": {
                    "health_axes": ["sodium", "blood_pressure"],
                    "risk_flags": ["hypertension_context"],
                },
                "health_analysis_snapshot": {"readiness_level": "level_1_initial"},
                "active_supplement_snapshot": {
                    "registered_supplements": [
                        {
                            "display_name": "Vitamin D",
                            "ingredients": [
                                {
                                    "display_name": "Vitamin D",
                                    "nutrient_code": "vitamin_d_ug",
                                    "analysis_use": "standard_nutrient",
                                },
                                {
                                    "display_name": "Herbal blend",
                                    "nutrient_code": None,
                                    "analysis_use": "label_only",
                                },
                            ],
                        }
                    ]
                },
                "recent_food_and_checklist_snapshot": {
                    "recent_food_records": [
                        {
                            "display_items": ["ramen"],
                            "estimated_tags": ["sodium_high"],
                            "rough_nutrient_axes": ["sodium_high", "carbohydrate_high"],
                        }
                    ],
                    "checklist_items": ["drink water"],
                },
            }
        },
    )


def _card() -> AnswerCard:
    return AnswerCard(
        card_id="db:sodium-dinner",
        answerability="answerable",
        topic="sodium_dinner_adjustment",
        intent="meal",
        condition="hypertension",
        allowed_guidance=("Choose lower-sodium soup and add a protein side.",),
        specific_examples=("grilled fish", "tofu", "steamed egg"),
        checklist=("check soup intake", "pick one protein food"),
        caution_conditions=("kidney disease requires separate potassium review",),
        must_not_say=("Never eat ramen", "safe for everyone"),
        source_id="kdris-2025",
        source_url="https://example.test/kdris",
        source_family="nutrition_reference",
        source_version_id="source-version-1",
        version_label="2025",
        review_status="reviewed",
        reviewed_at="2026-05-01",
        expires_at="2027-05-01",
        grounding_snippet_ids=("db:sodium-dinner",),
        source_name="KDRIs",
        concrete_guidance="Lower sodium at the next meal and choose concrete foods.",
    )


def test_chat_turn_plan_builds_answer_plan_from_context_and_answer_cards() -> None:
    turn = ChatTurnModule(retriever=_FakeRetriever(_card())).plan(_request())

    plan = turn.answer_plan

    assert plan.intent == "meal"
    assert plan.context_used == (
        "user_profile_summary",
        "health_analysis_snapshot",
        "active_supplement_snapshot",
        "recent_food_and_checklist_snapshot",
    )
    assert plan.personalization_level == "app_context"
    assert plan.readiness_level == "level_1_initial"
    assert plan.problem_axes == ("sodium", "blood_pressure", "hypertension_context")
    assert plan.nutrient_priorities == (
        "sodium_high",
        "carbohydrate_high",
        "vitamin_d_ug",
    )
    assert plan.food_first_actions == (
        "grilled fish",
        "tofu",
        "steamed egg",
    )
    assert plan.supplement_considerations == (
        "Vitamin D: standard_nutrient",
        "Herbal blend: label_only",
    )
    assert plan.behavior_actions == (
        "check soup intake",
        "pick one protein food",
        "drink water",
    )
    assert plan.safety_boundaries == ("kidney disease requires separate potassium review",)
    assert plan.source_basis == (_card().source_metadata(),)
    assert plan.ctas == ("add_checklist_item", "ask_about_this_result")
    assert plan.must_not_say == ("Never eat ramen", "safe for everyone")


def test_chat_turn_plan_builds_analysis_plan_with_missing_record_cta() -> None:
    request = _request(message="Run today's analysis")
    request.context["user_health_context_snapshot"]["recent_food_and_checklist_snapshot"] = {
        "recent_food_records": [],
        "checklist_items": [],
    }

    turn = ChatTurnModule(retriever=_FakeRetriever(_card())).plan(request)

    assert turn.analysis_plan.score_status == "analysis_pending"
    assert turn.analysis_plan.score is None
    assert turn.analysis_plan.missing_records == ("food_records",)
    assert turn.analysis_plan.ctas == ("complete_missing_record",)


def test_answer_plan_prompt_summary_excludes_forbidden_card_phrases() -> None:
    turn = ChatTurnModule(retriever=_FakeRetriever(_card())).plan(_request())

    summary = turn.answer_plan.to_prompt_summary()

    assert "context_used=user_profile_summary" in summary
    assert "source_basis=kdris-2025" in summary
    assert "Never eat ramen" not in summary
    assert "safe for everyone" not in summary


def test_answer_plan_uses_expanded_depth_for_meal_plan_and_supplement_followups() -> None:
    module = ChatTurnModule(retriever=_FakeRetriever(_card()))

    meal_plan_turn = module.plan(_request(message="식단 짜줘"))
    supplement_turn = module.plan(_request(message="영양제까지 봐줘"))

    assert meal_plan_turn.answer_plan.answer_depth == "expanded"
    assert supplement_turn.answer_plan.answer_depth == "expanded"
