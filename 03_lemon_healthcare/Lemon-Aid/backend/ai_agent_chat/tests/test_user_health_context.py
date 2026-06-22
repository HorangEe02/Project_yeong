"""User health context snapshot contract tests."""

from __future__ import annotations

from lemon_ai_agent.user_health_context import (
    ContextResolver,
    UserHealthContextSnapshot,
    build_user_health_context_snapshot_from_app_records,
)


def test_user_health_context_snapshot_keeps_only_safe_structured_fields() -> None:
    """Snapshots must not carry raw prompts, OCR text, transcripts, or LLM output."""
    snapshot = UserHealthContextSnapshot.from_mapping(
        {
            "user_profile_summary": {
                "health_axes": ["sodium", "blood_pressure"],
                "raw_prompt": "나는 고혈압인데 어제 뭘 먹었는지 전부 말해줘",
            },
            "today_analysis_snapshot": {
                "status": "analysis_pending",
                "raw_llm_output": "hidden chain",
            },
            "health_analysis_snapshot": {"readiness_level": "level_1_initial"},
            "active_supplement_snapshot": {
                "registered_supplements": [
                    {
                        "display_name": "비타민 D",
                        "nutrient_codes": ["vitamin_d"],
                        "raw_ocr_text": "제품 라벨 원문",
                    }
                ]
            },
            "recent_food_and_checklist_snapshot": {
                "recent_food_records": [{"display_items": ["라면"], "meal_type": "lunch"}],
                "raw_chat_transcript": [{"role": "user", "content": "raw"}],
            },
            "chat_derived_health_signals": {
                "signals": [{"name": "late_night_snack", "confidence": "user_reported_signal"}]
            },
            "visible_analysis_context": {
                "last_visible_summary": "오늘 분석은 아직 대기 상태입니다.",
                "messages": [{"role": "assistant", "content": "raw"}],
            },
            "raw_ocr": "top-level raw",
            "raw_prompt": "top-level raw",
        }
    )

    safe_context = snapshot.to_safe_context()

    assert safe_context["user_profile_summary"]["health_axes"] == ["sodium", "blood_pressure"]
    assert safe_context["active_supplement_snapshot"]["registered_supplements"][0][
        "nutrient_codes"
    ] == ["vitamin_d"]
    assert "raw_prompt" not in str(safe_context)
    assert "raw_ocr_text" not in str(safe_context)
    assert "raw_chat_transcript" not in str(safe_context)
    assert "raw_llm_output" not in str(safe_context)
    assert "messages" not in str(safe_context)


def test_user_health_context_snapshot_removes_provider_and_model_payloads() -> None:
    snapshot = UserHealthContextSnapshot.from_mapping(
        {
            "active_supplement_snapshot": {
                "registered_supplements": [
                    {
                        "display_name": "Vitamin D",
                        "provider_payload": {"completion": "hidden"},
                        "raw_provider_payload": {"request": "hidden"},
                        "raw_model_output": "hidden model output",
                        "model_output": "hidden model output",
                    }
                ]
            },
            "recent_food_and_checklist_snapshot": {
                "recent_food_records": [
                    {
                        "display_items": ["rice"],
                        "llm_output": "hidden parser output",
                    }
                ]
            },
        }
    )

    safe_context = snapshot.to_safe_context()
    safe_text = str(safe_context)

    assert "Vitamin D" in safe_text
    assert "rice" in safe_text
    assert "provider_payload" not in safe_text
    assert "raw_provider_payload" not in safe_text
    assert "raw_model_output" not in safe_text
    assert "model_output" not in safe_text
    assert "llm_output" not in safe_text
    assert "hidden" not in safe_text


def test_context_resolver_uses_snapshot_for_general_health_question() -> None:
    snapshot = UserHealthContextSnapshot.from_mapping(
        {
            "user_profile_summary": {
                "health_axes": ["sodium", "blood_pressure"],
                "risk_flags": ["hypertension_context"],
            },
            "recent_food_and_checklist_snapshot": {
                "recent_food_records": [{"display_items": ["라면"], "meal_type": "lunch"}]
            },
        }
    )

    result = ContextResolver().resolve(
        "오늘 저녁은 나트륨을 줄이려면 어떻게 먹는 게 좋아?",
        snapshot,
    )

    assert result.status == "sufficient"
    assert result.required_records == ()
    assert result.safe_context["user_profile_summary"]["health_axes"] == [
        "sodium",
        "blood_pressure",
    ]


