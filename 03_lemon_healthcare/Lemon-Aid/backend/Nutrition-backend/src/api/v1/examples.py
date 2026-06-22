"""OpenAPI example payloads for API v1."""

from __future__ import annotations

UNPROCESSABLE_ENTITY_EXAMPLE = {
    "validation_error": {
        "summary": "Validation error",
        "description": "입력 범위 또는 필수 필드가 잘못된 경우입니다.",
        "value": {
            "detail": [
                {
                    "type": "greater_than_equal",
                    "loc": ["body", "daily_steps"],
                    "msg": "Input should be greater than or equal to 0",
                    "input": -1,
                    "ctx": {"ge": 0},
                }
            ]
        },
    }
}

HEALTH_RESPONSE_EXAMPLES = {
    "healthy": {
        "summary": "Service is healthy",
        "value": {"status": "ok", "version": "0.1.0"},
    }
}

ACTIVITY_SCORE_REQUEST_EXAMPLES = {
    "phase1_chronic_disease": {
        "summary": "Phase 1 chronic-disease activity score",
        "description": "웨어러블 심박 시간이 있는 50세 여성 예시입니다.",
        "value": {
            "profile": {
                "age": 50,
                "sex": "female",
                "height_cm": 160,
                "weight_kg": 68,
                "chronic_diseases": ["diabetes", "hypertension"],
            },
            "daily_steps": 7000,
            "target_hr_minutes": 20,
            "group_v2_scores": [60.0, 62.0, 64.0],
            "hrmax_formula": "guide_220_age",
        },
    }
}

ACTIVITY_SCORE_RESPONSE_EXAMPLES = {
    "activity_score": {
        "summary": "Calculated v1-v4 activity score",
        "value": {
            "bmi": {
                "bmi": 26.6,
                "category": "obese_1",
                "evidence_level": "A",
                "note": "BMI 기준 분류이며 체성분이나 질환 상태를 확정하지 않습니다.",
            },
            "recommended_steps": 7500,
            "target_hr_range": {
                "low_bpm": 111,
                "high_bpm": 131,
                "formula": "tanaka_2001",
            },
            "hr_factor": 0.667,
            "percentile_bonus": 0,
            "disease_multiplier": 1.2,
            "v1_score": 77.77,
            "v2_score": 69.99,
            "v3_score": 69.99,
            "v4_score": 83.99,
            "note": "활동점수는 건강 행동 참고 지표이며 질환 개선 효과를 의미하지 않습니다.",
        },
    }
}

WEIGHT_PREDICTION_REQUEST_EXAMPLES = {
    "phase1_weight_prediction": {
        "summary": "7, 30, 90 day weight prediction",
        "description": "단순 에너지 수지 기반 기간별 체중 예측 예시입니다.",
        "value": {
            "age": 50,
            "sex": "female",
            "height_cm": 160,
            "weight_kg": 68,
            "daily_steps": 6500,
            "daily_intake_kcal": 1500,
            "walking_cadence_steps_per_min": None,
            "walking_cadence_minutes": 0,
            "exercise_average_heart_rate_bpm": None,
            "heart_rate_exercise_minutes": 0,
            "periods_days": [7, 30, 90],
        },
    }
}

