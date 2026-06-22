"""Current-user food record API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import food_records
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.schemas.food_record import FoodRecordCreate, FoodRecordResponse
from src.security.auth import AuthenticatedUser
from src.services.privacy import ConsentRequiredError


async def _fake_session_dependency() -> AsyncIterator[object]:
    yield object()


async def _allow_consent(*_args: object, **_kwargs: object) -> None:
    pass


async def _deny_consent(*_args: object, **_kwargs: object) -> None:
    raise ConsentRequiredError("Consent is required.")


async def _record_noop_audit(*_args: object, **_kwargs: object) -> None:
    pass


def _client() -> TestClient:
    app = create_app()
    # The /me/food-records routes adopted get_rls_context_session (RLS Stage-2
    # ambient-tx rollout, Step 3); overriding get_async_session alone no longer
    # reaches them.
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    return TestClient(app)


def _food_response(*, food_record_id: UUID | None = None) -> FoodRecordResponse:
    now = datetime.now(UTC)
    return FoodRecordResponse(
        id=food_record_id or uuid4(),
        recorded_date=date(2026, 5, 31),
        meal_type="lunch",
        display_items=["라면"],
        amount_text="1그릇",
        estimated_tags=["sodium_high", "refined_carb", "soup_or_stew"],
        rough_nutrient_axes=["sodium_high", "carbohydrate_high"],
        user_confirmed=True,
        source="manual",
        food_db_match_id=None,
        match_confidence=None,
        nutrient_estimates=None,
        created_at=now,
        updated_at=now,
    )


def test_food_record_crud_routes_use_current_user(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    food_record_id = uuid4()

    async def _create(
        _session: object,
        user: AuthenticatedUser,
        _settings: object,
        request: FoodRecordCreate,
    ) -> FoodRecordResponse:
        captured["create_subject"] = user.subject
        captured["create_items"] = request.display_items
        return _food_response(food_record_id=food_record_id)

    async def _list(
        _session: object,
        user: AuthenticatedUser,
        _settings: object,
        *_args: object,
        **_kwargs: object,
    ) -> list[FoodRecordResponse]:
        captured["list_subject"] = user.subject
        return [_food_response(food_record_id=food_record_id)]

    async def _update(
        _session: object,
        user: AuthenticatedUser,
        _settings: object,
        record_id_arg: UUID,
        request: object,
    ) -> FoodRecordResponse:
        captured["update_subject"] = user.subject
        captured["update_id"] = record_id_arg
        captured["update_request"] = request
        return _food_response(food_record_id=record_id_arg)

    async def _delete(
        _session: object,
        user: AuthenticatedUser,
        _settings: object,
        record_id_arg: UUID,
    ) -> None:
        captured["delete_subject"] = user.subject
        captured["delete_id"] = record_id_arg

    monkeypatch.setattr(food_records, "require_user_consent", _allow_consent)
    monkeypatch.setattr(food_records, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(food_records, "create_food_record_service", _create)
    monkeypatch.setattr(food_records, "list_food_records_service", _list)
    monkeypatch.setattr(food_records, "update_food_record_service", _update)
    monkeypatch.setattr(food_records, "delete_food_record_service", _delete)

    create_response = _client().post(
        "/api/v1/me/food-records",
        json={
            "recorded_date": "2026-05-31",
            "meal_type": "lunch",
            "display_items": ["라면"],
            "amount_text": "1그릇",
            "source": "manual",
        },
    )
    list_response = _client().get("/api/v1/me/food-records?date_from=2026-05-31")
    update_response = _client().patch(
        f"/api/v1/me/food-records/{food_record_id}",
        json={"display_items": ["닭가슴살 샐러드"], "estimated_tags": ["protein_food"]},
    )
    delete_response = _client().delete(f"/api/v1/me/food-records/{food_record_id}")

    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.json()["estimated_tags"] == [
        "sodium_high",
        "refined_carb",
        "soup_or_stew",
    ]
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["items"][0]["id"] == str(food_record_id)
    assert update_response.status_code == status.HTTP_200_OK
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert captured["create_subject"] == "local-dev-user"
    assert captured["list_subject"] == "local-dev-user"
    assert captured["update_id"] == food_record_id
    assert captured["delete_id"] == food_record_id


def test_create_food_record_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(food_records, "require_user_consent", _deny_consent)
    monkeypatch.setattr(food_records, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post(
        "/api/v1/me/food-records",
        json={
            "recorded_date": "2026-05-31",
            "meal_type": "lunch",
            "display_items": ["라면"],
            "source": "manual",
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"


def test_food_record_schema_rejects_raw_or_unconfirmed_fields() -> None:
    response = _client().post(
        "/api/v1/me/food-records",
        json={
            "recorded_date": "2026-05-31",
            "meal_type": "lunch",
            "display_items": ["라면"],
            "source": "manual",
            "raw_ocr_text": "label text",
            "raw_prompt": "what did I eat?",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