def test_context_resolver_requests_targeted_food_lookup_for_specific_meal_query() -> None:
    snapshot = UserHealthContextSnapshot.from_mapping(
        {
            "user_profile_summary": {"health_axes": ["sodium"]},
            "recent_food_and_checklist_snapshot": {"recent_food_records": []},
        }
    )

    result = ContextResolver().resolve("어제 점심에 내가 뭐 먹었지?", snapshot)

    assert result.status == "needs_structured_lookup"
    assert result.required_records == ("food_records",)
    assert result.lookup_filters == {"date_scope": "specific_or_recent", "record_type": "food"}
    assert "recent_food_and_checklist_snapshot" not in result.safe_context


def test_context_resolver_treats_today_meal_plan_as_guidance_not_record_lookup() -> None:
    snapshot = UserHealthContextSnapshot.from_mapping(
        {
            "user_profile_summary": {
                "health_axes": ["blood_glucose"],
                "risk_flags": ["diabetes_context"],
            },
            "recent_food_and_checklist_snapshot": {"recent_food_records": []},
        }
    )

    result = ContextResolver().resolve(
        "당뇨 수치가 요즘 계속 오르네. 오늘 점심, 저녁 식단을 짜줘.",
        snapshot,
    )

    assert result.status == "sufficient"
    assert result.required_records == ()
    assert result.reason == "snapshot_sufficient"


def test_context_resolver_requires_more_info_when_snapshot_is_empty() -> None:
    result = ContextResolver().resolve(
        "내 건강 상태에 맞게 오늘 뭘 하면 좋아?",
        UserHealthContextSnapshot.empty(),
    )

    assert result.status == "needs_more_info"
    assert result.required_records == ()
    assert result.safe_context == {}


def test_app_record_snapshot_builder_maps_team_db_rows_without_raw_payloads() -> None:
    snapshot = build_user_health_context_snapshot_from_app_records(
        profile={
            "age_band": "40s",
            "gender": "female",
            "goals": ["meal_management"],
            "raw_prompt": "must be removed",
        },
        meal_records=[
            {
                "id": "meal-1",
                "meal_type": "lunch",
                "source": "manual",
                "status": "confirmed",
                "nutrition_summary": {"sodium_mg": 2600, "kcal": 550},
                "raw_ocr_text": "must be removed",
            }
        ],
        meal_food_items_by_meal_id={
            "meal-1": [
                {
                    "food_name_text": "ramen",
                    "sodium_mg": 2600,
                    "raw_provider_payload": {"hidden": True},
                }
            ]
        },
        supplements=[
            {
                "display_name": "Vitamin D",
                "status": "active",
                "ingredients": [
                    {
                        "display_name": "vitamin d",
                        "nutrient_code": "vitamin_d",
                        "analysis_use": "standard_nutrient",
                    }
                ],
                "raw_model_output": "must be removed",
            }
        ],
        medical_conditions=[
            {
                "condition_text": "hypertension",
                "clinical_status": "active",
                "source": "user_confirmed",
            }
        ],
        medications=[
            {
                "medication_name_text": "atorvastatin",
                "active_status": "active",
                "dose_text": "10mg",
            }
        ],
        patient_status_snapshots=[
            {
                "data_quality": "partial",
                "risk_flags": ["hypertension_context"],
                "raw_llm_output": "must be removed",
            }
        ],
    )

    safe_context = snapshot.to_safe_context()

    assert safe_context["user_profile_summary"]["condition_names"] == ["hypertension"]
    assert safe_context["user_profile_summary"]["medication_names"] == ["atorvastatin"]
    assert safe_context["user_profile_summary"]["health_axes"] == [
        "blood_pressure",
        "sodium",
    ]
    assert safe_context["user_profile_summary"]["risk_flags"] == ["hypertension_context"]
    assert safe_context["health_analysis_snapshot"]["readiness_level"] == "level_1_initial"
    food_record = safe_context["recent_food_and_checklist_snapshot"]["recent_food_records"][0]
    assert food_record["display_items"] == ["ramen"]
    assert food_record["rough_nutrient_axes"] == ["sodium", "energy"]
    assert safe_context["recent_food_and_checklist_snapshot"]["checklist_items"] == [
        "check_next_meal_sodium"
    ]
    supplement = safe_context["active_supplement_snapshot"]["registered_supplements"][0]
    assert supplement["display_name"] == "Vitamin D"
    assert supplement["ingredients"][0]["nutrient_code"] == "vitamin_d"
    assert "raw_prompt" not in str(safe_context)
    assert "raw_ocr_text" not in str(safe_context)
    assert "raw_provider_payload" not in str(safe_context)
    assert "raw_model_output" not in str(safe_context)
    assert "raw_llm_output" not in str(safe_context)


