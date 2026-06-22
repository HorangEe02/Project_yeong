"""Health profile and metric sample API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import health
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.db.health import BodyProfileSnapshot, HealthDailySummary, HealthMetricSample
from src.models.schemas.health import BodyProfileSnapshotCreate, HealthMetricSampleCreate
from src.security.auth import AuthenticatedUser
from src.services.privacy import ConsentRequiredError


async def _fake_session_dependency() -> AsyncIterator[object]:
    """Yield a fake session for route tests.

    Yields:
        Fake session object.
    """
    yield object()


async def _allow_consent(*_args: object, **_kwargs: object) -> None:
    """No-op consent service."""


async def _deny_consent(*_args: object, **_kwargs: object) -> None:
    """Always deny consent.

    Raises:
        ConsentRequiredError: Always raised.
    """
    raise ConsentRequiredError("Consent is required.")


async def _record_noop_audit(*_args: object, **_kwargs: object) -> None:
    """No-op audit service."""


def _client() -> TestClient:
    """Return test client with DB session override.

    Returns:
        FastAPI test client.
    """
    app = create_app()
    # Routes adopted get_rls_context_session (ambient-tx Step 4, RLS Stage-2
    # rollout); overriding get_async_session alone no longer reaches them.
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    return TestClient(app)


def _profile_row() -> BodyProfileSnapshot:
    """Return a profile snapshot fixture.

    Returns:
        Body profile ORM row.
    """
    now = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)
    return BodyProfileSnapshot(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        effective_at=now,
        source="manual",
        birth_year=1990,
        height_cm=Decimal("172.50"),
        weight_kg=Decimal("68.40"),
        consent_snapshot={"consent_type": "sensitive_health_analysis"},
        created_at=now,
        updated_at=now,
    )


def test_create_profile_snapshot_returns_sanitized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify profile route stores current-user data and hides owner fields."""
    captured: dict[str, object] = {}
    row = _profile_row()

    async def fake_create(
        _session: object,
        user: AuthenticatedUser,
        request: BodyProfileSnapshotCreate,
    ) -> BodyProfileSnapshot:
        """Capture route inputs and return a profile row."""
        captured["subject"] = user.subject
        captured["height_cm"] = request.height_cm
        return row

    monkeypatch.setattr(health, "require_user_consent", _allow_consent)
    monkeypatch.setattr(health, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(health, "create_body_profile_snapshot", fake_create)

    response = _client().post(
        "/api/v1/health/profile-snapshots",
        json={"height_cm": "172.50", "weight_kg": "68.40"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert captured["subject"] == "local-dev-user"
    body = response.json()
    assert body["height_cm"] == "172.50"
    assert "owner_subject" not in body
    assert "consent_snapshot" not in body


def test_create_profile_snapshot_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify profile writes fail closed without sensitive-health consent."""
    monkeypatch.setattr(health, "require_user_consent", _deny_consent)
    monkeypatch.setattr(health, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post("/api/v1/health/profile-snapshots", json={"weight_kg": "68.40"})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"


def test_metric_sample_rejects_mass_assignment_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify metric sample route rejects server-owned fields."""
    monkeypatch.setattr(health, "require_user_consent", _allow_consent)
    monkeypatch.setattr(health, "record_sensitive_audit_event", _record_noop_audit)
    payload = {
        "metric_type": "weight_kg",
        "measured_at": "2026-05-27T10:00:00Z",
        "value_numeric": "68.4000",
        "unit": "kg",
        "owner_subject": "attacker",
    }

    response = _client().post("/api/v1/health/metric-samples", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_create_metric_sample_returns_sanitized_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify metric route hides owner and source hashes."""
    now = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)
    sample = HealthMetricSample(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        metric_type="weight_kg",
        measured_at=now,
        value_numeric=Decimal("68.4000"),
        unit="kg",
        source_platform="manual",
        source_record_hash="a" * 64,
        quality_flags=["manual_entry"],
        created_at=now,
        updated_at=now,
    )

    async def fake_create(
        _session: object,
        _user: AuthenticatedUser,
        _request: HealthMetricSampleCreate,
    ) -> HealthMetricSample:
        """Return fake metric sample."""
        return sample

    monkeypatch.setattr(health, "require_user_consent", _allow_consent)
    monkeypatch.setattr(health, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(health, "create_health_metric_sample", fake_create)

    response = _client().post(
        "/api/v1/health/metric-samples",
        json={
            "metric_type": "weight_kg",
            "measured_at": "2026-05-27T10:00:00Z",
            "value_numeric": "68.4000",
            "unit": "kg",
            "source_record_hash": "a" * 64,
            "quality_flags": ["manual_entry"],
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["metric_type"] == "weight_kg"
    assert "owner_subject" not in body
    assert "source_record_hash" not in body


def test_daily_summary_response_hides_owner_and_source_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify daily summary route returns current-user summaries without internal keys."""
    row = HealthDailySummary(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        measured_date=date(2026, 5, 27),
        source_platform="manual",
        steps=7200,
        source_record_hash="b" * 64,
        synced_at=datetime(2026, 5, 27, 10, 0, tzinfo=UTC),
    )

    async def fake_list(*_args: object, **_kwargs: object) -> list[HealthDailySummary]:
        """Return one fake summary."""
        return [row]

    monkeypatch.setattr(health, "require_user_consent", _allow_consent)
    monkeypatch.setattr(health, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(health, "list_health_daily_summaries", fake_list)

    response = _client().get("/api/v1/health/daily-summary")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["summaries"][0]["steps"] == 7200
    assert "owner_subject" not in body["summaries"][0]
    assert "source_record_hash" not in body["summaries"][0]
