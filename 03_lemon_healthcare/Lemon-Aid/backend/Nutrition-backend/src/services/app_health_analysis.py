"""App-context today and health analysis snapshots for chatbot workflows."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.analysis_result import AnalysisResult
from src.models.schemas.analysis_result import AnalysisType
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject

APP_HEALTH_ANALYSIS_ALGORITHM_VERSION = "app-health-analysis-v1.0.0"
TODAY_SCORE_NAME = "오늘 현재 분석 점수"
TODAY_SCORE_DESCRIPTION = "기록 기반 생활관리 점수"
AnalysisKind = Literal["today_analysis", "health_analysis"]

_ALLOWED_CHAT_SIGNAL_STAGES = {
    "confirmed_from_chat",
    "user_reported_signal",
    "conversation_context_only",
}
_ANALYSIS_RUN_CTAS = ("run_or_refresh_analysis", "ask_about_this_result")
PERSONAL_BASELINE_MIN_DAYS = 14
LONG_TERM_MIN_DAYS = 90
CHECKLIST_CANDIDATE_LIMIT = 3
_INTERNAL_PAYLOAD_TERMS = (
    "candidate",
    "internal",
    "llm_output",
    "model_output",
    "ocr_preview",
    "parser_candidate",
    "provider_payload",
    "raw_",
    "unconfirmed",
    "yolo",
)


def build_today_analysis_snapshot(user_health_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Build a current-records-only today analysis snapshot."""
    recent = _mapping(user_health_snapshot.get("recent_food_and_checklist_snapshot"))
    active_supplements = _mapping(user_health_snapshot.get("active_supplement_snapshot"))
    food_records = _mapping_items(recent.get("recent_food_records"))
    registered_supplements = _mapping_items(active_supplements.get("registered_supplements"))
    checked_today = _mapping_items(active_supplements.get("checked_today"))
    supplement_check_required = bool(registered_supplements)
    missing_records = _today_missing_records(
        has_food_records=bool(food_records),
        supplement_check_required=supplement_check_required,
        has_supplement_check=bool(checked_today),
    )
    stale_reasons = _string_list(recent.get("stale_reasons"))
    priority_adjustments = _food_nutrient_axes(food_records)
    status = "analysis_pending" if missing_records else "ready_for_analysis"

    return {
        "schema_version": "today-analysis-snapshot-v1",
        "status": status,
        "score_name": TODAY_SCORE_NAME,
        "score_description": TODAY_SCORE_DESCRIPTION,
        "score": None if status == "analysis_pending" else _today_score(priority_adjustments),
        "analysis_scope": "current_records_so_far",
        "minimum_conditions": {
            "food_records": bool(food_records),
            "supplement_check_required": supplement_check_required,
            "supplement_check": bool(checked_today),
        },
        "missing_records": list(missing_records),
        "stale": bool(stale_reasons),
        "stale_reasons": stale_reasons,
        "strengths": _today_strengths(food_records, checked_today),
        "priority_adjustments": list(priority_adjustments),
        "recommended_foods": _recommended_foods(priority_adjustments),
        "checklist_actions": _today_checklist_actions(recent, priority_adjustments),
        "ctas": list(_limited_ctas(_today_ctas(missing_records, stale_reasons))),
    }


