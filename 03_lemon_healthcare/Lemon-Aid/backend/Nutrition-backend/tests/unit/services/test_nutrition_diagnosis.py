"""Nutrition diagnosis service tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from src.models.db.analysis_result import AnalysisResult
from src.models.schemas.analysis_result import AnalysisType
from src.services.nutrition_diagnosis import build_nutrition_diagnosis_response


def _nutrition_record(user_messages: list[str] | None = None) -> AnalysisResult:
    """Return a nutrition analysis result fixture.

    Args:
        user_messages: Optional user messages for the two result rows.

    Returns:
        Analysis result ORM object.
    """
    messages = user_messages or [
        "부족 가능성이 높아 섭취량 확인이 필요합니다.",
        "상한 섭취량을 초과할 수 있어 전문가 상담 권장 대상입니다.",
    ]
    now = datetime.now(UTC)
    return AnalysisResult(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        analysis_type=AnalysisType.NUTRITION_ANALYSIS.value,
        algorithm_version="nutrition-v1.0.0",
        kdris_source_manifest_version="2.0",
        input_snapshot={"profile": {"age": 30}},
        result_snapshot={
            "results": [
                {
                    "nutrient_code": "vitamin_c_mg",
                    "nutrient_name": "Vitamin C",
                    "reference_amount": 100.0,
                    "reference_type": "RDA",
                    "reference_unit": "mg",
                    "actual_amount": 30.0,
                    "ratio": 0.3,
                    "ul_amount": 2000.0,
                    "status": "deficient",
                    "priority": 1,
                    "user_message": messages[0],
                },
                {
                    "nutrient_code": "vitamin_a_ug",
                    "nutrient_name": "Vitamin A",
                    "reference_amount": 700.0,
                    "reference_type": "RDA",
                    "reference_unit": "ug",
                    "actual_amount": 5000.0,
                    "ratio": 7.14,
                    "ul_amount": 3000.0,
                    "status": "risky",
                    "priority": 0,
                    "user_message": messages[1],
                },
            ],
            "dataset_status": "implementation_sample_not_official_reference_table",
            "dataset_version": "2020-sample",
            "source_manifest_version": "2.0",
        },
        created_at=now,
        updated_at=now,
    )


def test_build_nutrition_diagnosis_response_counts_statuses_and_omits_snapshots() -> None:
    """Verify persisted nutrition results are converted into a safe diagnosis response."""
    response = build_nutrition_diagnosis_response(_nutrition_record())
    body = response.model_dump()

    assert response.data_status == "ready"
    assert response.summary.deficient_count == 1
    assert response.summary.risky_count == 1
    assert response.summary.deficient_or_low_count == 1
    assert response.summary.excessive_or_risky_count == 1
    assert response.summary.dataset_version == "2020-sample"
    assert "owner_subject" not in body
    assert "input_snapshot" not in body
    assert "result_snapshot" not in body


def test_build_nutrition_diagnosis_response_returns_not_ready_without_record() -> None:
    """Verify no stored nutrition result is represented as an empty safe response."""
    response = build_nutrition_diagnosis_response(None)

    assert response.data_status == "not_ready"
    assert response.result_id is None
    assert response.summary.total_count == 0
    assert response.diagnoses == []


def test_build_nutrition_diagnosis_response_rejects_forbidden_user_wording() -> None:
    """Verify unsafe persisted user wording does not reach API responses."""
    record = _nutrition_record(user_messages=["진단 문구", "안전 문구"])

    with pytest.raises(ValueError, match="unsafe user wording"):
        build_nutrition_diagnosis_response(record)
