"""Medical record and patient status API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import medical_records
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.db.medical import MedicalRecordCollection, PatientCondition, PatientStatusSnapshot
from src.models.schemas.medical import (
    MedicalRecordCreateRequest,
    PatientStatusSnapshotCreate,
    PatientStatusSnapshotResponse,
)
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
    # Routes adopted get_rls_context_session (ambient-tx Step 5, RLS Stage-2
    # rollout); overriding get_async_session alone no longer reaches them.
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    return TestClient(app)


def _collection() -> MedicalRecordCollection:
    """Return medical collection fixture.

    Returns:
        Medical record collection row.
    """
    now = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)
    return MedicalRecordCollection(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        record_type="condition",
        source="user_manual",
        status="active",
        consent_snapshot={"consent_type": "sensitive_health_analysis"},
        created_at=now,
        updated_at=now,
    )


def _condition(collection_id: object) -> PatientCondition:
    """Return condition fixture.

    Args:
        collection_id: Parent collection id.

    Returns:
        Patient condition row.
    """
    return PatientCondition(
        id=uuid4(),
        medical_collection_id=collection_id,
        condition_text="사용자 확인 질환명",
        condition_code_hash="b" * 64,
        clinical_status="active",
        source="user_confirmed",
        confirmed_at=datetime(2026, 5, 27, 10, 0, tzinfo=UTC),
    )


def test_create_medical_record_returns_sanitized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify medical record create route hides owner hash and code hash."""
    captured: dict[str, object] = {}
    collection = _collection()
    condition = _condition(collection.id)

    async def fake_create(
        _session: object,
        user: AuthenticatedUser,
        _settings: object,
        request: MedicalRecordCreateRequest,
    ) -> tuple[MedicalRecordCollection, list[PatientCondition], list[object]]:
        """Capture inputs and return fake persisted rows."""
        captured["subject"] = user.subject
        captured["record_type"] = request.record_type.value
        return collection, [condition], []

    monkeypatch.setattr(medical_records, "require_user_consent", _allow_consent)
    monkeypatch.setattr(medical_records, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(medical_records, "create_medical_record", fake_create)

    response = _client().post(
        "/api/v1/medical-records",
        json={
            "record_type": "condition",
            "condition": {
                "condition_text": "사용자 확인 질환명",
                "clinical_status": "active",
            },
            "user_confirmed": True,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert captured["subject"] == "local-dev-user"
    body = response.json()
    assert body["record_type"] == "condition"
    assert body["conditions"][0]["condition_text"] == "사용자 확인 질환명"
    assert "owner_subject_hash" not in str(body)
    assert "condition_code_hash" not in str(body)
    assert "source_document_id" not in str(body)


def test_create_medical_record_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify medical record writes fail closed without sensitive-health consent."""
    monkeypatch.setattr(medical_records, "require_user_consent", _deny_consent)
    monkeypatch.setattr(medical_records, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post(
        "/api/v1/medical-records",
        json={
            "record_type": "condition",
            "condition": {"condition_text": "사용자 확인 질환명"},
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"


def test_medical_record_rejects_mass_assignment_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify medical record body rejects server-owned fields."""
    monkeypatch.setattr(medical_records, "require_user_consent", _allow_consent)
    monkeypatch.setattr(medical_records, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post(
        "/api/v1/medical-records",
        json={
            "record_type": "condition",
            "condition": {"condition_text": "사용자 확인 질환명"},
            "owner_subject_hash": "a" * 64,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_patient_status_rejects_diagnostic_summary_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify patient status route rejects diagnostic/raw keys before service write."""
    monkeypatch.setattr(medical_records, "require_user_consent", _allow_consent)
    monkeypatch.setattr(medical_records, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post(
        "/api/v1/patient/status",
        json={"metric_summary": {"diagnosis": "not allowed"}},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_patient_status_latest_returns_non_diagnostic_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify latest patient status response is code-based and sanitized."""
    now = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)
    response_model = PatientStatusSnapshotResponse(
        id=uuid4(),
        status="ready",
        status_at=now,
        summary_type="system_derived",
        metric_summary={"steps_days_present": 3},
        medication_summary={"active_count": 2},
        risk_flags=["data_insufficient"],
        data_quality="partial",
        generated_by="backend_rule",
        expires_at=now + timedelta(hours=24),
    )

    async def fake_latest(
        _session: object,
        _user: AuthenticatedUser,
        _settings: object,
    ) -> PatientStatusSnapshotResponse:
        """Return fake latest status response."""
        return response_model

    monkeypatch.setattr(medical_records, "require_user_consent", _allow_consent)
    monkeypatch.setattr(medical_records, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(medical_records, "get_latest_patient_status_snapshot", fake_latest)

    response = _client().get("/api/v1/patient/status/latest")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["risk_flags"] == ["data_insufficient"]
    assert "owner_subject_hash" not in str(body)
    assert "diagnosis" not in str(body)
    assert "treatment_instruction" not in str(body)


def test_create_patient_status_returns_sanitized_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify patient status create route hides owner hash and raw fields."""
    now = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)
    snapshot = PatientStatusSnapshot(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        status_at=now,
        summary_type="system_derived",
        symptom_categories=[],
        metric_summary={"steps_days_present": 3},
        medication_summary={"active_count": 2},
        risk_flags=["data_insufficient"],
        data_quality="partial",
        generated_by="backend_rule",
        expires_at=now + timedelta(hours=24),
    )

    async def fake_create(
        _session: object,
        _user: AuthenticatedUser,
        _settings: object,
        request: PatientStatusSnapshotCreate,
    ) -> PatientStatusSnapshot:
        """Return fake created status snapshot."""
        assert request.metric_summary == {"steps_days_present": 3}
        return snapshot

    monkeypatch.setattr(medical_records, "require_user_consent", _allow_consent)
    monkeypatch.setattr(medical_records, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(medical_records, "create_patient_status_snapshot", fake_create)

    response = _client().post(
        "/api/v1/patient/status",
        json={
            "metric_summary": {"steps_days_present": 3},
            "medication_summary": {"active_count": 2},
            "risk_flags": ["data_insufficient"],
            "data_quality": "partial",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["status"] == "ready"
    assert "owner_subject_hash" not in str(body)