WEIGHT_PREDICTION_RESPONSE_EXAMPLES = {
    "weight_prediction": {
        "summary": "Predicted body weight by period",
        "value": {
            "predictions": [
                {
                    "days": 7,
                    "estimated_bmr": 1269.0,
                    "estimated_tdee": 1745.0,
                    "daily_balance_kcal": -245.0,
                    "cumulative_balance_kcal": -1715.0,
                    "theoretical_change_kg": -0.223,
                    "corrected_change_kg": -0.405,
                    "predicted_weight_kg": 67.6,
                    "warning": None,
                },
                {
                    "days": 30,
                    "estimated_bmr": 1269.0,
                    "estimated_tdee": 1745.0,
                    "daily_balance_kcal": -245.0,
                    "cumulative_balance_kcal": -7350.0,
                    "theoretical_change_kg": -0.955,
                    "corrected_change_kg": -1.123,
                    "predicted_weight_kg": 66.88,
                    "warning": None,
                },
                {
                    "days": 90,
                    "estimated_bmr": 1269.0,
                    "estimated_tdee": 1745.0,
                    "daily_balance_kcal": -245.0,
                    "cumulative_balance_kcal": -22050.0,
                    "theoretical_change_kg": -2.864,
                    "corrected_change_kg": -3.369,
                    "predicted_weight_kg": 64.63,
                    "warning": "90일 이상 기대 체중 범위는 대사 적응을 반영하는 동적 모델 검토가 필요합니다.",
                },
            ],
            "evidence_level": "B",
            "note": "체중 예측은 단순 에너지 수지 기반 참고값이며 장기 대사 적응을 완전히 반영하지 않습니다.",
        },
    }
}

KDRIS_LOOKUP_RESPONSE_EXAMPLES = {
    "kdris_lookup_sample": {
        "summary": "KDRIs sample references",
        "value": {
            "query": {"age": 30, "sex": "male", "pregnancy_status": "none"},
            "references": [
                {
                    "nutrient_code": "energy_kcal",
                    "nutrient_name": "Energy",
                    "sex": "all",
                    "age_min": 19,
                    "age_max": 64,
                    "pregnancy_status": "none",
                    "reference_type": "EER",
                    "reference_amount": 2000.0,
                    "reference_unit": "kcal",
                    "ul_amount": None,
                    "ul_unit": None,
                    "source_note": "sample_fixture_not_verified_kdris",
                    "source_id": "local_kdris_2020_sample_fixture",
                    "review_status": "not_applicable_sample_fixture",
                    "dataset_version": "2020-sample",
                    "source_manifest_version": "2.0",
                },
                {
                    "nutrient_code": "protein_g",
                    "nutrient_name": "Protein",
                    "sex": "all",
                    "age_min": 19,
                    "age_max": 64,
                    "pregnancy_status": "none",
                    "reference_type": "RDA",
                    "reference_amount": 60.0,
                    "reference_unit": "g",
                    "ul_amount": None,
                    "ul_unit": None,
                    "source_note": "sample_fixture_not_verified_kdris",
                    "source_id": "local_kdris_2020_sample_fixture",
                    "review_status": "not_applicable_sample_fixture",
                    "dataset_version": "2020-sample",
                    "source_manifest_version": "2.0",
                },
            ],
            "dataset_status": "implementation_sample_not_official_reference_table",
            "dataset_version": "2020-sample",
            "source_manifest_version": "2.0",
            "note": "현재 KDRIs 데이터는 Phase 1 샘플 fixture이며 공식 수치 검수 전입니다.",
        },
    }
}

NUTRITION_ANALYSIS_REQUEST_EXAMPLES = {
    "vitamin_status_sample": {
        "summary": "Vitamin C and Vitamin A intake check",
        "description": "샘플 KDRIs fixture 기준으로 섭취 상태를 비교하는 예시입니다.",
        "value": {
            "profile": {
                "age": 30,
                "sex": "male",
                "height_cm": 170,
                "weight_kg": 70,
            },
            "intakes": [
                {"nutrient_code": "vitamin_c_mg", "amount": 30, "unit": "mg"},
                {"nutrient_code": "vitamin_a_ug", "amount": 5000, "unit": "ug"},
            ],
        },
    }
}

