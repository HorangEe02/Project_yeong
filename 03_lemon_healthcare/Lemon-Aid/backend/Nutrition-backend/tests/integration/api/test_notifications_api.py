"""Reminder preference API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import notifications
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.schemas.notification import (
    ReminderCategory,
    ReminderPreferenceCreate,
    ReminderPreferenceResponse,
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
    """Return a TestClient with the DB session dependency replaced."""
    app = create_app()
    # Routes adopted get_rls_context_session (ambient-tx Step 4, RLS Stage-2
    # rollout); overriding get_async_session alone no longer reaches them.
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    return TestClient(app)


def _reminder_response(
    *,
    reminder_id: UUID | None = None,
    category: ReminderCategory = ReminderCategory.SUPPLEMENT_REMINDER,
    enabled: bool = True,
    message: str = "영양제 기록 시간을 확인해 주세요.",
) -> ReminderPreferenceResponse:
    """Return a reminder response fixture."""
    now = datetime.now(UTC)
    return ReminderPreferenceResponse(
        id=reminder_id or uuid4(),
        category=category,
        time_of_day="09:00",
        timezone="Asia/Seoul",
        enabled=enabled,
        message=message,
        created_at=now,
        updated_at=now,
        disabled_at=None if enabled else now,
    )


def test_reminder_preferences_crud_routes_use_current_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify reminder preference create/list/update/disable API contract."""
    captured: dict[str, object] = {}
    reminder_id = uuid4()

    async def _create(
        _session: object,
        user: AuthenticatedUser,
        request: ReminderPreferenceCreate,
    ) -> ReminderPreferenceResponse:
        captured["create_subject"] = user.subject
        captured["create_category"] = request.category
        return _reminder_response(reminder_id=reminder_id)

    async def _list(
        _session: object,
        user: AuthenticatedUser,
    ) -> list[ReminderPreferenceResponse]:
        captured["list_subject"] = user.subject
        return [_reminder_response(reminder_id=reminder_id)]

    async def _update(
        _session: object,
        user: AuthenticatedUser,
        reminder_id_arg: UUID,
        _request: object,
    ) -> ReminderPreferenceResponse:
        captured["update_subject"] = user.subject
        captured["update_id"] = reminder_id_arg
        return _reminder_response(reminder_id=reminder_id_arg, message="저녁 기록 확인")

    async def _disable(
        _session: object,
        user: AuthenticatedUser,
        reminder_id_arg: UUID,
    ) -> ReminderPreferenceResponse:
        captured["disable_subject"] = user.subject
        captured["disable_id"] = reminder_id_arg
        return _reminder_response(reminder_id=reminder_id_arg, enabled=False)

    monkeypatch.setattr(notifications, "require_user_consent", _allow_consent)
    monkeypatch.setattr(notifications, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(notifications, "create_reminder_preference_service", _create)
    monkeypatch.setattr(notifications, "list_reminder_preferences_service", _list)
    monkeypatch.setattr(notifications, "update_reminder_preference_service", _update)
    monkeypatch.setattr(notifications, "disable_reminder_preference_service", _disable)

    create_response = _client().post(
        "/api/v1/notifications/reminders",
        json={
            "category": "supplement_reminder",
            "time_of_day": "09:00",
            "timezone": "Asia/Seoul",
            "enabled": True,
            "message": "영양제 기록 시간을 확인해 주세요.",
        },
    )
    list_response = _client().get("/api/v1/notifications/reminders")
    update_response = _client().patch(
        f"/api/v1/notifications/reminders/{reminder_id}",
        json={"time_of_day": "20:30", "message": "저녁 기록 확인"},
    )
    disable_response = _client().post(f"/api/v1/notifications/reminders/{reminder_id}/disable")

    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.json()["category"] == "supplement_reminder"
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["items"][0]["id"] == str(reminder_id)
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["message"] == "저녁 기록 확인"
    assert disable_response.status_code == status.HTTP_200_OK
    assert disable_response.json()["enabled"] is False
    assert captured == {
        "create_subject": "local-dev-user",
        "create_category": ReminderCategory.SUPPLEMENT_REMINDER,
        "list_subject": "local-dev-user",
        "update_subject": "local-dev-user",
        "update_id": reminder_id,
        "disable_subject": "local-dev-user",
        "disable_id": reminder_id,
    }


def test_create_reminder_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify health-related reminder creation fails closed without consent."""
    monkeypatch.setattr(notifications, "require_user_consent", _deny_consent)
    monkeypatch.setattr(notifications, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post(
        "/api/v1/notifications/reminders",
        json={
            "category": "daily_coaching_prompt",
            "time_of_day": "18:00",
            "timezone": "Asia/Seoul",
            "message": "오늘 코칭을 확인해 주세요.",
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"


def test_disabled_reminders_are_not_selected_for_dispatch() -> None:
    """Verify disabled reminders are excluded from dispatch candidates."""
    enabled = _reminder_response(enabled=True)
    disabled = _reminder_response(enabled=False)

    selected = notifications.select_enabled_reminders_for_dispatch([enabled, disabled])

    assert selected == [enabled]


def test_reminder_text_avoids_medical_diagnosis_treatment_or_prescription() -> None:
    """Verify reminder text rejects medical diagnosis/treatment/prescription language."""
    with pytest.raises(ValueError):
        ReminderPreferenceCreate(
            category=ReminderCategory.SAFETY_FOLLOW_UP,
            time_of_day="18:00",
            timezone="Asia/Seoul",
            message="진단과 처방을 위해 지금 확인하세요.",
        )