def test_app_record_snapshot_builder_exposes_profile_keys_consumed_by_agent() -> None:
    snapshot = build_user_health_context_snapshot_from_app_records(
        medical_conditions=[
            {
                "condition_text": "hypertension",
                "clinical_status": "active",
                "source": "user_confirmed",
            }
        ],
        medications=[
            {
                "medication_name_text": "atorvastatin",
                "active_status": "active",
            }
        ],
    )

    profile = snapshot.to_safe_context()["user_profile_summary"]

    assert profile["condition_names"] == ["hypertension"]
    assert profile["medication_names"] == ["atorvastatin"]
    assert profile["chronic_conditions"] == ["hypertension"]
    assert profile["medications"] == ["atorvastatin"]


def test_app_record_snapshot_builder_limits_recent_food_records_newest_first() -> None:
    meal_records = [
        {
            "id": f"meal-{index:02d}",
            "meal_type": "lunch",
            "status": "confirmed",
            "recorded_at": f"2026-06-{index:02d}T12:00:00",
            "display_items": [f"meal {index:02d}"],
        }
        for index in range(1, 13)
    ]

    snapshot = build_user_health_context_snapshot_from_app_records(meal_records=meal_records)

    records = snapshot.to_safe_context()["recent_food_and_checklist_snapshot"][
        "recent_food_records"
    ]

    assert [record["meal_id"] for record in records] == [
        "meal-12",
        "meal-11",
        "meal-10",
        "meal-09",
        "meal-08",
        "meal-07",
        "meal-06",
        "meal-05",
        "meal-04",
        "meal-03",
    ]


def test_app_record_snapshot_builder_uses_newest_patient_status_snapshot() -> None:
    snapshot = build_user_health_context_snapshot_from_app_records(
        patient_status_snapshots=[
            {
                "id": "status-new",
                "recorded_at": "2026-06-12T09:00:00",
                "data_quality": "complete",
                "risk_flags": ["blood_glucose_context"],
            },
            {
                "id": "status-old",
                "recorded_at": "2026-06-01T09:00:00",
                "data_quality": "partial",
                "risk_flags": ["old_context"],
            },
        ],
    )

    health = snapshot.to_safe_context()["health_analysis_snapshot"]

    assert health["data_quality"] == "complete"
    assert health["readiness_level"] == "level_2_ready"
    assert health["risk_flags"] == ["blood_glucose_context"]


def test_app_record_snapshot_builder_ignores_deleted_or_stopped_rows() -> None:
    snapshot = build_user_health_context_snapshot_from_app_records(
        meal_records=[
            {
                "id": "deleted-meal",
                "meal_type": "dinner",
                "status": "deleted",
                "display_items": ["old meal"],
            }
        ],
        supplements=[
            {
                "display_name": "Stopped supplement",
                "active_status": "stopped",
                "ingredients": [{"display_name": "iron"}],
            }
        ],
        medical_conditions=[
            {
                "condition_text": "old condition",
                "status": "archived",
            }
        ],
        medications=[
            {
                "medication_name_text": "stopped medication",
                "active_status": "stopped",
            }
        ],
    )

    safe_context = snapshot.to_safe_context()

    assert safe_context["recent_food_and_checklist_snapshot"]["recent_food_records"] == []
    assert safe_context["active_supplement_snapshot"]["registered_supplements"] == []
    assert "user_profile_summary" not in safe_context