NUTRITION_ANALYSIS_RESPONSE_EXAMPLES = {
    "nutrition_analysis": {
        "summary": "Nutrient intake status result",
        "value": {
            "results": [
                {
                    "nutrient_code": "vitamin_c_mg",
                    "nutrient_name": "Vitamin C",
                    "reference_amount": 100.0,
                    "reference_type": "RDA",
                    "source_id": "local_kdris_2020_sample_fixture",
                    "errata_version": None,
                    "review_status": "not_applicable_sample_fixture",
                    "reference_unit": "mg",
                    "actual_amount": 30.0,
                    "ratio": 0.3,
                    "ul_amount": 2000.0,
                    "status": "at_risk_inadequate",
                    "priority": 1,
                    "user_message": "부족 가능성이 높아 섭취량 확인이 필요합니다.",
                },
                {
                    "nutrient_code": "vitamin_a_ug",
                    "nutrient_name": "Vitamin A",
                    "reference_amount": 700.0,
                    "reference_type": "RDA",
                    "source_id": "local_kdris_2020_sample_fixture",
                    "errata_version": None,
                    "review_status": "not_applicable_sample_fixture",
                    "reference_unit": "ug",
                    "actual_amount": 5000.0,
                    "ratio": 7.14,
                    "ul_amount": 3000.0,
                    "status": "risky",
                    "priority": 0,
                    "user_message": "상한 섭취량을 초과할 수 있어 전문가 상담 권장 대상입니다.",
                },
            ],
            "dataset_status": "implementation_sample_not_official_reference_table",
            "dataset_version": "2020-sample",
            "source_manifest_version": "2.0",
            "note": "결과는 섭취 상태 참고용이며 개인 건강 상태를 확정하지 않습니다.",
        },
    }
}

NUTRITION_DIAGNOSIS_LATEST_RESPONSE_EXAMPLES = {
    "ready": {
        "summary": "Latest persisted nutrition diagnosis",
        "value": {
            "data_status": "ready",
            "result_id": "33333333-3333-4333-8333-333333333333",
            "created_at": "2026-05-12T12:20:00Z",
            "algorithm_version": "nutrition-v1.0.0",
            "summary": {
                "total_count": 2,
                "deficient_count": 1,
                "low_count": 0,
                "adequate_count": 0,
                "excessive_count": 0,
                "risky_count": 1,
                "deficient_or_low_count": 1,
                "excessive_or_risky_count": 1,
                "dataset_status": "implementation_sample_not_official_reference_table",
                "dataset_version": "2020-sample",
                "source_manifest_version": "2.0",
                "summary_message": (
                    "섭취량 확인이 필요한 낮은 섭취 영양소 1종, "
                    "과다 가능성 확인 영양소 1종이 있습니다."
                ),
            },
            "diagnoses": [
                {
                    "nutrient_code": "vitamin_c_mg",
                    "nutrient_name": "Vitamin C",
                    "reference_amount": 100.0,
                    "reference_type": "RDA",
                    "source_id": "local_kdris_2020_sample_fixture",
                    "errata_version": None,
                    "review_status": "not_applicable_sample_fixture",
                    "reference_unit": "mg",
                    "actual_amount": 30.0,
                    "ratio": 0.3,
                    "ul_amount": 2000.0,
                    "status": "deficient",
                    "priority": 1,
                    "user_message": "부족 가능성이 높아 섭취량 확인이 필요합니다.",
                },
                {
                    "nutrient_code": "vitamin_a_ug",
                    "nutrient_name": "Vitamin A",
                    "reference_amount": 700.0,
                    "reference_type": "RDA",
                    "source_id": "local_kdris_2020_sample_fixture",
                    "errata_version": None,
                    "review_status": "not_applicable_sample_fixture",
                    "reference_unit": "ug",
                    "actual_amount": 5000.0,
                    "ratio": 7.14,
                    "ul_amount": 3000.0,
                    "status": "risky",
                    "priority": 0,
                    "user_message": "상한 섭취량을 초과할 수 있어 전문가 상담 권장 대상입니다.",
                },
            ],
            "recommended_foods": {},
            "disclaimers": ["결과는 건강관리 참고 정보이며 개인 건강 상태를 확정하지 않습니다."],
        },
    },
    "not_ready": {
        "summary": "No persisted nutrition diagnosis yet",
        "value": {
            "data_status": "not_ready",
            "result_id": None,
            "created_at": None,
            "algorithm_version": None,
            "summary": {
                "total_count": 0,
                "deficient_count": 0,
                "low_count": 0,
                "adequate_count": 0,
                "excessive_count": 0,
                "risky_count": 0,
                "deficient_or_low_count": 0,
                "excessive_or_risky_count": 0,
                "dataset_status": None,
                "dataset_version": None,
                "source_manifest_version": None,
                "summary_message": (
                    "저장된 영양 분석 결과가 없어 대시보드에 표시할 "
                    "부족 영양소 정보가 아직 없습니다."
                ),
            },
            "diagnoses": [],
            "recommended_foods": {},
            "disclaimers": ["결과는 건강관리 참고 정보이며 개인 건강 상태를 확정하지 않습니다."],
        },
    },
}

