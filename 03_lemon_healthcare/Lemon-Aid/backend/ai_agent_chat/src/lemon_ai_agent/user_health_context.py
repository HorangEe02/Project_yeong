"""Privacy-safe app health context contracts for chatbot planning."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

ContextResolutionStatus = Literal[
    "sufficient",
    "needs_structured_lookup",
    "needs_more_info",
    "unknown_no_reviewed_source",
]

_SNAPSHOT_FIELDS = (
    "user_profile_summary",
    "today_analysis_snapshot",
    "health_analysis_snapshot",
    "active_supplement_snapshot",
    "recent_food_and_checklist_snapshot",
    "chat_derived_health_signals",
    "visible_analysis_context",
)

_FORBIDDEN_CONTEXT_KEYS = {
    "authorization",
    "conversation",
    "image_base64",
    "image_bytes",
    "messages",
    "prompt",
    "llm_output",
    "model_output",
    "provider_payload",
    "raw_chat_transcript",
    "raw_image",
    "raw_image_bytes",
    "raw_llm_output",
    "raw_model_output",
    "raw_ocr",
    "raw_ocr_text",
    "raw_prompt",
    "raw_provider_payload",
}

_MAX_RECENT_FOOD_RECORDS = 10

_FOOD_LOOKUP_TERMS = (
    "먹었",
    "먹은",
    "식사",
    "끼니",
    "아침",
    "점심",
    "저녁",
    "간식",
    "meal",
    "food",
)

_SPECIFIC_TIME_TERMS = (
    "오늘",
    "어제",
    "그제",
    "방금",
    "아까",
    "최근",
    "이번",
    "today",
    "yesterday",
    "recent",
)

_FOOD_RECORD_QUERY_TERMS = (
    "내가",
    "먹었",
    "먹은",
    "뭐 먹",
    "무엇을 먹",
    "기록",
    "조회",
    "확인해",
    "확인해줘",
)

_MEAL_PLANNING_TERMS = (
    "식단",
    "짜줘",
    "추천",
    "어떻게 먹",
    "뭘 먹",
    "뭐 먹으면",
    "먹으면 좋",
    "메뉴",
    "계획",
    "meal plan",
    "recommend",
)


@dataclass(frozen=True)
class UserHealthContextSnapshot:
    """Sanitized app-owned context available before each chatbot answer.

    The snapshot is a structured summary contract, not a dump of app data. Raw
    prompt text, OCR text, full chat transcripts, and raw LLM output are
    intentionally removed at construction time.
    """

    user_profile_summary: dict[str, Any] = field(default_factory=dict)
    today_analysis_snapshot: dict[str, Any] = field(default_factory=dict)
    health_analysis_snapshot: dict[str, Any] = field(default_factory=dict)
    active_supplement_snapshot: dict[str, Any] = field(default_factory=dict)
    recent_food_and_checklist_snapshot: dict[str, Any] = field(default_factory=dict)
    chat_derived_health_signals: dict[str, Any] = field(default_factory=dict)
    visible_analysis_context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> UserHealthContextSnapshot:
        return cls()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> UserHealthContextSnapshot:
        sanitized = _sanitize_context_value(value)
        if not isinstance(sanitized, dict):
            return cls.empty()
        return cls(
            **{field_name: _as_dict(sanitized.get(field_name)) for field_name in _SNAPSHOT_FIELDS}
        )

    def to_safe_context(self) -> dict[str, Any]:
        """Return non-empty, raw-free snapshot sections for planning prompts."""
        return {
            field_name: section
            for field_name in _SNAPSHOT_FIELDS
            if (section := getattr(self, field_name))
        }

    def has_context(self) -> bool:
        return bool(self.to_safe_context())

    def has_recent_food_records(self) -> bool:
        records = self.recent_food_and_checklist_snapshot.get("recent_food_records")
        return isinstance(records, list) and bool(records)


@dataclass(frozen=True)
class ContextResolution:
    status: ContextResolutionStatus
    safe_context: dict[str, Any] = field(default_factory=dict)
    required_records: tuple[str, ...] = ()
    lookup_filters: dict[str, str] = field(default_factory=dict)
    reason: str = ""


class ContextResolver:
    """Decides whether a question can use the snapshot or needs targeted DB reads."""

    def resolve(
        self,
        question: str,
        snapshot: UserHealthContextSnapshot,
    ) -> ContextResolution:
        normalized_question = question.casefold()
        if not snapshot.has_context():
            return ContextResolution(
                status="needs_more_info",
                reason="empty_user_health_context_snapshot",
            )

        if (
            _asks_for_specific_food_record(normalized_question)
            and not snapshot.has_recent_food_records()
        ):
            return ContextResolution(
                status="needs_structured_lookup",
                safe_context=_profile_only_context(snapshot),
                required_records=("food_records",),
                lookup_filters={
                    "date_scope": "specific_or_recent",
                    "record_type": "food",
                },
                reason="specific_food_record_not_in_snapshot",
            )

        return ContextResolution(
            status="sufficient",
            safe_context=snapshot.to_safe_context(),
            reason="snapshot_sufficient",
        )


def build_user_health_context_snapshot_from_app_records(
    *,
    profile: Mapping[str, Any] | None = None,
    meal_records: Iterable[Mapping[str, Any]] = (),
    meal_food_items_by_meal_id: Mapping[str, Iterable[Mapping[str, Any]]] | None = None,
    food_nutrition_by_catalog_item_id: Mapping[str, Mapping[str, Any]] | None = None,
    food_nutrition_by_class_en: Mapping[str, Mapping[str, Any]] | None = None,
    food_image_analysis_runs_by_meal_id: Mapping[str, Iterable[Mapping[str, Any]]] | None = None,
    supplements: Iterable[Mapping[str, Any]] = (),
    user_supplement_ingredients_by_supplement_id: (
        Mapping[str, Iterable[Mapping[str, Any]]] | None
    ) = None,
    supplement_products_by_id: Mapping[str, Mapping[str, Any]] | None = None,
    supplement_product_ingredients_by_product_id: (
        Mapping[str, Iterable[Mapping[str, Any]]] | None
    ) = None,
    medical_conditions: Iterable[Mapping[str, Any]] = (),
    medications: Iterable[Mapping[str, Any]] = (),
    patient_status_snapshots: Iterable[Mapping[str, Any]] = (),
) -> UserHealthContextSnapshot:
    """Fold app/DB-shaped records into the chatbot's raw-free context snapshot.

    This adapter is intentionally table-agnostic: callers pass already-loaded,
    app-owned mappings and the chatbot receives only the stable snapshot fields.
    It does not choose reviewed sources, create medical cautions, or change
    boundary policy.
    """
    medical_condition_rows = tuple(medical_conditions)
    medication_rows = tuple(medications)
    patient_status_rows = tuple(patient_status_snapshots)
    meal_rows = tuple(meal_records)
    supplement_rows = tuple(supplements)

    profile_summary = _profile_summary(
        profile or {},
        medical_conditions=medical_condition_rows,
        medications=medication_rows,
        patient_status_snapshots=patient_status_rows,
    )
    food_snapshot = _recent_food_snapshot(
        meal_rows,
        meal_food_items_by_meal_id=meal_food_items_by_meal_id or {},
        food_nutrition_by_catalog_item_id=food_nutrition_by_catalog_item_id or {},
        food_nutrition_by_class_en=food_nutrition_by_class_en or {},
        food_image_analysis_runs_by_meal_id=food_image_analysis_runs_by_meal_id or {},
    )
    supplement_snapshot = _active_supplement_snapshot(
        supplement_rows,
        user_supplement_ingredients_by_supplement_id=(
            user_supplement_ingredients_by_supplement_id or {}
        ),
        supplement_products_by_id=supplement_products_by_id or {},
        supplement_product_ingredients_by_product_id=(
            supplement_product_ingredients_by_product_id or {}
        ),
    )
    health_snapshot = _health_analysis_snapshot(patient_status_rows)

    return UserHealthContextSnapshot.from_mapping(
        {
            "user_profile_summary": profile_summary,
            "health_analysis_snapshot": health_snapshot,
            "active_supplement_snapshot": supplement_snapshot,
            "recent_food_and_checklist_snapshot": food_snapshot,
        }
    )


def _profile_only_context(snapshot: UserHealthContextSnapshot) -> dict[str, Any]:
    if not snapshot.user_profile_summary:
        return {}
    return {"user_profile_summary": snapshot.user_profile_summary}


def _profile_summary(
    profile: Mapping[str, Any],
    *,
    medical_conditions: Iterable[Mapping[str, Any]],
    medications: Iterable[Mapping[str, Any]],
    patient_status_snapshots: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    condition_names = _active_condition_names(medical_conditions)
    medication_names = _active_medication_names(medications)
    status_risk_flags = _status_risk_flags(patient_status_snapshots)
    health_axes = _unique_strings(
        (
            *_string_list(profile.get("health_axes")),
            *_condition_axes(condition_names),
        )
    )
    risk_flags = _unique_strings((*_string_list(profile.get("risk_flags")), *status_risk_flags))
    summary = _copy_present(
        profile,
        (
            "age_band",
            "gender",
            "goals",
            "readiness_level",
        ),
    )
    if health_axes:
        summary["health_axes"] = health_axes
    if risk_flags:
        summary["risk_flags"] = risk_flags
    if condition_names:
        summary["condition_names"] = condition_names
        summary["chronic_conditions"] = condition_names
    if medication_names:
        summary["medication_names"] = medication_names
        summary["medications"] = medication_names
    return summary


def _recent_food_snapshot(
    meal_records: Iterable[Mapping[str, Any]],
    *,
    meal_food_items_by_meal_id: Mapping[str, Iterable[Mapping[str, Any]]],
    food_nutrition_by_catalog_item_id: Mapping[str, Mapping[str, Any]],
    food_nutrition_by_class_en: Mapping[str, Mapping[str, Any]],
    food_image_analysis_runs_by_meal_id: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    checklist_items: list[str] = []
    for meal in _newest_active_rows(meal_records, limit=_MAX_RECENT_FOOD_RECORDS):
        meal_id = _clean_identifier(meal.get("id") or meal.get("meal_id"))
        food_items = tuple(_iter_active_rows(meal_food_items_by_meal_id.get(meal_id, ())))
        analysis_runs = tuple(
            _iter_active_rows(food_image_analysis_runs_by_meal_id.get(meal_id, ()))
        )
        display_items = _food_display_items(meal, food_items)
        nutrition_summary = _nutrition_summary(_as_dict(meal.get("nutrition_summary")))
        food_item_snapshots = [
            _food_item_snapshot(
                item,
                food_nutrition_by_catalog_item_id=food_nutrition_by_catalog_item_id,
                food_nutrition_by_class_en=food_nutrition_by_class_en,
            )
            for item in food_items
        ]
        food_item_snapshots = [item for item in food_item_snapshots if item]
        analysis_run_snapshots = [_food_analysis_run_snapshot(run) for run in analysis_runs]
        analysis_run_snapshots = [run for run in analysis_run_snapshots if run]
        nutrient_axes = _unique_strings(
            (
                *_nutrient_axes_from_mapping(_as_dict(meal.get("nutrition_summary"))),
                *(axis for item in food_items for axis in _nutrient_axes_from_mapping(item)),
                *(
                    axis
                    for run in analysis_run_snapshots
                    for axis in _nutrient_axes_from_mapping(
                        _as_dict(run.get("nutrition_estimate_snapshot"))
                    )
                ),
            )
        )
        if "sodium" in nutrient_axes:
            checklist_items.append("check_next_meal_sodium")
        record = {
            "meal_id": meal_id,
            "meal_type": _clean_string(meal.get("meal_type")) or "unknown",
            "display_items": display_items,
            "rough_nutrient_axes": nutrient_axes,
        }
        if nutrition_summary:
            record["nutrition_summary"] = nutrition_summary
        if food_item_snapshots:
            record["food_items"] = food_item_snapshots
        if analysis_run_snapshots:
            record["analysis_runs"] = analysis_run_snapshots
        source = _clean_string(meal.get("source"))
        if source:
            record["source"] = source
        status = _clean_string(meal.get("status"))
        if status:
            record["status"] = status
        records.append(record)
    return {
        "recent_food_records": records,
        "checklist_items": _unique_strings(checklist_items),
    }


def _active_supplement_snapshot(
    supplements: Iterable[Mapping[str, Any]],
    *,
    user_supplement_ingredients_by_supplement_id: Mapping[str, Iterable[Mapping[str, Any]]],
    supplement_products_by_id: Mapping[str, Mapping[str, Any]],
    supplement_product_ingredients_by_product_id: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    registered: list[dict[str, Any]] = []
    for supplement in _iter_active_rows(supplements):
        supplement_id = _clean_identifier(supplement.get("id") or supplement.get("supplement_id"))
        product_id = _clean_identifier(
            supplement.get("matched_product_id") or supplement.get("product_id")
        )
        product = _as_dict(supplement_products_by_id.get(product_id))
        product_active = not product or next(_iter_active_rows((product,)), None) is not None
        display_name = _clean_string(
            supplement.get("display_name")
            or supplement.get("product_name")
            or supplement.get("supplement_name_text")
            or product.get("product_name")
        )
        ingredients = [
            *_supplement_ingredients(
                supplement,
                default_analysis_use="standard_nutrient",
            ),
            *_supplement_ingredients(
                {
                    "ingredients": user_supplement_ingredients_by_supplement_id.get(
                        supplement_id,
                        (),
                    )
                },
                default_analysis_use="user_confirmed",
            ),
        ]
        if product_active:
            ingredients.extend(
                _supplement_ingredients(
                    {
                        "ingredients": supplement_product_ingredients_by_product_id.get(
                            product_id,
                            (),
                        )
                    },
                    default_analysis_use="reference_product",
                )
            )
        if not display_name and not ingredients:
            continue
        item: dict[str, Any] = {
            "display_name": display_name or "supplement",
            "ingredients": ingredients,
        }
        for key in ("serving_snapshot", "intake_schedule", "precaution_snapshot"):
            value = supplement.get(key)
            if value not in (None, "", [], {}):
                item[key] = value
        status = _clean_string(supplement.get("status") or supplement.get("active_status"))
        if status:
            item["status"] = status
        registered.append(item)
    return {"registered_supplements": registered}


def _health_analysis_snapshot(
    patient_status_snapshots: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    snapshots = _newest_active_rows(patient_status_snapshots, limit=1)
    if not snapshots:
        return {}
    latest = snapshots[0]
    summary = _copy_present(
        latest,
        (
            "readiness_level",
            "data_quality",
            "summary_type",
            "metric_summary",
            "medication_summary",
            "symptom_categories",
            "risk_flags",
        ),
    )
    if "readiness_level" not in summary:
        data_quality = _clean_string(latest.get("data_quality"))
        if data_quality == "complete":
            summary["readiness_level"] = "level_2_ready"
        elif data_quality:
            summary["readiness_level"] = "level_1_initial"
    return summary


def _asks_for_specific_food_record(normalized_question: str) -> bool:
    if any(term in normalized_question for term in _MEAL_PLANNING_TERMS):
        return False
    return (
        any(term in normalized_question for term in _FOOD_RECORD_QUERY_TERMS)
        and any(term in normalized_question for term in _FOOD_LOOKUP_TERMS)
        and any(term in normalized_question for term in _SPECIFIC_TIME_TERMS)
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _copy_present(
    source: Mapping[str, Any],
    keys: tuple[str, ...],
) -> dict[str, Any]:
    return {
        key: source[key] for key in keys if key in source and source[key] not in (None, "", [], {})
    }


def _iter_active_rows(rows: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("deleted_at") not in (None, ""):
            continue
        if row.get("is_active") is False:
            continue
        status = _clean_string(
            row.get("status") or row.get("active_status") or row.get("clinical_status")
        )
        if status in {
            "archived",
            "deleted",
            "expired",
            "failed",
            "inactive",
            "resolved",
            "stopped",
        }:
            continue
        yield row


def _newest_active_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> tuple[Mapping[str, Any], ...]:
    active_rows = tuple(_iter_active_rows(rows))
    return tuple(sorted(active_rows, key=_row_recency_key, reverse=True)[:limit])


def _row_recency_key(row: Mapping[str, Any]) -> str:
    return _clean_identifier(
        row.get("recorded_at")
        or row.get("recorded_date")
        or row.get("occurred_at")
        or row.get("created_at")
        or row.get("updated_at")
        or row.get("date")
    )


def _food_display_items(
    meal: Mapping[str, Any],
    food_items: tuple[Mapping[str, Any], ...],
) -> list[str]:
    names = [
        _clean_string(
            item.get("food_name_text")
            or item.get("display_name")
            or item.get("name")
            or item.get("class_ko")
        )
        for item in food_items
    ]
    if not any(names):
        names.extend(_string_list(meal.get("display_items")))
    return _unique_strings(name for name in names if name)


def _nutrient_axes_from_mapping(value: Mapping[str, Any]) -> list[str]:
    axes: list[str] = []
    for key in value:
        normalized = key.casefold() if isinstance(key, str) else ""
        if "sodium" in normalized or normalized in {"na_mg", "natrium_mg"}:
            axes.append("sodium")
        elif "protein" in normalized:
            axes.append("protein")
        elif "carb" in normalized or "sugar" in normalized:
            axes.append("carbohydrate")
        elif normalized in {"fat_g", "sat_fat_g", "trans_fat_g"} or "fat" in normalized:
            axes.append("fat")
        elif "kcal" in normalized or "calorie" in normalized:
            axes.append("energy")
    return axes


def _food_item_snapshot(
    item: Mapping[str, Any],
    *,
    food_nutrition_by_catalog_item_id: Mapping[str, Mapping[str, Any]],
    food_nutrition_by_class_en: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    display_name = _clean_string(
        item.get("food_name_text")
        or item.get("display_name")
        or item.get("name")
        or item.get("class_ko")
    )
    snapshot: dict[str, Any] = {}
    if display_name:
        snapshot["display_name"] = display_name
    nutrition = _nutrition_summary(item)
    if nutrition:
        snapshot["nutrition"] = nutrition
    for key in ("portion_amount", "portion_unit", "source"):
        value = item.get(key)
        if value not in (None, "", [], {}):
            snapshot[key] = value
    catalog_nutrition = _catalog_nutrition_for_item(
        item,
        food_nutrition_by_catalog_item_id=food_nutrition_by_catalog_item_id,
        food_nutrition_by_class_en=food_nutrition_by_class_en,
    )
    if catalog_nutrition:
        snapshot["catalog_nutrition"] = catalog_nutrition
    return snapshot


def _catalog_nutrition_for_item(
    item: Mapping[str, Any],
    *,
    food_nutrition_by_catalog_item_id: Mapping[str, Mapping[str, Any]],
    food_nutrition_by_class_en: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    catalog_id = _clean_identifier(item.get("food_catalog_item_id"))
    class_en = _clean_string(item.get("class_en") or item.get("canonical_food_id"))
    row = _as_dict(food_nutrition_by_catalog_item_id.get(catalog_id))
    if not row and class_en:
        row = _as_dict(food_nutrition_by_class_en.get(class_en))
    if not row or next(_iter_active_rows((row,)), None) is None:
        return {}
    return _copy_present(
        row,
        (
            "class_en",
            "class_ko",
            "serving_g",
            "kcal_100g",
            "carb_g",
            "sugar_g",
            "fat_g",
            "protein_g",
            "sodium_mg",
            "chol_mg",
            "sat_fat_g",
            "trans_fat_g",
            "source",
            "source_manifest_version",
        ),
    )


def _food_analysis_run_snapshot(run: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = _copy_present(
        run,
        (
            "status",
            "detector_model",
            "classifier_model",
            "warning_codes",
        ),
    )
    nutrition_estimate = _nutrition_summary(_as_dict(run.get("nutrition_estimate_snapshot")))
    if nutrition_estimate:
        snapshot["nutrition_estimate_snapshot"] = nutrition_estimate
    return snapshot


def _nutrition_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return _copy_present(
        value,
        (
            "kcal",
            "kcal_100g",
            "carb_g",
            "sugar_g",
            "protein_g",
            "fat_g",
            "sodium_mg",
            "chol_mg",
            "sat_fat_g",
            "trans_fat_g",
        ),
    )


def _supplement_ingredients(
    supplement: Mapping[str, Any],
    *,
    default_analysis_use: str,
) -> list[dict[str, Any]]:
    raw_ingredients = supplement.get("ingredients") or supplement.get("ingredient_snapshot") or []
    ingredients: list[dict[str, Any]] = []
    if not isinstance(raw_ingredients, list):
        return ingredients
    for raw in raw_ingredients:
        if not isinstance(raw, Mapping):
            continue
        display_name = _clean_string(
            raw.get("display_name")
            or raw.get("name")
            or raw.get("nutrient_name")
            or raw.get("ingredient_name")
            or raw.get("standard_name")
        )
        nutrient_code = _clean_string(raw.get("nutrient_code") or raw.get("code"))
        analysis_use = _clean_string(raw.get("analysis_use")) or default_analysis_use
        if not display_name and not nutrient_code:
            continue
        ingredient: dict[str, Any] = {"analysis_use": analysis_use}
        if display_name:
            ingredient["display_name"] = display_name
        if nutrient_code:
            ingredient["nutrient_code"] = nutrient_code
        for key in ("amount", "unit", "daily_value_percent"):
            if raw.get(key) not in (None, "", [], {}):
                ingredient[key] = raw[key]
        ingredients.append(ingredient)
    return ingredients


def _active_condition_names(
    medical_conditions: Iterable[Mapping[str, Any]],
) -> list[str]:
    return _unique_strings(
        _clean_string(condition.get("condition_text") or condition.get("display_name"))
        for condition in _iter_active_rows(medical_conditions)
    )


def _active_medication_names(medications: Iterable[Mapping[str, Any]]) -> list[str]:
    return _unique_strings(
        _clean_string(medication.get("medication_name_text") or medication.get("display_name"))
        for medication in _iter_active_rows(medications)
    )


def _status_risk_flags(
    patient_status_snapshots: Iterable[Mapping[str, Any]],
) -> list[str]:
    flags: list[str] = []
    for snapshot in _iter_active_rows(patient_status_snapshots):
        flags.extend(_string_list(snapshot.get("risk_flags")))
    return _unique_strings(flags)


def _condition_axes(condition_names: list[str]) -> list[str]:
    axes: list[str] = []
    for condition in condition_names:
        normalized = condition.casefold()
        if "hypertension" in normalized or "blood pressure" in normalized:
            axes.append("blood_pressure")
            axes.append("sodium")
        if "diabetes" in normalized or "blood glucose" in normalized:
            axes.append("blood_glucose")
            axes.append("carbohydrate")
        if "kidney" in normalized:
            axes.append("kidney")
    return axes


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_string(item) for item in value if _clean_string(item)]


def _unique_strings(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _clean_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:160]


def _clean_identifier(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())[:160]


def _sanitize_context_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, nested_value in value.items():
            if not isinstance(key, str):
                continue
            if key.strip().casefold() in _FORBIDDEN_CONTEXT_KEYS:
                continue
            sanitized[key] = _sanitize_context_value(nested_value)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_context_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_context_value(item) for item in value)
    return value
