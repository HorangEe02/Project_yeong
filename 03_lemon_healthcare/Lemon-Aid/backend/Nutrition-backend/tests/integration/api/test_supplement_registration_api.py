"""User supplement registration API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import supplements
from src.db.dependencies import get_async_session, get_rls_context_session
from src.main import create_app
from src.models.db.supplement import UserSupplement, UserSupplementIngredient
from src.models.schemas.supplement import (
    UserSupplementCreate,
    UserSupplementListResponse,
)
from src.models.schemas.taxonomy import SupplementCategorySummary
from src.security.auth import AuthenticatedUser
from src.services.privacy import ConsentRequiredError
from src.services.supplement_registration import (
    SupplementRegistrationValidationError,
    UserSupplementStoreResult,
)


class _RouteFakeTransaction:
    """No-op async transaction context for the route-owned RLS seam."""

    async def __aenter__(self) -> _RouteFakeTransaction:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        return None


class _RouteFakeScalars:
    def all(self) -> list[object]:
        return []


class _RouteFakeSession:
    """Async session double supporting rls_request_transaction in route tests."""

    def __init__(self) -> None:
        # A real AsyncSession always exposes ``.info``; rls_request_transaction reads it.
        self.info: dict[str, object] = {}

    def begin(self) -> _RouteFakeTransaction:
        return _RouteFakeTransaction()

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        """No-op: absorbs the RLS set_config statements."""

    async def scalar(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def scalars(self, *_args: object, **_kwargs: object) -> _RouteFakeScalars:
        return _RouteFakeScalars()

    async def commit(self) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


async def _fake_session_dependency() -> AsyncIterator[object]:
    """Yield a fake session for route tests.

    Yields:
        Fake async session supporting the route-owned RLS transaction seam.
    """
    yield _RouteFakeSession()


async def _allow_consent(*_args: object, **_kwargs: object) -> None:
    """No-op consent dependency for route tests.

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
    """No-op audit writer for route tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.
    """


def _payload() -> dict[str, object]:
    """Return a valid user supplement confirmation payload.

    Returns:
        JSON payload dictionary.
    """
    return {
        "analysis_id": "11111111-1111-4111-8111-111111111111",
        "display_name": "Vitamin D 1000 IU",
        "manufacturer": "Sample Nutrition",
        "ingredients": [
            {
                "display_name": "Vitamin D",
                "original_name": "Vitamin D",
                "nutrient_code": "vitamin_d_ug",
                "amount": 25,
                "unit": "ug",
                "confidence": 1,
                "source": "user_confirmed",
            }
        ],
        "serving": {"amount": 1, "unit": "capsule", "daily_servings": 1},
        "intake_schedule": {"frequency": "daily", "time_of_day": ["morning"]},
        "evidence_refs": ["span-1"],
        "user_confirmed": True,
    }


def _stored_supplement() -> UserSupplement:
    """Return a stored supplement row fixture.

    Returns:
        User supplement row.
    """
    now = datetime.now(UTC)
    return UserSupplement(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        display_name="Vitamin D 1000 IU",
        manufacturer="Sample Nutrition",
        serving_snapshot={"amount": 1, "unit": "capsule", "daily_servings": 1},
        intake_schedule={"frequency": "daily", "time_of_day": ["morning"]},
        evidence_refs=["span-1"],
        user_confirmed_at=now,
        created_at=now,
        updated_at=now,
    )


def _stored_ingredient(supplement_id: object) -> UserSupplementIngredient:
    """Return a stored supplement ingredient row fixture.

    Args:
        supplement_id: Parent supplement id.

    Returns:
        User supplement ingredient row.
    """
    return UserSupplementIngredient(
        id=uuid4(),
        user_supplement_id=supplement_id,
        display_name="Vitamin D",
        nutrient_code="vitamin_d_ug",
        amount=Decimal("25"),
        unit="ug",
        confidence=Decimal("1"),
        source="user_confirmed",
        sort_order=0,
    )