P1_CONTRACT_STUB_EXAMPLE = {
    "p1_contract_stub": {
        "summary": "P1 contract frozen, implementation pending",
        "value": {
            "detail": {
                "code": "p1_contract_stub",
                "message": "This P1 API contract is frozen; implementation starts after P1-0.",
            }
        },
    }
}

UNAUTHORIZED_EXAMPLE = {
    "missing_bearer_token": {
        "summary": "Missing bearer token",
        "value": {"detail": "Not authenticated."},
    }
}

INSUFFICIENT_SCOPE_EXAMPLE = {
    "insufficient_scope": {
        "summary": "Required OAuth scope is missing",
        "value": {"detail": "Not enough permissions."},
    }
}

CONSENT_REQUIRED_EXAMPLE = {
    "consent_required": {
        "summary": "Required consent is missing",
        "value": {
            "detail": {
                "code": "consent_required",
                "message": "Required user consent has not been granted.",
                "required_consents": ["ocr_image_processing"],
            }
        },
    }
}

UNSUPPORTED_MEDIA_TYPE_EXAMPLE = {
    "unsupported_media_type": {
        "summary": "Unsupported image type",
        "value": {
            "detail": {
                "code": "unsupported_media_type",
                "message": "Only JPEG, PNG, and WebP label images are accepted.",
            }
        },
    }
}

PAYLOAD_TOO_LARGE_EXAMPLE = {
    "payload_too_large": {
        "summary": "Uploaded image is too large",
        "value": {
            "detail": {
                "code": "payload_too_large",
                "message": "Uploaded label image exceeds the configured size limit.",
            }
        },
    }
}

TOO_MANY_REQUESTS_EXAMPLE = {
    "too_many_requests": {
        "summary": "Rate limit exceeded",
        "value": {
            "detail": {
                "code": "too_many_requests",
                "message": "Too many requests. Please retry later.",
            }
        },
    }
}

SUPPLEMENT_ANALYSIS_RESPONSE_EXAMPLES = {
    "requires_confirmation": {
        "summary": "Supplement label image intake preview requires user confirmation",
        "value": {
            "analysis_id": "11111111-1111-4111-8111-111111111111",
            "status": "requires_confirmation",
            "parsed_product": {
                "product_name": None,
                "manufacturer": None,
                "serving_size": None,
                "daily_servings": None,
            },
            "ingredient_candidates": [],
            "matched_product_candidates": [],
            "low_confidence_fields": ["label_text"],
            "warnings": [
                "Image intake is complete. OCR and LLM extraction are pending and require user review."
            ],
            "algorithm_version": "supplement-intake-v1.0.0",
            "source_manifest_version": None,
            "expires_at": "2026-05-12T12:00:00Z",
        },
    }
}

SUPPLEMENT_CREATE_REQUEST_EXAMPLES = {
    "confirmed_supplement": {
        "summary": "User-confirmed supplement record",
        "value": {
            "analysis_id": "11111111-1111-4111-8111-111111111111",
            "display_name": "Vitamin D 1000 IU",
            "manufacturer": "Sample Nutrition",
            "ingredients": [
                {
                    "display_name": "Vitamin D",
                    "nutrient_code": "vitamin_d_ug",
                    "amount": 25,
                    "unit": "ug",
                    "confidence": 1,
                    "source": "user_confirmed",
                }
            ],
            "serving": {"amount": 1, "unit": "capsule", "daily_servings": 1},
            "intake_schedule": {"frequency": "daily", "time_of_day": ["morning"]},
            "user_confirmed": True,
        },
    }
}

