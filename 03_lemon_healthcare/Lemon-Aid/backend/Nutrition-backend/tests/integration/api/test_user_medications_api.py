"""Current-user medication profile API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import user_medications
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.schemas.user_medication import (
    UserMedicationCreate,
    UserMedicationResponse,
)
from src.security.auth import AuthenticatedUser
from src.services.privacy import ConsentRequiredError


async def _fake_session_dependency() -> AsyncIterator[object]:
    """Yield a fake session for route tests."""
    yield object()


async def _allow_consent(*_args: object, **_kwargs: object) -> None:
    """No-op consent service for route tests."""


async def _deny_consent(*_args: object, **_kwargs: object) -> None:
    """Raise a missing-consent service error."""
    raise ConsentRequiredError("Consent is required.")


async def _record_noop_audit(*_args: object, **_kwargs: object) -> None:
    """No-op audit service for route tests."""


def _client() -> TestClient:
    """Return a TestClient with DB session replaced."""
    app = create_app()
    # Routes adopted get_rls_context_session (ambient-tx Step 4, RLS Stage-2
    # rollout); overriding get_async_session alone no longer reaches them.
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    return TestClient(app)


def _medication_response(
    *,
    medication_id: UUID | None = None,
    display_name: str = "amlodipine",
    normalized_name: str = "amlodipine",
    medication_class: str | None = "calcium_channel_blocker",
    is_active: bool = True,
) -> UserMedicationResponse:
    """Return a saved medication response fixture."""
    now = datetime.now(UTC)
    return UserMedicationResponse(
        id=medication_id or uuid4(),
        display_name=display_name,
        normalized_name=normalized_name,
        medication_class=medication_class,
        condition_tags=["hypertension"],
        confirmation_status="user_confirmed",
        is_active=is_active,
        last_confirmed_at=now,
        created_at=now,
        updated_at=now,
    )


def test_user_medication_crud_routes_use_current_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify create/list/update/deactivate API contract for saved medications."""
    captured: dict[str, object] = {}
    medication_id = uuid4()

    async def _create(
        _session: object,
        user: AuthenticatedUser,
        _settings: object,
        request: UserMedicationCreate,
    ) -> UserMedicationResponse:
        captured["create_subject"] = user.subject
        captured["create_display_name"] = request.display_name
        return _medication_response(medication_id=medication_id)

    async def _list(
        _session: object,
        user: AuthenticatedUser,
        _settings: object,
    ) -> list[UserMedicationResponse]:
        captured["list_subject"] = user.subject
        return [_medication_response(medication_id=medication_id)]

    async def _update(
        _session: object,
        user: AuthenticatedUser,
        _settings: object,
        medication_id_arg: UUID,
        request: object,
    ) -> UserMedicationResponse:
        captured["update_subject"] = user.subject
        captured["update_id"] = medication_id_arg
        captured["update_request"] = request
        return _medication_response(medication_id=medication_id_arg, display_name="losartan")

    async def _deactivate(
        _session: object,
        user: AuthenticatedUser,
        _settings: object,
        medication_id_arg: UUID,
    ) -> UserMedicationResponse:
        captured["deactivate_subject"] = user.subject
        captured["deactivate_id"] = medication_id_arg
        return _medication_response(medication_id=medication_id_arg, is_active=False)

    monkeypatch.setattr(user_medications, "require_user_consent", _allow_consent)
    monkeypatch.setattr(user_medications, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(user_medications, "create_user_medication_service", _create)
    monkeypatch.setattr(user_medications, "list_user_medications_service", _list)
    monkeypatch.setattr(user_medications, "update_user_medication_service", _update)
    monkeypatch.setattr(user_medications, "deactivate_user_medication_service", _deactivate)

    create_response = _client().post(
        "/api/v1/me/medications",
        json={
            "display_name": "amlodipine",
            "normalized_name": "amlodipine",
            "medication_class": "calcium_channel_blocker",
            "condition_tags": ["hypertension"],
        },
    )
    list_response = _client().get("/api/v1/me/medications")
    update_response = _client().patch(
        f"/api/v1/me/medications/{medication_id}",
        json={"display_name": "losartan", "medication_class": "arb"},
    )
    deactivate_response = _client().post(f"/api/v1/me/medications/{medication_id}/deactivate")

    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.json()["display_name"] == "amlodipine"
    assert "dose_text" not in str(create_response.json())
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["items"][0]["id"] == str(medication_id)
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["display_name"] == "losartan"
    assert deactivate_response.status_code == status.HTTP_200_OK
    assert deactivate_response.json()["is_active"] is False
    assert captured["create_subject"] == "local-dev-user"
    assert captured["list_subject"] == "local-dev-user"
    assert captured["update_id"] == medication_id
    assert captured["deactivate_id"] == medication_id


def test_create_user_medication_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify saved medication writes fail closed without sensitive consent."""
    monkeypatch.setattr(user_medications, "require_user_consent", _deny_consent)
    monkeypatch.setattr(user_medications, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post(
        "/api/v1/me/medications",
        json={
            "display_name": "amlodipine",
            "normalized_name": "amlodipine",
            "medication_class": "calcium_channel_blocker",
            "condition_tags": ["hypertension"],
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"


def test_user_medication_schema_rejects_raw_or_dosage_fields() -> None:
    """Verify v1 storage cannot accept free-text medical details or dosing fields."""
    response = _client().post(
        "/api/v1/me/medications",
        json={
            "display_name": "amlodipine",
            "normalized_name": "amlodipine",
            "medication_class": "calcium_channel_blocker",
            "condition_tags": ["hypertension"],
            "dose_text": "5mg every morning",
            "free_text_note": "doctor note",
            "raw_ocr_text": "label image text",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
