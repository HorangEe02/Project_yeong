"""AUDIT-KR self-check scoring tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from src.config import Settings
from src.main import create_app
from src.models.schemas.nutrition import AuditKRRequest
from src.nutrition.audit_kr import score_audit_kr


def test_audit_kr_low_risk_keeps_supplement_flow_available() -> None:
    """위험 음주 cut-off 미만이면 추천 보류 없이 낮은 위험으로 분류한다."""
    result = score_audit_kr(AuditKRRequest(sex="male", item_scores=[0] * 10))

    assert result.score == 0
    assert result.risk_level == "low_risk"
    assert result.supplement_recommendation_paused is False
    assert result.nutrition_priority_nutrients == []


def test_audit_kr_risk_prioritizes_alcohol_support_nutrients() -> None:
    """위험 음주 범위에서는 B1, 엽산, 마그네슘, 아연 확인을 우선 안내한다."""
    result = score_audit_kr(
        AuditKRRequest(sex="female", item_scores=[1, 1, 1, 0, 0, 0, 0, 0, 0, 0])
    )

    assert result.score == 3
    assert result.risk_level == "risky_drinking"
    assert result.supplement_recommendation_paused is False
    assert result.nutrition_priority_nutrients == [
        "thiamin_mg",
        "folate_ug",
        "magnesium_mg",
        "zinc_mg",
    ]
    assert "B1" in result.recommendation_messages[0]


def test_audit_kr_dependence_cutoff_is_sex_specific() -> None:
    """알코올 사용장애 screening cut-off는 남 10점, 여 8점으로 적용한다."""
    female_result = score_audit_kr(
        AuditKRRequest(sex="female", item_scores=[1, 1, 1, 1, 1, 1, 1, 1, 0, 0])
    )
    male_below_cutoff = score_audit_kr(
        AuditKRRequest(sex="male", item_scores=[1, 1, 1, 1, 1, 1, 1, 1, 0, 0])
    )
    male_result = score_audit_kr(AuditKRRequest(sex="male", item_scores=[1] * 10))

    assert female_result.risk_level == "dependence_cutoff"
    assert female_result.supplement_recommendation_paused is True
    assert "1577-0199" in female_result.recommendation_messages[0]
    assert "중독관리통합지원센터" in female_result.recommendation_messages[0]
    assert male_below_cutoff.risk_level == "risky_drinking"
    assert male_result.risk_level == "dependence_cutoff"


def test_audit_kr_request_requires_ten_items() -> None:
    """AUDIT-KR self-check는 10개 항목 점수를 모두 요구한다."""
    with pytest.raises(ValidationError):
        AuditKRRequest(sex="female", item_scores=[1, 1, 1])


def test_audit_kr_api_scores_request() -> None:
    """Nutrition API에서 AUDIT-KR self-check를 점수화한다."""
    app = create_app(settings=Settings(allowed_hosts=["testserver"]))
    client = TestClient(app)

    response = client.post(
        "/api/v1/nutrition/audit-kr",
        json={"sex": "female", "item_scores": [1, 1, 1, 1, 1, 1, 1, 1, 0, 0]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 8
    assert body["risk_level"] == "dependence_cutoff"
    assert body["supplement_recommendation_paused"] is True