USER_SUPPLEMENT_RESPONSE_EXAMPLES = {
    "registered_supplement": {
        "summary": "Stored user supplement",
        "value": {
            "id": "22222222-2222-4222-8222-222222222222",
            "display_name": "Vitamin D 1000 IU",
            "manufacturer": "Sample Nutrition",
            "ingredients": [
                {
                    "display_name": "Vitamin D",
                    "nutrient_code": "vitamin_d_ug",
                    "amount": 25,
                    "unit": "ug",
                    "confidence": 1,
                    "source": "user_confirmed",
                }
            ],
            "serving": {"amount": 1, "unit": "capsule", "daily_servings": 1},
            "intake_schedule": {"frequency": "daily", "time_of_day": ["morning"]},
            "user_confirmed_at": "2026-05-12T12:05:00Z",
            "created_at": "2026-05-12T12:05:00Z",
        },
    }
}

USER_SUPPLEMENT_LIST_RESPONSE_EXAMPLES = {
    "registered_supplements": {
        "summary": "Current-user supplement list",
        "value": {
            "results": [USER_SUPPLEMENT_RESPONSE_EXAMPLES["registered_supplement"]["value"]],
            "limit": 20,
            "offset": 0,
        },
    }
}

SUPPLEMENT_IMPACT_PREVIEW_RESPONSE_EXAMPLES = {
    "ready": {
        "summary": "Deterministic supplement impact preview",
        "value": {
            "calculation_version": "supplement-impact-v1.0.0",
            "reference_version": "2025",
            "source_manifest_version": "2.0",
            "data_status": "ready",
            "current_supplement_contributions": [
                {
                    "nutrient_code": "vitamin_d_ug",
                    "nutrient_name": "Vitamin D",
                    "reference_unit": "ug",
                    "total_daily_amount": 25.0,
                    "original_unit_totals": {"ug": 25.0},
                    "contribution_count": 1,
                    "supplement_ids": ["22222222-2222-4222-8222-222222222222"],
                    "items": [
                        {
                            "supplement_id": "22222222-2222-4222-8222-222222222222",
                            "supplement_name": "Vitamin D 1000 IU",
                            "ingredient_id": "44444444-4444-4444-8444-444444444444",
                            "display_name": "Vitamin D",
                            "nutrient_code": "vitamin_d_ug",
                            "amount_per_serving": 25.0,
                            "unit": "ug",
                            "daily_servings": 1.0,
                            "daily_amount": 25.0,
                            "source": "user_confirmed",
                            "confidence": 1.0,
                        }
                    ],
                    "warnings": [],
                }
            ],
            "deficiency_support_candidates": [],
            "excess_or_duplicate_risks": [],
            "missing_profile_fields": [],
            "safe_user_message": (
                "현재 입력 기준으로 우선 확인할 보충제 중복 또는 상한 위험이 없습니다."
            ),
            "clinical_disclaimer": (
                "이 결과는 라벨과 사용자가 확인한 입력 기록 기준의 건강관리 참고 정보이며, "
                "개인 건강 상태를 확정하지 않습니다."
            ),
            "warnings": [],
            "requires_user_confirmation": False,
        },
    }
}

SUPPLEMENT_RECOMMENDATION_EXPLAIN_REQUEST_EXAMPLES = {
    "deterministic_preview": {
        "summary": "Explain deterministic supplement impact preview",
        "value": {
            "preview": SUPPLEMENT_IMPACT_PREVIEW_RESPONSE_EXAMPLES["ready"]["value"],
            "locale": "ko-KR",
            "use_local_llm": False,
        },
    }
}

