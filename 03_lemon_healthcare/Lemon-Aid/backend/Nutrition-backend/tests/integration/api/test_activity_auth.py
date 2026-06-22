"""Auth + consent + audit integration tests for /activity/score."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any, Self, cast
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from src.api.v1 import activity as activity_module
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.db.privacy import AuditLog
from src.models.schemas.privacy import ConsentType
from src.security.auth import AuthenticatedUser, require_analysis_read
from src.services.privacy import ConsentRequiredError

_VALID_REQUEST = {
    "profile": {
        "age": 50,
        "sex": "female",
        "height_cm": 160,
        "weight_kg": 68,
        "chronic_diseases": ["diabetes", "hypertension"],
    },
    "daily_steps": 7000,
    "target_hr_minutes": 20,
}


class _TransactionContext:
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        return None


class _FakeSession:
    """Capture audit rows added by the route under test."""

    def __init__(self) -> None:
        self.audits: list[AuditLog] = []
        self.committed = False

    def begin(self) -> _TransactionContext:
        return _TransactionContext()

    def add(self, record: object) -> None:
        if isinstance(record, AuditLog):
            self.audits.append(record)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, record: object) -> None:
        audit = cast(AuditLog, record)
        if getattr(audit, "id", None) is None:
            audit.id = uuid4()
        audit.created_at = datetime.now(UTC)

    async def scalar(self, _statement: object) -> None:
        return None


def _session_dependency(session: _FakeSession) -> Callable[[], AsyncIterator[object]]:
    async def dependency() -> AsyncIterator[object]:
        yield session

    return dependency


async def _allow_consent(*_args: object, **_kwargs: object) -> None:
    return None


async def _record_noop(*_args: object, **_kwargs: object) -> None:
    return None


def test_returns_401_when_authentication_dependency_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the route propagates 401 from ``require_analysis_read``."""
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _session_dependency(_FakeSession())
    monkeypatch.setattr(activity_module, "require_user_consent", _allow_consent)
    monkeypatch.setattr(activity_module, "record_sensitive_audit_event", _record_noop)

    async def _reject_auth() -> AuthenticatedUser:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized"},
        )

    app.dependency_overrides[require_analysis_read] = _reject_auth
    client = TestClient(app)

    response = client.post("/api/v1/activity/score", json=_VALID_REQUEST)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_returns_403_when_sensitive_consent_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify missing SENSITIVE_HEALTH_ANALYSIS consent yields HTTP 403."""

    async def _deny(*_args: object, **_kwargs: object) -> None:
        raise ConsentRequiredError("User has not granted SENSITIVE_HEALTH_ANALYSIS consent.")

    monkeypatch.setattr(activity_module, "require_user_consent", _deny)
    monkeypatch.setattr(activity_module, "record_sensitive_audit_event", _record_noop)
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _session_dependency(_FakeSession())
    client = TestClient(app)

    response = client.post("/api/v1/activity/score", json=_VALID_REQUEST)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    body = response.json()
    assert body["detail"]["code"] == "consent_required"
    assert body["detail"]["required_consents"] == [ConsentType.SENSITIVE_HEALTH_ANALYSIS.value]


def test_returns_200_and_emits_audit_event_when_consent_granted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the success path records one ``activity_score_compute`` audit row."""
    captured_audits: list[dict[str, Any]] = []

    async def _capture_audit(*args: object, **kwargs: object) -> None:
        captured_audits.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(activity_module, "require_user_consent", _allow_consent)
    monkeypatch.setattr(activity_module, "record_sensitive_audit_event", _capture_audit)
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _session_dependency(_FakeSession())
    client = TestClient(app)

    response = client.post("/api/v1/activity/score", json=_VALID_REQUEST)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["bmi"]["category"] == "obese_1"
    assert body["recommended_steps"] == 7500
    assert len(captured_audits) == 1
    assert captured_audits[0]["kwargs"]["action"] == "activity_score_compute"
    assert captured_audits[0]["kwargs"]["resource_type"] == "activity_score"
    assert captured_audits[0]["kwargs"]["outcome"] == "success"
