"""Health sync API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import health
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.db.health import HealthSyncBatch
from src.models.schemas.health import HealthSyncRequest
from src.security.auth import AuthenticatedUser
from src.services.health_sync import HealthSyncConflictError, HealthSyncResult
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


def _payload() -> dict[str, object]:
    """Return a valid health sync payload.

    Returns:
        JSON payload dictionary.
    """
    return {
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
    }


def _stored_batch() -> HealthSyncBatch:
    """Return a stored health sync batch fixture.

    Returns:
        Health sync batch row.
    """
    now = datetime.now(UTC)
    return HealthSyncBatch(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        client_batch_id="ios-2026-05-12T12-10-00Z",
        source_platform="ios_healthkit",
        record_count=1,
        accepted_count=1,
        rejected_count=0,
        input_snapshot={
            "date_min": "2026-05-12",
            "date_max": "2026-05-12",
            "source_platform_counts": {"ios_healthkit": 1},
            "metric_presence_counts": {
                "steps": 1,
                "weight_kg": 1,
                "resting_heart_rate_bpm": 1,
                "active_energy_kcal": 1,
            },
        },
        result_snapshot={"accepted_count": 1, "rejected_count": 0},
        synced_at=now,
        created_at=now,
        updated_at=now,
    )


def _client() -> TestClient:
    """Return a TestClient with the DB session dependency replaced.

    Returns:
        FastAPI test client.
    """
    app = create_app()
    # Routes adopted get_rls_context_session (ambient-tx Step 4, RLS Stage-2
    # rollout); overriding get_async_session alone no longer reaches them.
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    return TestClient(app)


def test_sync_health_daily_aggregates_uses_current_user_and_returns_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify health sync route stores current-user aggregates."""
    captured: dict[str, object] = {}
    batch = _stored_batch()

    async def fake_sync(
        _session: object,
        user: AuthenticatedUser,
        request: HealthSyncRequest,
    ) -> HealthSyncResult:
        """Capture route inputs and return a stored batch.

        Args:
            _session: Fake session dependency.
            user: Authenticated user passed by the route.
            request: Validated sync payload.

        Returns:
            Fake persisted health sync result.
        """
        captured["subject"] = user.subject
        captured["client_batch_id"] = request.client_batch_id
        return HealthSyncResult(
            batch=batch, accepted_count=1, rejected_count=0, synced_at=batch.synced_at
        )

    monkeypatch.setattr(health, "require_user_consent", _allow_consent)
    monkeypatch.setattr(health, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(health, "sync_health_daily_aggregates_service", fake_sync)

    response = _client().post("/api/v1/health/sync", json=_payload())

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert captured["subject"] == "local-dev-user"
    assert captured["client_batch_id"] == "ios-2026-05-12T12-10-00Z"
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 0
    assert body["batch_id"] == str(batch.id)
    assert "owner_subject" not in body
    assert "input_snapshot" not in body


def test_sync_health_daily_aggregates_requires_health_device_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify health sync fails closed without health-device consent."""
    monkeypatch.setattr(health, "require_user_consent", _deny_consent)
    monkeypatch.setattr(health, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post("/api/v1/health/sync", json=_payload())

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"


def test_sync_health_daily_aggregates_rejects_mass_assignment_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify server-owned fields are not accepted in request bodies."""
    monkeypatch.setattr(health, "require_user_consent", _allow_consent)
    monkeypatch.setattr(health, "record_sensitive_audit_event", _record_noop_audit)
    payload = {**_payload(), "owner_subject": "attacker", "accepted_count": 999}

    response = _client().post("/api/v1/health/sync", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_sync_health_daily_aggregates_rejects_empty_metric_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify health records must include at least one metric."""
    monkeypatch.setattr(health, "require_user_consent", _allow_consent)
    monkeypatch.setattr(health, "record_sensitive_audit_event", _record_noop_audit)
    payload = {
        "records": [{"measured_date": "2026-05-12", "source_platform": "manual"}],
    }

    response = _client().post("/api/v1/health/sync", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_sync_health_daily_aggregates_returns_409_for_idempotency_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify conflicting client batch ids return a stable 409 error."""

    async def fake_sync(*_args: object, **_kwargs: object) -> HealthSyncResult:
        """Raise an idempotency conflict.

        Args:
            *_args: Positional call arguments.
            **_kwargs: Keyword call arguments.

        Returns:
            Never returns.

        Raises:
            HealthSyncConflictError: Always raised for this test.
        """
        raise HealthSyncConflictError("client_batch_id was already used for different records.")

    monkeypatch.setattr(health, "require_user_consent", _allow_consent)
    monkeypatch.setattr(health, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(health, "sync_health_daily_aggregates_service", fake_sync)

    response = _client().post("/api/v1/health/sync", json=_payload())

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"]["code"] == "idempotency_conflict"