SUPPLEMENT_RECOMMENDATION_EXPLAIN_RESPONSE_EXAMPLES = {
    "safe_explanation": {
        "summary": "Safe explanation",
        "value": {
            "safe_user_message": (
                "현재 입력 기준으로 우선 확인할 보충제 중복 또는 상한 위험이 없습니다."
            ),
            "explanation_bullets": ["계산된 보충제 영양소는 1종입니다."],
            "clinical_disclaimer": (
                "이 결과는 라벨과 사용자가 확인한 입력 기록 기준의 건강관리 참고 정보이며, "
                "개인 건강 상태를 확정하지 않습니다."
            ),
            "blocked_terms_detected": [],
            "llm_used": False,
            "warnings": [],
        },
    }
}

HEALTH_SYNC_REQUEST_EXAMPLES = {
    "ios_healthkit_daily_aggregate": {
        "summary": "Daily HealthKit aggregate",
        "value": {
            "client_batch_id": "ios-2026-05-12T12-10-00Z",
            "records": [
                {
                    "measured_date": "2026-05-12",
                    "source_platform": "ios_healthkit",
                    "steps": 7200,
                    "weight_kg": 68.4,
                    "resting_heart_rate_bpm": 68,
                    "active_energy_kcal": 430,
                }
            ],
        },
    },
    "android_health_connect_daily_aggregate": {
        "summary": "Daily Health Connect aggregate",
        "value": {
            "client_batch_id": "android-2026-05-12T12-10-00Z",
            "records": [
                {
                    "measured_date": "2026-05-12",
                    "source_platform": "android_health_connect",
                    "steps": 6800,
                    "resting_heart_rate_bpm": 70,
                    "active_energy_kcal": 390,
                    "source_record_hash": "b" * 64,
                }
            ],
        },
    },
}

HEALTH_SYNC_RESPONSE_EXAMPLES = {
    "accepted_health_aggregate": {
        "summary": "Accepted health aggregate sync",
        "value": {
            "batch_id": "44444444-4444-4444-8444-444444444444",
            "accepted_count": 1,
            "rejected_count": 0,
            "synced_at": "2026-05-12T12:10:00Z",
        },
    }
}

HEALTH_SYNC_CONFLICT_EXAMPLE = {
    "idempotency_conflict": {
        "summary": "Client batch id reused for different records",
        "value": {
            "detail": {
                "code": "idempotency_conflict",
                "message": "client_batch_id was already used for different records.",
            }
        },
    }
}

DASHBOARD_SUMMARY_RESPONSE_EXAMPLES = {
    "dashboard_summary": {
        "summary": "Current-user dashboard summary",
        "value": {
            "as_of": "2026-05-12T12:15:00Z",
            "nutrition": {
                "data_status": "ready",
                "latest_result_id": "33333333-3333-4333-8333-333333333333",
                "low_count": 1,
                "high_count": 0,
                "dataset_version": "2020-sample",
                "source_manifest_version": "2.0",
            },
            "activity": {
                "data_status": "ready",
                "latest_steps": 7200,
                "latest_resting_heart_rate_bpm": 68,
                "latest_active_energy_kcal": 430.25,
                "latest_activity_score": 84.2,
                "measured_date": "2026-05-12",
            },
            "weight": {
                "data_status": "ready",
                "latest_weight_kg": 68.4,
                "predicted_weight_kg": 68.1,
                "measured_date": "2026-05-12",
            },
            "supplements": {"registered_count": 2, "requires_review_count": 0},
            "health_score": {
                "data_status": "ready",
                "score": 78,
                "label": "good",
                "label_text": "양호",
                "message": "전반적으로 좋아요. 한두 가지만 더 신경 써보세요.",
                "components": {
                    "activity": {"available": True, "subscore": 82.0, "weight": 0.6},
                    "nutrition": {"available": True, "subscore": 72.0, "weight": 0.4},
                },
                "source_citations": [],
                "algorithm_version": "daily-health-score-v1.0.0",
                "measured_date": "2026-05-12",
            },
            "disclaimers": ["결과는 건강관리 참고 정보이며 개인 상태를 확정하지 않습니다."],
            "algorithm_version": "dashboard-contract-v1.0.0",
        },
    }
}