def test_create_user_supplement_uses_current_user_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify registration route stores a current-user confirmed supplement."""
    captured: dict[str, object] = {}
    supplement = _stored_supplement()
    ingredient = _stored_ingredient(supplement.id)

    async def fake_store(
        _session: object,
        user: AuthenticatedUser,
        request: UserSupplementCreate,
        _settings: object,
    ) -> UserSupplementStoreResult:
        """Capture route inputs and return a stored row.

        Args:
                _session: Fake session dependency.
                user: Authenticated user passed by the route.
                request: Validated request payload.
                _settings: Route settings passed through by the API.

            Returns:
            Fake persisted supplement result.
        """
        captured["subject"] = user.subject
        captured["analysis_id"] = request.analysis_id
        captured["evidence_refs"] = request.evidence_refs
        captured["ingredient_original_name"] = request.ingredients[0].original_name
        return UserSupplementStoreResult(supplement=supplement, ingredients=[ingredient])

    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(supplements, "create_user_supplement_from_confirmation", fake_store)
    app = create_app()
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.post("/api/v1/supplements", json=_payload())

    assert response.status_code == status.HTTP_201_CREATED
    assert captured["subject"] == "local-dev-user"
    assert str(captured["analysis_id"]) == "11111111-1111-4111-8111-111111111111"
    assert captured["evidence_refs"] == ["span-1"]
    assert captured["ingredient_original_name"] == "Vitamin D"
    body = response.json()
    assert body["display_name"] == "Vitamin D 1000 IU"
    assert body["evidence_refs"] == ["span-1"]
    assert body["ingredients"][0].get("original_name") is None
    assert "owner_subject" not in body


def test_create_user_supplement_passes_category_key_and_echoes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a chosen category_key flows to the service and is echoed back."""
    captured: dict[str, object] = {}
    supplement = _stored_supplement()
    supplement.category_key = "비타민B"
    ingredient = _stored_ingredient(supplement.id)
    summary = SupplementCategorySummary(
        id=uuid4(),
        category_key="비타민B",
        display_name="비타민B",
        sort_order=1,
    )

    async def fake_store(
        _session: object,
        _user: AuthenticatedUser,
        request: UserSupplementCreate,
        _settings: object,
    ) -> UserSupplementStoreResult:
        """Capture the chosen category key and return a stored row."""
        captured["category_key"] = request.category_key
        return UserSupplementStoreResult(
            supplement=supplement,
            ingredients=[ingredient],
            categories=[summary],
        )

    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(supplements, "create_user_supplement_from_confirmation", fake_store)
    app = create_app()
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements",
        json={**_payload(), "category_key": "비타민B"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert captured["category_key"] == "비타민B"
    body = response.json()
    assert body["category_key"] == "비타민B"
    assert [item["category_key"] for item in body["categories"]] == ["비타민B"]


def test_create_user_supplement_rejects_unknown_category_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an unknown category key maps to HTTP 422."""

    async def fake_store(
        _session: object,
        _user: AuthenticatedUser,
        _request: UserSupplementCreate,
        _settings: object,
    ) -> UserSupplementStoreResult:
        """Raise the validation error the service raises for unknown categories."""
        raise SupplementRegistrationValidationError("선택한 영양제 분류를 찾을 수 없어요.")

    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(supplements, "create_user_supplement_from_confirmation", fake_store)
    app = create_app()
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements",
        json={**_payload(), "category_key": "없는분류"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"]["code"] == "invalid_supplement_confirmation"


def test_create_user_supplement_rejects_mass_assignment_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify owner and server-owned fields are not accepted in request bodies."""
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app()
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)
    payload = {
        **_payload(),
        "owner_subject": "attacker",
        "matched_product_id": "22222222-2222-4222-8222-222222222222",
    }

    response = client.post("/api/v1/supplements", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_create_user_supplement_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify supplement registration fails closed without sensitive-health consent."""
    monkeypatch.setattr(supplements, "require_user_consent", _deny_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app()
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.post("/api/v1/supplements", json=_payload())

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"


def test_list_user_supplements_returns_owner_scoped_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify list route returns stored current-user supplement records."""
    supplement = _stored_supplement()
    ingredient = _stored_ingredient(supplement.id)
    response_model = supplements.user_supplement_to_response(supplement, [ingredient])

    async def fake_list(
        _session: object,
        _user: AuthenticatedUser,
        limit: int,
        offset: int,
        *,
        category_key: str | None = None,
        category_id: object | None = None,
        q: str | None = None,
    ) -> UserSupplementListResponse:
        """Return a fake list response.

        Args:
            _session: Fake session dependency.
            _user: Authenticated user passed by the route.
            limit: Requested limit.
            offset: Requested offset.
            category_key: Optional category key filter passed by the route.
            category_id: Optional category id filter passed by the route.
            q: Optional text filter passed by the route.

        Returns:
            Fake list response.
        """
        assert category_key is None
        assert category_id is None
        assert q is None
        return UserSupplementListResponse(results=[response_model], limit=limit, offset=offset)

    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(supplements, "list_user_supplement_records", fake_list)
    app = create_app()
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.get("/api/v1/supplements")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"][0]["ingredients"][0]["nutrient_code"] == "vitamin_d_ug"


def test_get_user_supplement_returns_404_for_inaccessible_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify detail route hides non-owner or missing supplement records."""

    async def fake_get(*_args: object, **_kwargs: object) -> None:
        """Return no supplement row.

        Args:
            *_args: Positional call arguments.
            **_kwargs: Keyword call arguments.

        Returns:
            None.
        """

    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(supplements, "get_user_supplement_record", fake_get)
    app = create_app()
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.get(f"/api/v1/supplements/{uuid4()}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_user_supplement_returns_204_when_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify delete route delegates owner-scoped soft deletion."""
    captured: dict[str, object] = {}

    async def fake_delete(
        _session: object,
        user: AuthenticatedUser,
        supplement_id: object,
    ) -> bool:
        """Capture delete inputs and simulate a successful delete.

        Args:
            _session: Fake session dependency.
            user: Authenticated user passed by the route.
            supplement_id: Requested supplement id.

        Returns:
            True to simulate a deleted row.
        """
        captured["subject"] = user.subject
        captured["supplement_id"] = supplement_id
        return True

    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(supplements, "soft_delete_user_supplement", fake_delete)
    app = create_app()
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)
    supplement_id = uuid4()

    response = client.delete(f"/api/v1/supplements/{supplement_id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert captured["subject"] == "local-dev-user"
    assert captured["supplement_id"] == supplement_id
