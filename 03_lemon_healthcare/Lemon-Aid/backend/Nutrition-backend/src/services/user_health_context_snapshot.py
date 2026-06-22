"""Build privacy-safe user health context snapshots for chatbot calls."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lemon_ai_agent.user_health_context import UserHealthContextSnapshot

_MAX_RECENT_FOOD_RECORDS = 10


def build_user_health_context_snapshot(
    *,
    request_context: Mapping[str, Any],
    memory_context: Mapping[str, Any],
    medication_context: Mapping[str, Any],
    food_record_context: list[Mapping[str, Any]] | None = None,
    active_supplement_context: Mapping[str, Any] | None = None,
) -> UserHealthContextSnapshot:
    """Build a raw-free app context snapshot from server-owned route context."""
    active_supplement_snapshot = _build_active_supplement_snapshot(
        request_context,
        active_supplement_context=active_supplement_context,
    )
    recent_food_and_checklist_snapshot = _build_recent_food_and_checklist_snapshot(
        request_context,
        food_record_context=food_record_context,
    )
    snapshot_payload: dict[str, Any] = {
        "user_profile_summary": _build_user_profile_summary(
            request_context,
            medication_context,
        ),
        "today_analysis_snapshot": _mapping_or_empty(
            request_context.get("today_analysis_snapshot")
        ),
        "health_analysis_snapshot": _build_health_analysis_snapshot(
            request_context,
            memory_context,
        ),
        "active_supplement_snapshot": active_supplement_snapshot,
        "recent_food_and_checklist_snapshot": recent_food_and_checklist_snapshot,
        "chat_derived_health_signals": _mapping_or_empty(
            request_context.get("chat_derived_health_signals")
        ),
        "visible_analysis_context": _build_visible_analysis_context(
            request_context,
            food_record_context=food_record_context,
            active_supplement_snapshot=active_supplement_snapshot,
            recent_food_and_checklist_snapshot=recent_food_and_checklist_snapshot,
        ),
    }
    return UserHealthContextSnapshot.from_mapping(snapshot_payload)


def _build_user_profile_summary(
    request_context: Mapping[str, Any],
    medication_context: Mapping[str, Any],
) -> dict[str, Any]:
    profile = _mapping_or_empty(request_context.get("profile"))
    medication_details = _confirmed_medication_details(medication_context)
    medications = [
        str(detail["display_name"])
        for detail in medication_details
        if isinstance(detail.get("display_name"), str) and detail["display_name"]
    ]
    if not medications and not medication_details:
        medications = _string_list(medication_context.get("medications"))
    summary = {
        "goals": _string_list(profile.get("goals")),
        "chronic_conditions": _string_list(profile.get("chronic_conditions")),
        "health_axes": _string_list(profile.get("health_axes")),
        "risk_flags": _string_list(profile.get("risk_flags")),
        "medications": list(dict.fromkeys(medications)),
    }
    if medication_details:
        summary["medication_details"] = medication_details
    return _drop_empty_values(summary)


def _build_health_analysis_snapshot(
    request_context: Mapping[str, Any],
    memory_context: Mapping[str, Any],
) -> dict[str, Any]:
    snapshot = _mapping_or_empty(request_context.get("health_analysis_snapshot"))
    if not _is_confirmed_context_record(snapshot):
        snapshot = {}
    memory_types = _memory_types(memory_context)
    if memory_types:
        snapshot = {**snapshot, "memory_types": memory_types}
    return snapshot


def _build_active_supplement_snapshot(
    request_context: Mapping[str, Any],
    *,
    active_supplement_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if active_supplement_context:
        return _sanitize_active_supplement_snapshot(active_supplement_context)
    return _sanitize_active_supplement_snapshot(
        _mapping_or_empty(request_context.get("active_supplement_snapshot"))
    )


def _build_recent_food_and_checklist_snapshot(
    request_context: Mapping[str, Any],
    *,
    food_record_context: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    existing = _mapping_or_empty(request_context.get("recent_food_and_checklist_snapshot"))
    latest_entries = _mapping_or_empty(request_context.get("latest_confirmed_entries"))
    recent_food_records = _confirmed_food_records(food_record_context or [])
    if not recent_food_records:
        recent_food_records = _confirmed_food_records(existing.get("recent_food_records"))
    if not recent_food_records:
        recent_food_records = _confirmed_food_records(latest_entries.get("foods"))
    checklist_items = existing.get("checklist_items", request_context.get("checklist_items", []))
    return _drop_empty_values(
        {
            **existing,
            "recent_food_records": recent_food_records,
            "checklist_items": checklist_items,
        }
    )


def _build_visible_analysis_context(
    request_context: Mapping[str, Any],
    *,
    food_record_context: list[Mapping[str, Any]] | None = None,
    active_supplement_snapshot: Mapping[str, Any] | None = None,
    recent_food_and_checklist_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    visible = _mapping_or_empty(request_context.get("visible_analysis_context"))
    if not visible:
        return {}

    stale_reasons: list[str] = []
    current_values: dict[str, list[str]] = {}

    visible_food_record_ids = _string_list(visible.get("food_record_ids"))
    current_food_record_ids = _food_record_ids(food_record_context or [])
    if visible_food_record_ids and current_food_record_ids != visible_food_record_ids:
        stale_reasons.append("food_record_changed_after_visible_analysis")
        current_values["current_food_record_ids"] = current_food_record_ids

    visible_checked_supplement_ids = _string_list(visible.get("checked_supplement_ids"))
    current_checked_supplement_ids = _item_ids(
        _mapping_or_empty(active_supplement_snapshot).get("checked_today"),
        keys=("supplement_id", "user_supplement_id", "id"),
    )
    if (
        visible_checked_supplement_ids
        and current_checked_supplement_ids != visible_checked_supplement_ids
    ):
        stale_reasons.append("supplement_check_changed_after_visible_analysis")
        current_values["current_checked_supplement_ids"] = current_checked_supplement_ids

    visible_checklist_item_ids = _string_list(visible.get("checklist_item_ids"))
    current_checklist_item_ids = _item_ids(
        _mapping_or_empty(recent_food_and_checklist_snapshot).get("checklist_items"),
        keys=("checklist_item_id", "id"),
    )
    if visible_checklist_item_ids and current_checklist_item_ids != visible_checklist_item_ids:
        stale_reasons.append("checklist_changed_after_visible_analysis")
        current_values["current_checklist_item_ids"] = current_checklist_item_ids

    if stale_reasons:
        return {
            **visible,
            "stale": True,
            "stale_reasons": stale_reasons,
            **current_values,
        }
    return {**visible, "stale": False}


def _confirmed_medication_details(medication_context: Mapping[str, Any]) -> list[dict[str, Any]]:
    details = medication_context.get("medication_details")
    if not isinstance(details, list):
        return []
    confirmed: list[dict[str, Any]] = []
    for detail in details:
        if not isinstance(detail, Mapping):
            continue
        if not _is_confirmed_medication(detail):
            continue
        confirmed.append(dict(detail))
    return confirmed


def _is_confirmed_medication(value: Mapping[str, Any]) -> bool:
    if value.get("is_active") is False:
        return False
    status = value.get("confirmation_status")
    return not isinstance(status, str) or status == "user_confirmed"


def _sanitize_active_supplement_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    supplements = [
        _sanitize_confirmed_supplement(supplement)
        for supplement in _mapping_items(value.get("registered_supplements"))
        if _is_confirmed_context_record(supplement)
    ]
    checked_supplement_ids = {
        supplement.get("supplement_id")
        for supplement in supplements
        if isinstance(supplement.get("supplement_id"), str)
    }
    checked_today = [
        checked
        for checked in _mapping_items(value.get("checked_today"))
        if _is_confirmed_context_record(checked)
        and (not checked_supplement_ids or checked.get("supplement_id") in checked_supplement_ids)
    ]
    policy = _mapping_or_empty(value.get("policy"))
    return _drop_empty_values(
        {
            "registered_supplements": supplements,
            "checked_today": checked_today,
            "policy": {
                **policy,
                "nutrient_code_required_for_standard_analysis": True,
                "unconfirmed_preview_excluded": True,
                "label_only_ingredients_do_not_drive_nutrient_analysis": True,
            },
        }
    )


def _sanitize_confirmed_supplement(value: Mapping[str, Any]) -> dict[str, Any]:
    supplement = dict(value)
    ingredients = [
        _sanitize_supplement_ingredient(ingredient)
        for ingredient in _mapping_items(supplement.get("ingredients"))
    ]
    if ingredients:
        supplement["ingredients"] = ingredients
    else:
        supplement.pop("ingredients", None)
    return supplement


def _sanitize_supplement_ingredient(value: Mapping[str, Any]) -> dict[str, Any]:
    ingredient = dict(value)
    ingredient["analysis_use"] = (
        "standard_nutrient" if ingredient.get("nutrient_code") else "label_only"
    )
    return ingredient


def _confirmed_food_records(value: Any) -> list[dict[str, Any]]:
    records = [
        dict(record) for record in _mapping_items(value) if _is_confirmed_context_record(record)
    ]
    return sorted(records, key=_record_recency_key, reverse=True)[:_MAX_RECENT_FOOD_RECORDS]


def _record_recency_key(value: Mapping[str, Any]) -> str:
    return _clean_identifier(
        value.get("recorded_at")
        or value.get("recorded_date")
        or value.get("occurred_at")
        or value.get("created_at")
        or value.get("updated_at")
        or value.get("date")
    )


def _mapping_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _is_confirmed_context_record(value: Mapping[str, Any]) -> bool:
    if value.get("user_confirmed") is False:
        return False
    if value.get("is_active") is False:
        return False
    if value.get("needs_user_review") is True:
        return False

    status_values = (
        value.get("status"),
        value.get("approval_status"),
        value.get("confirmation_status"),
        value.get("stage"),
    )
    excluded_statuses = {
        "candidate",
        "draft",
        "failed",
        "learning",
        "ocr_preview",
        "parser_candidate",
        "preview",
        "requires_confirmation",
        "unconfirmed",
        "yolo_candidate",
    }
    for status in status_values:
        if isinstance(status, str) and status.casefold() in excluded_statuses:
            return False
    return True


def _food_record_ids(records: list[Mapping[str, Any]]) -> list[str]:
    values: list[str] = []
    for record in records:
        record_id = record.get("food_record_id")
        if isinstance(record_id, str) and record_id.strip():
            values.append(record_id.strip())
    return values


def _item_ids(value: Any, *, keys: tuple[str, ...]) -> list[str]:
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            values.append(item.strip())
            continue
        if not isinstance(item, Mapping):
            continue
        for key in keys:
            item_id = item.get(key)
            if isinstance(item_id, str) and item_id.strip():
                values.append(item_id.strip())
                break
    return values


def _memory_types(memory_context: Mapping[str, Any]) -> list[str]:
    summaries = memory_context.get("summaries")
    if not isinstance(summaries, list):
        return []
    values: list[str] = []
    for summary in summaries:
        if not isinstance(summary, Mapping):
            continue
        memory_type = summary.get("memory_type")
        if isinstance(memory_type, str) and memory_type not in values:
            values.append(memory_type)
    return values


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _clean_identifier(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())[:160]


def _drop_empty_values(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: nested for key, nested in value.items() if nested not in (None, [], {})}
