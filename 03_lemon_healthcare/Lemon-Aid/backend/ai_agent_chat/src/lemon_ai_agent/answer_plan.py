"""Planning contracts shared by chatbot and analysis rendering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from lemon_ai_agent.answer_card import AnswerCard
from lemon_ai_agent.chat_session import ChatbotRequest
from lemon_ai_agent.knowledge import ChatIntentAnalysis

AnswerDepth = Literal["brief", "standard", "expanded"]
PersonalizationLevel = Literal["general", "reviewed_evidence_only", "app_context"]
ScoreStatus = Literal["analysis_pending", "ready_for_analysis"]
BRIEF_ANSWER_MESSAGE_MAX_CHARS = 24
EXPANDED_ANSWER_TERMS = (
    "why",
    "detail",
    "meal plan",
    "supplements too",
    "자세히",
    "왜",
    "식단 짜",
    "식단짜",
    "영양제까지",
)


@dataclass(frozen=True)
class AnswerPlan:
    """Question-level plan built before LLM or deterministic rendering."""

    intent: str
    answer_depth: AnswerDepth = "standard"
    context_used: tuple[str, ...] = ()
    personalization_level: PersonalizationLevel = "general"
    readiness_level: str = "level_0_preparing"
    problem_axes: tuple[str, ...] = ()
    nutrient_priorities: tuple[str, ...] = ()
    food_first_actions: tuple[str, ...] = ()
    supplement_considerations: tuple[str, ...] = ()
    behavior_actions: tuple[str, ...] = ()
    safety_boundaries: tuple[str, ...] = ()
    source_basis: tuple[dict[str, str], ...] = ()
    ctas: tuple[str, ...] = ()
    must_not_say: tuple[str, ...] = ()

    def to_prompt_summary(self) -> str:
        """Return compact plan details for LLM grounding without forbidden wording."""
        return "\n".join(
            (
                f"intent={self.intent}",
                f"answer_depth={self.answer_depth}",
                f"context_used={', '.join(self.context_used) or 'none'}",
                f"personalization_level={self.personalization_level}",
                f"readiness_level={self.readiness_level}",
                f"problem_axes={', '.join(self.problem_axes) or 'none'}",
                f"nutrient_priorities={', '.join(self.nutrient_priorities) or 'none'}",
                f"food_first_actions={', '.join(self.food_first_actions) or 'none'}",
                f"supplement_considerations={', '.join(self.supplement_considerations) or 'none'}",
                f"behavior_actions={', '.join(self.behavior_actions) or 'none'}",
                f"safety_boundaries={', '.join(self.safety_boundaries) or 'none'}",
                f"source_basis={', '.join(_source_ids(self.source_basis)) or 'none'}",
                f"ctas={', '.join(self.ctas) or 'none'}",
            )
        )


@dataclass(frozen=True)
class AnalysisPlan:
    """Analysis-tab plan generated from the same app context as chatbot answers."""

    score_status: ScoreStatus = "analysis_pending"
    score: int | None = None
    readiness_level: str = "level_0_preparing"
    strengths: tuple[str, ...] = ()
    priority_adjustments: tuple[str, ...] = ()
    nutrient_priorities: tuple[str, ...] = ()
    recommended_foods: tuple[str, ...] = ()
    checklist_actions: tuple[str, ...] = ()
    missing_records: tuple[str, ...] = ()
    safety_boundaries: tuple[str, ...] = ()
    ctas: tuple[str, ...] = ()


class AnswerPlanBuilder:
    """Build app-context-aware answer and analysis plans for one chat turn."""

    def build_answer_plan(
        self,
        request: ChatbotRequest,
        analysis: ChatIntentAnalysis,
        answer_cards: tuple[AnswerCard, ...],
    ) -> AnswerPlan:
        snapshot = _snapshot(request)
        context_used = _non_empty_context_sections(snapshot)
        return AnswerPlan(
            intent=analysis.primary_intent,
            answer_depth=_answer_depth(request.message),
            context_used=context_used,
            personalization_level=_personalization_level(snapshot, answer_cards),
            readiness_level=_readiness_level(snapshot),
            problem_axes=_problem_axes(snapshot, analysis),
            nutrient_priorities=_nutrient_priorities(snapshot),
            food_first_actions=_food_first_actions(answer_cards),
            supplement_considerations=_supplement_considerations(snapshot),
            behavior_actions=_behavior_actions(answer_cards, snapshot),
            safety_boundaries=_safety_boundaries(answer_cards, analysis),
            source_basis=tuple(card.source_metadata() for card in answer_cards),
            ctas=_answer_ctas(snapshot),
            must_not_say=_must_not_say(answer_cards),
        )

    def build_analysis_plan(
        self,
        request: ChatbotRequest,
        answer_plan: AnswerPlan,
    ) -> AnalysisPlan:
        snapshot = _snapshot(request)
        missing_records = _missing_analysis_records(snapshot)
        if missing_records:
            return AnalysisPlan(
                score_status="analysis_pending",
                readiness_level=answer_plan.readiness_level,
                nutrient_priorities=answer_plan.nutrient_priorities,
                recommended_foods=answer_plan.food_first_actions,
                checklist_actions=answer_plan.behavior_actions,
                missing_records=missing_records,
                safety_boundaries=answer_plan.safety_boundaries,
                ctas=("complete_missing_record",),
            )
        return AnalysisPlan(
            score_status="ready_for_analysis",
            score=None,
            readiness_level=answer_plan.readiness_level,
            strengths=_strengths(snapshot),
            priority_adjustments=answer_plan.nutrient_priorities,
            nutrient_priorities=answer_plan.nutrient_priorities,
            recommended_foods=answer_plan.food_first_actions,
            checklist_actions=answer_plan.behavior_actions,
            missing_records=(),
            safety_boundaries=answer_plan.safety_boundaries,
            ctas=("run_or_refresh_analysis", "ask_about_this_result"),
        )


def _snapshot(request: ChatbotRequest) -> dict[str, Any]:
    value = request.context.get("user_health_context_snapshot")
    return dict(value) if isinstance(value, Mapping) else {}


def _non_empty_context_sections(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        key
        for key in (
            "user_profile_summary",
            "today_analysis_snapshot",
            "health_analysis_snapshot",
            "active_supplement_snapshot",
            "recent_food_and_checklist_snapshot",
            "chat_derived_health_signals",
            "visible_analysis_context",
        )
        if snapshot.get(key)
    )


def _answer_depth(message: str) -> AnswerDepth:
    normalized = message.casefold()
    if any(term in normalized for term in EXPANDED_ANSWER_TERMS):
        return "expanded"
    if len(message.strip()) < BRIEF_ANSWER_MESSAGE_MAX_CHARS:
        return "brief"
    return "standard"


def _personalization_level(
    snapshot: Mapping[str, Any],
    answer_cards: tuple[AnswerCard, ...],
) -> PersonalizationLevel:
    if snapshot:
        return "app_context"
    if answer_cards:
        return "reviewed_evidence_only"
    return "general"


def _readiness_level(snapshot: Mapping[str, Any]) -> str:
    health = _mapping(snapshot.get("health_analysis_snapshot"))
    value = health.get("readiness_level")
    return value if isinstance(value, str) and value else "level_0_preparing"


def _problem_axes(
    snapshot: Mapping[str, Any],
    analysis: ChatIntentAnalysis,
) -> tuple[str, ...]:
    profile = _mapping(snapshot.get("user_profile_summary"))
    axes = [
        *_string_list(profile.get("health_axes")),
        *_string_list(profile.get("risk_flags")),
        *analysis.related_conditions,
    ]
    return _unique(axes)


def _nutrient_priorities(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    priorities: list[str] = []
    recent = _mapping(snapshot.get("recent_food_and_checklist_snapshot"))
    for record in _mapping_items(recent.get("recent_food_records")):
        priorities.extend(_string_list(record.get("rough_nutrient_axes")))
    supplements = _mapping(snapshot.get("active_supplement_snapshot"))
    for supplement in _mapping_items(supplements.get("registered_supplements")):
        for ingredient in _mapping_items(supplement.get("ingredients")):
            if ingredient.get("analysis_use") != "standard_nutrient":
                continue
            nutrient_code = ingredient.get("nutrient_code")
            if isinstance(nutrient_code, str) and nutrient_code:
                priorities.append(nutrient_code)
    return _unique(priorities)


def _food_first_actions(answer_cards: tuple[AnswerCard, ...]) -> tuple[str, ...]:
    actions: list[str] = []
    for card in answer_cards:
        actions.extend(card.specific_examples)
    return _unique(actions)


def _supplement_considerations(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    considerations: list[str] = []
    supplements = _mapping(snapshot.get("active_supplement_snapshot"))
    for supplement in _mapping_items(supplements.get("registered_supplements")):
        for ingredient in _mapping_items(supplement.get("ingredients")):
            display_name = ingredient.get("display_name")
            analysis_use = ingredient.get("analysis_use")
            if isinstance(display_name, str) and isinstance(analysis_use, str):
                considerations.append(f"{display_name}: {analysis_use}")
    return _unique(considerations)


def _behavior_actions(
    answer_cards: tuple[AnswerCard, ...],
    snapshot: Mapping[str, Any],
) -> tuple[str, ...]:
    actions: list[str] = []
    for card in answer_cards:
        actions.extend(card.checklist)
    recent = _mapping(snapshot.get("recent_food_and_checklist_snapshot"))
    actions.extend(_string_list(recent.get("checklist_items")))
    return _unique(actions)


def _safety_boundaries(
    answer_cards: tuple[AnswerCard, ...],
    analysis: ChatIntentAnalysis,
) -> tuple[str, ...]:
    boundaries: list[str] = []
    boundaries.extend(analysis.boundary)
    for card in answer_cards:
        boundaries.extend(card.caution_conditions)
    return _unique(boundaries)


def _answer_ctas(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    ctas = ["ask_about_this_result"]
    recent = _mapping(snapshot.get("recent_food_and_checklist_snapshot"))
    if recent.get("checklist_items"):
        ctas.insert(0, "add_checklist_item")
    if _missing_analysis_records(snapshot):
        ctas.insert(0, "complete_missing_record")
    return _unique(ctas)


def _missing_analysis_records(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    recent = _mapping(snapshot.get("recent_food_and_checklist_snapshot"))
    food_records = recent.get("recent_food_records")
    if not isinstance(food_records, list) or not food_records:
        return ("food_records",)
    return ()


def _strengths(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    strengths: list[str] = []
    recent = _mapping(snapshot.get("recent_food_and_checklist_snapshot"))
    if recent.get("recent_food_records"):
        strengths.append("food_records_available")
    supplements = _mapping(snapshot.get("active_supplement_snapshot"))
    if supplements.get("registered_supplements"):
        strengths.append("confirmed_supplements_available")
    return tuple(strengths)


def _must_not_say(answer_cards: tuple[AnswerCard, ...]) -> tuple[str, ...]:
    phrases: list[str] = []
    for card in answer_cards:
        phrases.extend(card.must_not_say)
    return _unique(phrases)


def _source_ids(sources: tuple[dict[str, str], ...]) -> tuple[str, ...]:
    return tuple(source["source_id"] for source in sources if source.get("source_id"))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