def test_app_record_snapshot_builder_maps_horangee02_db_contract_rows() -> None:
    snapshot = build_user_health_context_snapshot_from_app_records(
        meal_records=[
            {
                "id": "meal-1",
                "meal_type": "dinner",
                "source": "camera",
                "status": "confirmed",
                "nutrition_summary": {"kcal": 610, "carb_g": 78, "sodium_mg": 1850},
            }
        ],
        meal_food_items_by_meal_id={
            "meal-1": [
                {
                    "food_name_text": "kimchi stew",
                    "food_catalog_item_id": "catalog-1",
                    "kcal": 410,
                    "carb_g": 38,
                    "protein_g": 19,
                    "fat_g": 17,
                    "sodium_mg": 1650,
                }
            ]
        },
        food_nutrition_by_catalog_item_id={
            "catalog-1": {
                "class_ko": "김치찌개",
                "serving_g": 300,
                "kcal_100g": 85,
                "carb_g": 4.5,
                "protein_g": 3.2,
                "fat_g": 3.8,
                "sodium_mg": 540,
                "source": "aihub_taxo59_csv",
                "is_active": True,
            }
        },
        food_image_analysis_runs_by_meal_id={
            "meal-1": [
                {
                    "status": "confirmed",
                    "nutrition_estimate_snapshot": {
                        "kcal": 600,
                        "sodium_mg": 1800,
                        "raw_provider_payload": {"hidden": True},
                    },
                    "warning_codes": ["high_sodium_estimate"],
                    "raw_image_bytes": "must be removed",
                }
            ]
        },
        supplements=[
            {
                "id": "supp-1",
                "display_name": "Calcium Plus",
                "matched_product_id": "product-1",
                "serving_snapshot": {"serving_size": "2 tablets"},
                "precaution_snapshot": ["review medications"],
            }
        ],
        user_supplement_ingredients_by_supplement_id={
            "supp-1": [
                {
                    "display_name": "calcium",
                    "nutrient_code": "calcium",
                    "amount": 500,
                    "unit": "mg",
                    "daily_value_percent": 50,
                }
            ]
        },
        supplement_product_ingredients_by_product_id={
            "product-1": [
                {
                    "standard_name": "vitamin d",
                    "nutrient_code": "vitamin_d",
                    "amount": 10,
                    "unit": "mcg",
                    "daily_value_percent": 100,
                }
            ]
        },
        medical_conditions=[{"condition_text": "diabetes", "clinical_status": "active"}],
        medications=[{"medication_name_text": "metformin", "active_status": "active"}],
        patient_status_snapshots=[
            {
                "summary_type": "confirmed_record_summary",
                "metric_summary": {"fasting_glucose_mg_dl": {"latest": 126}},
                "medication_summary": {"active_count": 1},
                "risk_flags": ["blood_glucose_context"],
                "data_quality": "complete",
            }
        ],
    )

    safe_context = snapshot.to_safe_context()

    food_record = safe_context["recent_food_and_checklist_snapshot"]["recent_food_records"][0]
    assert food_record["nutrition_summary"] == {
        "kcal": 610,
        "carb_g": 78,
        "sodium_mg": 1850,
    }
    assert food_record["food_items"][0]["nutrition"] == {
        "kcal": 410,
        "carb_g": 38,
        "protein_g": 19,
        "fat_g": 17,
        "sodium_mg": 1650,
    }
    assert food_record["food_items"][0]["catalog_nutrition"]["class_ko"] == "김치찌개"
    assert food_record["analysis_runs"][0]["nutrition_estimate_snapshot"] == {
        "kcal": 600,
        "sodium_mg": 1800,
    }
    assert food_record["analysis_runs"][0]["warning_codes"] == ["high_sodium_estimate"]
    supplement = safe_context["active_supplement_snapshot"]["registered_supplements"][0]
    assert supplement["ingredients"] == [
        {
            "display_name": "calcium",
            "nutrient_code": "calcium",
            "amount": 500,
            "unit": "mg",
            "daily_value_percent": 50,
            "analysis_use": "user_confirmed",
        },
        {
            "display_name": "vitamin d",
            "nutrient_code": "vitamin_d",
            "amount": 10,
            "unit": "mcg",
            "daily_value_percent": 100,
            "analysis_use": "reference_product",
        },
    ]
    assert safe_context["health_analysis_snapshot"]["metric_summary"] == {
        "fasting_glucose_mg_dl": {"latest": 126}
    }
    assert safe_context["health_analysis_snapshot"]["medication_summary"] == {"active_count": 1}
    assert "raw_provider_payload" not in str(safe_context)
    assert "raw_image_bytes" not in str(safe_context)


def test_app_record_snapshot_builder_excludes_inactive_horangee02_rows() -> None:
    snapshot = build_user_health_context_snapshot_from_app_records(
        meal_records=[
            {"id": "failed-meal", "status": "failed", "meal_type": "dinner"},
            {"id": "deleted-meal", "deleted_at": "2026-06-01", "meal_type": "lunch"},
        ],
        supplements=[
            {
                "id": "supp-1",
                "display_name": "Inactive product",
                "matched_product_id": "inactive-product",
                "deleted_at": "2026-06-01",
            }
        ],
        food_nutrition_by_catalog_item_id={
            "inactive-food": {"class_ko": "비활성 음식", "is_active": False}
        },
        supplement_product_ingredients_by_product_id={
            "inactive-product": [{"standard_name": "ignored"}]
        },
        medical_conditions=[
            {"condition_text": "resolved condition", "clinical_status": "resolved"}
        ],
        medications=[{"medication_name_text": "inactive medication", "active_status": "stopped"}],
    )

    safe_context = snapshot.to_safe_context()

    assert safe_context["recent_food_and_checklist_snapshot"]["recent_food_records"] == []
    assert safe_context["active_supplement_snapshot"]["registered_supplements"] == []
    assert "user_profile_summary" not in safe_context