AI_AGENT_DAILY_COACHING_REQUEST_EXAMPLES = {
    "daily_coaching_confirmed_mock": {
        "summary": "Confirmed mock intake for daily coaching",
        "value": {
            "request_id": "daily-coaching-2026-05-18",
            "user_id": "client-side-placeholder",
            "context": {
                "profile": {
                    "age": 52,
                    "gender": "male",
                    "goals": ["meal_management"],
                    "chronic_conditions": ["hypertension"],
                    "medications": ["blood_pressure_medication"],
                }
            },
            "payload": {
                "date": "2026-05-18",
                "sources": [
                    {
                        "source_type": "food_ocr",
                        "image_id": "meal-image-1",
                        "raw_ocr_text": "instant noodles sodium 2600mg",
                        "user_confirmed": True,
                    }
                ],
                "foods": [
                    {
                        "name": "instant noodles",
                        "meal_type": "lunch",
                        "serving_label": "1 bowl",
                        "nutrients": [
                            {"name": "sodium", "amount": 2600, "unit": "mg"},
                            {"name": "protein", "amount": 25, "unit": "g"},
                        ],
                    }
                ],
                "supplements": [],
                "health_trends": [],
            },
        },
    },
    "daily_coaching_preview_mock": {
        "summary": "Unconfirmed OCR source returns preview state",
        "value": {
            "request_id": "daily-coaching-preview-2026-05-18",
            "user_id": "client-side-placeholder",
            "context": {"profile": {"age": 45, "gender": "other"}},
            "payload": {
                "date": "2026-05-18",
                "sources": [
                    {
                        "source_type": "food_ocr",
                        "image_id": "meal-image-2",
                        "raw_ocr_text": "label text pending user review",
                        "user_confirmed": False,
                    }
                ],
                "foods": [],
                "supplements": [],
                "health_trends": [],
            },
        },
    },
}

AI_AGENT_DAILY_COACHING_RESPONSE_EXAMPLES = {
    "completed_daily_coaching": {
        "summary": "Completed deterministic coaching response",
        "value": {
            "request_id": "daily-coaching-2026-05-18",
            "user_id": "local-dev-user",
            "agent_name": "daily_health_agent",
            "status": "completed",
            "approval_status": "confirmed",
            "requires_user_approval": True,
            "message": (
                "For your question, the answer is based on the current input, "
                "recent flow, and policy checks already computed for 2026-05-18."
            ),
            "findings": [
                {
                    "nutrient": "sodium",
                    "total_amount": 2600,
                    "unit": "mg",
                    "ratio_to_target": 1.3,
                    "level": "risky",
                    "message": "Sodium is above the upper limit.",
                }
            ],
            "recommendations": [],
            "actions": [],
            "safety_warnings": [],
            "used_tools": [
                "daily_health_agent",
                "nutrition_engine",
                "supplement_engine",
                "safety_guard",
                "chat_agent",
            ],
            "latency_ms": 1.0,
            "cost_usd": 0,
            "provider": "deterministic",
            "debug_trace": [],
        },
    },
    "preview_daily_coaching": {
        "summary": "Preview response for unconfirmed OCR source",
        "value": {
            "request_id": "daily-coaching-preview-2026-05-18",
            "user_id": "local-dev-user",
            "agent_name": "daily_health_agent",
            "status": "preview",
            "approval_status": "requires_confirmation",
            "requires_user_approval": True,
            "message": "For your question, the answer is based on the current input.",
            "findings": [],
            "recommendations": [],
            "actions": [],
            "safety_warnings": [],
            "used_tools": [
                "daily_health_agent",
                "nutrition_engine",
                "supplement_engine",
                "safety_guard",
                "chat_agent",
            ],
            "latency_ms": 1.0,
            "cost_usd": 0,
            "provider": "deterministic",
            "debug_trace": [],
        },
    },
}