def build_health_analysis_snapshot(user_health_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Build a maturity-based health analysis snapshot from app context."""
    recent = _mapping(user_health_snapshot.get("recent_food_and_checklist_snapshot"))
    active_supplements = _mapping(user_health_snapshot.get("active_supplement_snapshot"))
    chat_signals = _mapping(user_health_snapshot.get("chat_derived_health_signals"))
    food_records = _mapping_items(recent.get("recent_food_records"))
    supplements = _mapping_items(active_supplements.get("registered_supplements"))
    checklist_items = _string_list(recent.get("checklist_items"))
    signal_stages = _chat_signal_stages(chat_signals)
    coverage = {
        "food": bool(food_records),
        "supplement": bool(supplements),
        "checklist": bool(checklist_items),
        "chat_signals": bool(signal_stages),
    }
    priority_adjustments = _food_nutrient_axes(food_records)
    return {
        "schema_version": "health-analysis-snapshot-v1",
        "readiness_level": _health_readiness_level(coverage, recent),
        "coverage": coverage,
        "strengths": _health_strengths(coverage),
        "priority_adjustments": list(priority_adjustments),
        "nutrient_priorities": list(priority_adjustments),
        "recommended_foods": _recommended_foods(priority_adjustments),
        "checklist_actions": _health_checklist_actions(checklist_items, priority_adjustments),
        "chat_signal_stages": list(signal_stages),
        "ctas": list(_limited_ctas(("run_or_refresh_analysis", "ask_about_this_result"))),
    }


def build_analysis_response_contract(user_health_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Build the Day 05 preview-only analysis/checklist/CTA response contract."""
    today_analysis = build_today_analysis_snapshot(user_health_snapshot)
    smart_analysis = build_health_analysis_snapshot(user_health_snapshot)
    checklist_candidates = _checklist_candidates(today_analysis, smart_analysis)
    ctas = _response_ctas(today_analysis, smart_analysis)
    return {
        "analysis_snapshot": {
            "today_analysis": today_analysis,
            "smart_analysis": smart_analysis,
        },
        "today_analysis": today_analysis,
        "smart_analysis": smart_analysis,
        "checklist_candidates": checklist_candidates,
        "ctas": ctas,
        "approval_preview": _approval_preview(checklist_candidates, ctas),
    }


def detect_analysis_run_intent(message: str) -> AnalysisKind | None:
    """Detect explicit analysis execution intent without executing it."""
    normalized = message.casefold()
    if not any(term in normalized for term in ("run", "analy", "분석", "실행")):
        return None
    if any(term in normalized for term in ("today", "오늘")):
        return "today_analysis"
    if any(term in normalized for term in ("health", "건강")):
        return "health_analysis"
    return None


def build_analysis_run_confirmation(
    analysis_kind: AnalysisKind,
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a non-persisting confirmation payload for chatbot-triggered analysis."""
    return {
        "analysis_kind": analysis_kind,
        "requires_user_confirmation": True,
        "will_persist": False,
        "snapshot_preview": dict(snapshot),
        "ctas": list(_limited_ctas(_ANALYSIS_RUN_CTAS)),
    }


def _checklist_candidates(
    today_analysis: Mapping[str, Any],
    smart_analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    actions: list[tuple[str, str]] = []
    for action in _string_list(today_analysis.get("checklist_actions")):
        actions.append(("today_analysis", action))
    for action in _string_list(smart_analysis.get("checklist_actions")):
        actions.append(("smart_analysis", action))

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source, action in actions:
        label = action.strip()
        if not label or label in seen or _contains_internal_payload_term(label):
            continue
        seen.add(label)
        candidates.append(
            {
                "candidate_id": f"checklist-candidate-v1-{len(candidates) + 1}",
                "kind": "today_practice",
                "title": label,
                "source": source,
                "approval_state": "approval_required",
                "side_effect": "none",
                "deferred_action": "add_today_practice",
            }
        )
        if len(candidates) >= CHECKLIST_CANDIDATE_LIMIT:
            break
    return candidates


def _response_ctas(
    today_analysis: Mapping[str, Any],
    smart_analysis: Mapping[str, Any],
) -> list[str]:
    ctas = [
        *_string_list(today_analysis.get("ctas")),
        *_string_list(smart_analysis.get("ctas")),
    ]
    return list(_limited_ctas(tuple(ctas)))


def _approval_preview(
    checklist_candidates: list[dict[str, Any]],
    ctas: list[str],
) -> dict[str, Any]:
    approval_actions = [
        {
            "action": "add_today_practice",
            "candidate_id": candidate["candidate_id"],
            "status": "approval_required",
            "side_effect": "none",
        }
        for candidate in checklist_candidates
    ]
    approval_actions.extend(
        {
            "action": cta,
            "status": "approval_required",
            "side_effect": "none",
        }
        for cta in ctas
        if cta in {"run_or_refresh_analysis", "complete_missing_record"}
    )
    return {
        "schema_version": "approval-preview-v1",
        "required": bool(approval_actions),
        "approval_state": "approval_required" if approval_actions else "not_required",
        "will_persist": False,
        "will_schedule_notification": False,
        "will_add_today_practice": False,
        "side_effects": [],
        "actions": approval_actions,
    }


def _contains_internal_payload_term(value: str) -> bool:
    normalized = value.casefold()
    return any(term in normalized for term in _INTERNAL_PAYLOAD_TERMS)


async def store_app_health_analysis_result(
    session: AsyncSession,
    user: AuthenticatedUser,
    *,
    analysis_kind: AnalysisKind,
    input_snapshot: dict[str, Any],
    result_snapshot: dict[str, Any],
    user_confirmed: bool,
) -> AnalysisResult:
    """Persist a confirmed app health analysis snapshot in existing analysis_results."""
    if not user_confirmed:
        raise ValueError("App health analysis persistence requires user confirmation.")
    record = AnalysisResult(
        owner_subject=build_owner_subject(user),
        analysis_type=AnalysisType.NUTRITION_ANALYSIS.value,
        algorithm_version=APP_HEALTH_ANALYSIS_ALGORITHM_VERSION,
        kdris_source_manifest_version=None,
        input_snapshot={**input_snapshot, "user_confirmed": True},
        result_snapshot={
            "analysis_kind": analysis_kind,
            "snapshot": dict(result_snapshot),
        },
    )
    # The chat route loads grounding context (medications/meals/supplements)
    # on this same request session before persisting, so an implicit
    # transaction is already open and session.begin() raises
    # InvalidRequestError (caught on the first live E2E smoke). Commit
    # directly instead — same pattern as store_daily_health_score_result.
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


def _today_missing_records(
    *,
    has_food_records: bool,
    supplement_check_required: bool,
    has_supplement_check: bool,
) -> tuple[str, ...]:
    missing: list[str] = []
    if not has_food_records:
        missing.append("food_records")
    if supplement_check_required and not has_supplement_check:
        missing.append("supplement_check")
    return tuple(missing)


def _today_score(priority_adjustments: tuple[str, ...]) -> int:
    penalty = min(len(priority_adjustments), 3) * 4
    return max(60, 80 - penalty)


def _today_strengths(
    food_records: list[dict[str, Any]],
    checked_today: list[dict[str, Any]],
) -> list[str]:
    strengths: list[str] = []
    if food_records:
        strengths.append("food_records_available")
    if checked_today:
        strengths.append("supplement_check_available")
    return strengths[:3]


def _health_strengths(coverage: Mapping[str, bool]) -> list[str]:
    labels = {
        "food": "food_records_available",
        "supplement": "supplements_confirmed",
        "checklist": "checklist_available",
        "chat_signals": "chat_signals_available",
    }
    return [labels[key] for key, covered in coverage.items() if covered][:3]


def _health_readiness_level(coverage: Mapping[str, bool], recent: Mapping[str, Any]) -> str:
    covered_count = sum(1 for covered in coverage.values() if covered)
    if covered_count == 0:
        return "level_0_preparing"
    if covered_count == 1:
        return "level_1_initial"
    tracking_days = _int_value(recent.get("tracking_days"))
    if tracking_days >= LONG_TERM_MIN_DAYS:
        return "level_4_long_term"
    if tracking_days >= PERSONAL_BASELINE_MIN_DAYS:
        return "level_3_personal_baseline"
    return "level_2_recent_pattern"


def _food_nutrient_axes(food_records: list[dict[str, Any]]) -> tuple[str, ...]:
    axes: list[str] = []
    for record in food_records:
        axes.extend(_string_list(record.get("rough_nutrient_axes")))
    return tuple(dict.fromkeys(axes))[:5]


def _recommended_foods(priority_adjustments: tuple[str, ...]) -> list[str]:
    if "sodium_high" in priority_adjustments:
        return ["grilled fish", "tofu", "steamed egg"]
    if "carbohydrate_high" in priority_adjustments:
        return ["vegetable side dish", "plain protein", "unsweetened yogurt"]
    return ["balanced meal with protein", "vegetable side dish"]


def _today_checklist_actions(
    recent: Mapping[str, Any],
    priority_adjustments: tuple[str, ...],
) -> list[str]:
    actions = _string_list(recent.get("checklist_items"))
    if "sodium_high" in priority_adjustments:
        actions.append("check soup and sauce intake")
    return list(dict.fromkeys(actions))[:5]


def _health_checklist_actions(
    checklist_items: list[str],
    priority_adjustments: tuple[str, ...],
) -> list[str]:
    actions = [*checklist_items]
    if priority_adjustments:
        actions.append("review repeated nutrient axes")
    return list(dict.fromkeys(actions))[:5]


def _today_ctas(
    missing_records: tuple[str, ...],
    stale_reasons: list[str],
) -> tuple[str, ...]:
    if missing_records:
        return ("complete_missing_record",)
    if stale_reasons:
        return _ANALYSIS_RUN_CTAS
    return _ANALYSIS_RUN_CTAS


def _limited_ctas(ctas: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(ctas))[:2]


def _chat_signal_stages(chat_signals: Mapping[str, Any]) -> tuple[str, ...]:
    stages: list[str] = []
    for signal in _mapping_items(chat_signals.get("signals")):
        stage = signal.get("stage")
        if isinstance(stage, str) and stage in _ALLOWED_CHAT_SIGNAL_STAGES:
            stages.append(stage)
    return tuple(dict.fromkeys(stages))


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


def _int_value(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0
