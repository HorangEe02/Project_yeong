"""P1-5 nutrition diagnosis and dashboard API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import dashboard, nutrition
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.schemas.dashboard import (
    DashboardActivitySummary,
    DashboardHealthScoreSummary,
    DashboardNutrientSummary,
    DashboardScoreComponent,
    DashboardScoreComponents,
    DashboardSummaryResponse,
    DashboardSupplementSummary,
    DashboardWeightSummary,
)
from src.models.schemas.nutrition import (
    NutritionDiagnosisLatestResponse,
    NutritionDiagnosisSummary,
)
from src.services.privacy import ConsentRequiredError


async def _fake_session_dependency() -> AsyncIterator[object]:
    """Yield a fake session for route tests.

    Yields:
        Fake session object.
    """
    yield object()


async def _allow_consent(*_args: object, **_kwargs: object) -> None:
    """No-op consent service for route tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.
    """


async def _deny_consent(*_args: object, **_kwargs: object) -> None:
    """Raise a missing-consent service error.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.

    Raises:
        ConsentRequiredError: Always raised for this test.
    """
    raise ConsentRequiredError("Consent is required.")


async def _record_noop_audit(*_args: object, **_kwargs: object) -> None:
    """No-op audit service for route tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.
    """


def _not_ready_diagnosis() -> NutritionDiagnosisLatestResponse:
    """Return a not-ready nutrition diagnosis response.

    Returns:
        Nutrition diagnosis response.
    """
    return NutritionDiagnosisLatestResponse(
        data_status="not_ready",
        result_id=None,
        created_at=None,
        algorithm_version=None,
        summary=NutritionDiagnosisSummary(
            total_count=0,
            deficient_count=0,
            low_count=0,
            adequate_count=0,
            excessive_count=0,
            risky_count=0,
            deficient_or_low_count=0,
            excessive_or_risky_count=0,
            summary_message="저장된 영양 분석 결과가 없습니다.",
        ),
        diagnoses=[],
        recommended_foods={},
        disclaimers=["결과는 건강관리 참고 정보이며 개인 건강 상태를 확정하지 않습니다."],
    )


def _dashboard_response() -> DashboardSummaryResponse:
    """Return a dashboard summary response.

    Returns:
        Dashboard summary response.
    """
    return DashboardSummaryResponse(
        as_of=datetime.now(UTC),
        nutrition=DashboardNutrientSummary(
            data_status="ready",
            latest_result_id=uuid4(),
            low_count=1,
            high_count=0,
            dataset_version="2020-sample",
            source_manifest_version="2.0",
        ),
        activity=DashboardActivitySummary(data_status="not_ready"),
        weight=DashboardWeightSummary(data_status="not_ready"),
        supplements=DashboardSupplementSummary(registered_count=2, requires_review_count=1),
        health_score=DashboardHealthScoreSummary(
            data_status="ready",
            score=78,
            label="good",
            label_text="양호",
            message="전반적으로 좋아요. 한두 가지만 더 신경 써보세요.",
            components=DashboardScoreComponents(
                activity=DashboardScoreComponent(available=True, subscore=82.0, weight=0.6),
                nutrition=DashboardScoreComponent(available=True, subscore=72.0, weight=0.4),
            ),
            disclaimers=["이 점수는 건강 관리 참고용이며 의학적 진단이 아닙니다."],
            algorithm_version="daily-health-score-v1.0.0",
        ),
        disclaimers=["결과는 건강관리 참고 정보이며 개인 건강 상태를 확정하지 않습니다."],
        algorithm_version="dashboard-v1.0.0",
    )


def _client() -> TestClient:
    """Return a TestClient with the DB session dependency replaced.

    Returns:
        FastAPI test client.
    """
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    return TestClient(app)


def test_latest_nutrition_diagnosis_returns_not_ready_without_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify latest diagnosis route returns a safe not-ready payload."""

    async def fake_latest(*_args: object, **_kwargs: object) -> NutritionDiagnosisLatestResponse:
        """Return a not-ready response.

        Args:
            *_args: Positional call arguments.
            **_kwargs: Keyword call arguments.

        Returns:
            Nutrition diagnosis response.
        """
        return _not_ready_diagnosis()

    monkeypatch.setattr(nutrition, "require_user_consent", _allow_consent)
    monkeypatch.setattr(nutrition, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(nutrition, "get_latest_nutrition_diagnosis", fake_latest)
    response = _client().get("/api/v1/nutrition/diagnosis/latest")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["data_status"] == "not_ready"
    assert "owner_subject" not in body
    assert "input_snapshot" not in body
    assert "result_snapshot" not in body


def test_latest_nutrition_diagnosis_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify latest diagnosis route fails closed without sensitive-health consent."""
    monkeypatch.setattr(nutrition, "require_user_consent", _deny_consent)
    monkeypatch.setattr(nutrition, "record_sensitive_audit_event", _record_noop_audit)
    response = _client().get("/api/v1/nutrition/diagnosis/latest")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"


def test_dashboard_summary_returns_owner_safe_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify dashboard route returns a safe summary payload."""

    async def fake_dashboard(*_args: object, **_kwargs: object) -> DashboardSummaryResponse:
        """Return a dashboard response.

        Args:
            *_args: Positional call arguments.
            **_kwargs: Keyword call arguments.

        Returns:
            Dashboard summary response.
        """
        return _dashboard_response()

    monkeypatch.setattr(dashboard, "require_user_consent", _allow_consent)
    monkeypatch.setattr(dashboard, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(dashboard, "build_dashboard_summary", fake_dashboard)
    response = _client().get("/api/v1/dashboard/summary")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["nutrition"]["low_count"] == 1
    assert body["supplements"]["registered_count"] == 2
    assert body["health_score"]["data_status"] == "ready"
    assert body["health_score"]["score"] == 78
    assert body["health_score"]["label"] == "good"
    assert body["health_score"]["components"]["activity"]["weight"] == 0.6
    assert body["health_score"]["algorithm_version"] == "daily-health-score-v1.0.0"
    assert "owner_subject" not in body
    assert "input_snapshot" not in body


def test_dashboard_summary_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify dashboard route fails closed without sensitive-health consent."""
    monkeypatch.setattr(dashboard, "require_user_consent", _deny_consent)
    monkeypatch.setattr(dashboard, "record_sensitive_audit_event", _record_noop_audit)
    response = _client().get("/api/v1/dashboard/summary")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"
