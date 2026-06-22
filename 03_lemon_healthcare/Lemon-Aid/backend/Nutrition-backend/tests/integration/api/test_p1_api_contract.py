"""P1 API and security contract tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import dashboard, meals, supplements
from src.config import Settings, get_settings
from src.db.dependencies import get_async_session, get_rls_context_session
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
from src.models.schemas.meal import MealRecordListResponse
from src.models.schemas.taxonomy import (
    FoodCatalogItemListResponse,
    FoodCatalogItemSummary,
    FoodCourseSummary,
    FoodCuisineListResponse,
    FoodCuisineSummary,
    SupplementCategoryListResponse,
    SupplementCategorySummary,
)
from src.security import auth as auth_dependencies
from src.security.auth import AuthenticatedUser
from src.services.taxonomy_catalog import TaxonomyFilterNotFoundError


def _openapi_schema() -> dict[str, Any]:
    """Return the generated OpenAPI schema.

    Returns:
        OpenAPI schema dictionary from the FastAPI app.
    """
    client = TestClient(create_app())
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    return cast(dict[str, Any], response.json())


def _jwt_settings() -> Settings:
    """Return JWT-enabled settings for authentication contract tests.

    Returns:
        Settings configured for JWT auth.
    """
    return Settings(
        auth_mode="jwt",
        jwt_issuer="https://auth.example.com/",
        jwt_audience="lemon-api",
        jwt_jwks_url="https://auth.example.com/.well-known/jwks.json",
    )


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


async def _record_noop_audit(*_args: object, **_kwargs: object) -> None:
    """No-op audit service for route tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.
    """


def _user_with_scopes(*scopes: str) -> AuthenticatedUser:
    """Return an authenticated test principal with explicit scopes.

    Args:
        scopes: OAuth scopes exposed to the route dependency under test.

    Returns:
        Authenticated user fixture.
    """
    return AuthenticatedUser(subject="user_123", scopes=tuple(scopes))


def _dashboard_response() -> DashboardSummaryResponse:
    """Return a dashboard response fixture.

    Returns:
        Dashboard summary response.
    """
    return DashboardSummaryResponse(
        as_of=datetime.now(UTC),
        nutrition=DashboardNutrientSummary(
            data_status="not_ready",
            low_count=0,
            high_count=0,
            source_manifest_version=None,
        ),
        activity=DashboardActivitySummary(),
        weight=DashboardWeightSummary(),
        supplements=DashboardSupplementSummary(registered_count=0, requires_review_count=0),
        health_score=DashboardHealthScoreSummary(
            data_status="not_ready",
            components=DashboardScoreComponents(
                activity=DashboardScoreComponent(available=False, subscore=None, weight=0.0),
                nutrition=DashboardScoreComponent(available=False, subscore=None, weight=0.0),
            ),
            disclaimers=["이 점수는 건강 관리 참고용이며 의학적 진단이 아닙니다."],
            algorithm_version="daily-health-score-v1.0.0",
        ),
        disclaimers=["결과는 건강관리 참고 정보이며 개인 건강 상태를 확정하지 않습니다."],
        algorithm_version="dashboard-v1.0.0",
    )


def test_openapi_exposes_bearer_auth_security_scheme() -> None:
    """Verify OpenAPI documents the JWT BearerAuth contract."""
    schema = _openapi_schema()

    security_scheme = schema["components"]["securitySchemes"]["BearerAuth"]
    assert security_scheme["type"] == "http"
    assert security_scheme["scheme"] == "bearer"
    assert security_scheme["bearerFormat"] == "JWT"
    assert "OAuth/OIDC Bearer access token" in security_scheme["description"]


def test_p1_contract_endpoints_are_registered_with_required_scopes() -> None:
    """Verify P1 endpoints expose frozen route-level scope contracts."""
    schema = _openapi_schema()

    expected = {
        ("/api/v1/supplements/analyze", "post"): (
            "p1_2_intake_ready",
            ["supplement:write"],
        ),
        ("/api/v1/supplements/analyze-multi", "post"): (
            "p1_2_intake_ready",
            ["supplement:write"],
        ),
        ("/api/v1/supplements/analysis-sessions", "post"): (
            "p1_2_intake_ready",
            ["supplement:write"],
        ),
        ("/api/v1/supplements/analysis-sessions/{analysis_group_id}/images", "post"): (
            "p1_2_intake_ready",
            ["supplement:write"],
        ),
        ("/api/v1/supplements/analysis-sessions/{analysis_group_id}/finalize", "post"): (
            "p1_2_intake_ready",
            ["supplement:write"],
        ),
        ("/api/v1/supplements/analyses/{analysis_id}/ocr-text", "post"): (
            "p1_2_intake_ready",
            ["supplement:write"],
        ),
        ("/api/v1/supplements/analyses/{analysis_id}/explain", "post"): (
            "p1_2_intake_ready",
            ["supplement:write"],
        ),
        ("/api/v1/meals/analyze-image", "post"): (
            "p1_2_intake_ready",
            ["meal:write"],
        ),
        ("/api/v1/meals/cuisines", "get"): (
            "p1_2_intake_ready",
            ["meal:read"],
        ),
        ("/api/v1/meals/foods", "get"): (
            "p1_2_intake_ready",
            ["meal:read"],
        ),
        ("/api/v1/meals", "get"): (
            "p1_2_intake_ready",
            ["meal:read"],
        ),
        ("/api/v1/supplements", "post"): ("p1_4_registration_ready", ["supplement:write"]),
        ("/api/v1/supplements", "get"): ("p1_4_registration_ready", ["supplement:read"]),
        ("/api/v1/supplements/categories", "get"): (
            "p1_4_registration_ready",
            ["supplement:read"],
        ),
        ("/api/v1/supplements/{supplement_id}", "get"): (
            "p1_4_registration_ready",
            ["supplement:read"],
        ),
        ("/api/v1/supplements/{supplement_id}", "delete"): (
            "p1_4_registration_ready",
            ["supplement:delete"],
        ),
        ("/api/v1/health/sync", "post"): ("p1_6_health_sync_ready", ["health:write"]),
        ("/api/v1/dashboard/summary", "get"): (
            "p1_5_deficiency_dashboard_ready",
            ["dashboard:read"],
        ),
        ("/api/v1/nutrition/diagnosis/latest", "get"): (
            "p1_5_deficiency_dashboard_ready",
            ["analysis:read"],
        ),
    }

    for (path, method), (contract_status, required_scopes) in expected.items():
        operation = schema["paths"][path][method]
        assert operation["x-contract-status"] == contract_status
        assert operation["x-required-scopes"] == required_scopes
        assert operation["security"] == [{"BearerAuth": []}]


def test_p1_contract_endpoints_expose_required_consents() -> None:
    """Verify P1 endpoints document consent gates before implementation starts."""
    schema = _openapi_schema()

    assert schema["paths"]["/api/v1/supplements/analyze"]["post"]["x-required-consents"] == [
        "ocr_image_processing"
    ]
    assert schema["paths"]["/api/v1/supplements/analyze"]["post"]["x-conditional-consents"] == [
        "external_ocr_processing"
    ]
    assert schema["paths"]["/api/v1/supplements/analyze-multi"]["post"]["x-required-consents"] == [
        "ocr_image_processing"
    ]
    assert schema["paths"]["/api/v1/supplements/analyze-multi"]["post"][
        "x-conditional-consents"
    ] == ["external_ocr_processing"]
    assert schema["paths"]["/api/v1/supplements/analysis-sessions"]["post"][
        "x-required-consents"
    ] == ["ocr_image_processing"]
    assert schema["paths"]["/api/v1/supplements/analysis-sessions/{analysis_group_id}/images"][
        "post"
    ]["x-required-consents"] == ["ocr_image_processing"]
    assert schema["paths"]["/api/v1/supplements/analysis-sessions/{analysis_group_id}/images"][
        "post"
    ]["x-conditional-consents"] == ["external_ocr_processing"]
    assert schema["paths"]["/api/v1/supplements/analysis-sessions/{analysis_group_id}/finalize"][
        "post"
    ]["x-required-consents"] == ["ocr_image_processing"]
    assert schema["paths"]["/api/v1/supplements/analyses/{analysis_id}/ocr-text"]["post"][
        "x-required-consents"
    ] == ["ocr_image_processing"]
    assert schema["paths"]["/api/v1/supplements/analyses/{analysis_id}/explain"]["post"][
        "x-required-consents"
    ] == ["ocr_image_processing"]
    assert schema["paths"]["/api/v1/meals/analyze-image"]["post"]["x-required-consents"] == [
        "food_image_processing"
    ]
    assert schema["paths"]["/api/v1/supplements"]["post"]["x-required-consents"] == [
        "sensitive_health_analysis"
    ]
    assert schema["paths"]["/api/v1/health/sync"]["post"]["x-required-consents"] == [
        "health_device_data"
    ]
    assert schema["paths"]["/api/v1/dashboard/summary"]["get"]["x-required-consents"] == [
        "sensitive_health_analysis"
    ]
    assert schema["paths"]["/api/v1/nutrition/diagnosis/latest"]["get"]["x-required-consents"] == [
        "sensitive_health_analysis"
    ]


def test_p1_dashboard_endpoint_returns_summary_after_auth_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify implemented dashboard route is callable after auth in development."""

    async def fake_build_dashboard_summary(
        *_args: object,
        **_kwargs: object,
    ) -> DashboardSummaryResponse:
        """Return a fake dashboard response.

        Args:
            *_args: Positional call arguments.
            **_kwargs: Keyword call arguments.

        Returns:
            Dashboard summary response.
        """
        return _dashboard_response()

    monkeypatch.setattr(dashboard, "require_user_consent", _allow_consent)
    monkeypatch.setattr(dashboard, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(dashboard, "build_dashboard_summary", fake_build_dashboard_summary)
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["algorithm_version"] == "dashboard-v1.0.0"


def test_taxonomy_catalog_endpoints_return_safe_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify taxonomy catalog routes serialize active lookup rows."""
    captured: dict[str, object] = {}

    async def fake_list_supplement_categories(
        _session: object,
        *,
        q: str | None,
        limit: int,
        offset: int,
    ) -> SupplementCategoryListResponse:
        """Return a supplement taxonomy fixture through the route layer."""
        captured["supplement_category_query"] = (q, limit, offset)
        return SupplementCategoryListResponse(
            results=[
                SupplementCategorySummary(
                    id=uuid4(),
                    category_key="vitamin",
                    display_name="비타민",
                    sort_order=1,
                )
            ],
            limit=limit,
            offset=offset,
        )

    async def fake_list_food_cuisines(_session: object) -> FoodCuisineListResponse:
        """Return a cuisine taxonomy fixture through the route layer."""
        return FoodCuisineListResponse(
            results=[
                FoodCuisineSummary(
                    id=uuid4(),
                    cuisine_code="korean",
                    display_name_ko="한식",
                    display_name_en="Korean",
                    sort_order=1,
                    courses=[
                        FoodCourseSummary(
                            id=uuid4(),
                            course_code="soup_stew",
                            display_name_ko="국·탕·찌개",
                            display_name_en="Soup and Stew",
                            sort_order=2,
                        )
                    ],
                )
            ]
        )

    async def fake_list_food_catalog_items(
        _session: object,
        *,
        cuisine_code: str | None,
        course_code: str | None,
        q: str | None,
        limit: int,
        offset: int,
    ) -> FoodCatalogItemListResponse:
        """Return a food catalog fixture through the route layer."""
        captured["food_catalog_query"] = (cuisine_code, course_code, q, limit, offset)
        return FoodCatalogItemListResponse(
            results=[
                FoodCatalogItemSummary(
                    id=uuid4(),
                    cuisine_code="korean",
                    course_code="soup_stew",
                    canonical_name_ko="된장찌개",
                    canonical_name_en="Soybean Paste Stew",
                    source="manual_seed",
                )
            ],
            limit=limit,
            offset=offset,
        )

    monkeypatch.setattr(supplements, "list_supplement_categories", fake_list_supplement_categories)
    monkeypatch.setattr(meals, "list_food_cuisines", fake_list_food_cuisines)
    monkeypatch.setattr(meals, "list_food_catalog_items", fake_list_food_catalog_items)
    app = create_app()
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    # Catalog read routes adopted get_rls_context_session (RLS Stage-2 rollout).
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    supplement_response = client.get("/api/v1/supplements/categories?q=vit&limit=3&offset=1")
    cuisine_response = client.get("/api/v1/meals/cuisines")
    food_response = client.get(
        "/api/v1/meals/foods?cuisine_code=korean&course_code=soup_stew&q=찌개&limit=5"
    )

    assert supplement_response.status_code == status.HTTP_200_OK
    assert supplement_response.json()["results"][0]["category_key"] == "vitamin"
    assert captured["supplement_category_query"] == ("vit", 3, 1)
    assert cuisine_response.status_code == status.HTTP_200_OK
    assert cuisine_response.json()["results"][0]["courses"][0]["course_code"] == "soup_stew"
    assert food_response.status_code == status.HTTP_200_OK
    assert food_response.json()["results"][0]["canonical_name_ko"] == "된장찌개"
    assert captured["food_catalog_query"] == ("korean", "soup_stew", "찌개", 5, 0)


def test_user_supplement_taxonomy_filter_not_found_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify stale supplement taxonomy filters fail with a stable 422 code."""

    async def fake_list_user_supplement_records(*_args: object, **_kwargs: object) -> object:
        """Raise the service-level stale taxonomy filter error."""
        raise TaxonomyFilterNotFoundError("Supplement category filter was not found.")

    monkeypatch.setattr(
        supplements,
        "list_user_supplement_records",
        fake_list_user_supplement_records,
    )
    app = create_app()
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    # list_user_supplements adopted get_rls_context_session (RLS Stage-2 rollout).
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.get("/api/v1/supplements?category_key=stale")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"]["code"] == "taxonomy_filter_not_found"


def test_meal_list_requires_meal_read_scope_and_returns_empty_filtered_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify meal list read access is separate from meal write access."""

    async def fake_current_user_write_only() -> AuthenticatedUser:
        """Return a principal that can write meals but cannot read them."""
        return _user_with_scopes("meal:write")

    async def fake_current_user_read() -> AuthenticatedUser:
        """Return a principal that can read meals."""
        return _user_with_scopes("meal:read")

    async def fake_list_user_meal_records(
        *,
        limit: int,
        offset: int,
        **_kwargs: object,
    ) -> MealRecordListResponse:
        """Return an empty current-user meal page."""
        return MealRecordListResponse(results=[], limit=limit, offset=offset)

    monkeypatch.setattr(meals, "list_user_meal_records", fake_list_user_meal_records)
    monkeypatch.setattr(meals, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    app.dependency_overrides[auth_dependencies.require_current_user] = fake_current_user_write_only
    client = TestClient(app)

    forbidden_response = client.get("/api/v1/meals")

    app.dependency_overrides[auth_dependencies.require_current_user] = fake_current_user_read
    ok_response = client.get("/api/v1/meals?cuisine_code=korean&course_code=soup_stew")

    assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN
    assert ok_response.status_code == status.HTTP_200_OK
    assert ok_response.json() == {"results": [], "limit": 20, "offset": 0}


def test_meal_taxonomy_filter_not_found_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify stale meal taxonomy filters fail with a stable 422 code."""

    async def fake_list_user_meal_records(*_args: object, **_kwargs: object) -> object:
        """Raise the service-level stale taxonomy filter error."""
        raise TaxonomyFilterNotFoundError("Food cuisine filter was not found.")

    monkeypatch.setattr(meals, "list_user_meal_records", fake_list_user_meal_records)
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.get("/api/v1/meals?cuisine_code=stale")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"]["code"] == "taxonomy_filter_not_found"


def test_p1_contract_endpoints_reject_missing_jwt_credentials() -> None:
    """Verify P1 route contracts keep JWT auth in production-style mode."""
    app = create_app(settings=_jwt_settings())
    app.dependency_overrides[get_settings] = _jwt_settings
    client = TestClient(app)

    response = client.get("/api/v1/supplements")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["www-authenticate"] == 'Bearer realm="lemon-healthcare"'


def test_p1_openapi_contains_contract_error_examples() -> None:
    """Verify P1 endpoints expose expected error response contracts."""
    schema = _openapi_schema()
    supplement_analyze = schema["paths"]["/api/v1/supplements/analyze"]["post"]["responses"]
    supplement_create = schema["paths"]["/api/v1/supplements"]["post"]["responses"]
    health_sync = schema["paths"]["/api/v1/health/sync"]["post"]["responses"]

    assert "501" not in supplement_analyze
    assert "501" not in supplement_create
    assert "501" not in health_sync
    assert "idempotency_conflict" in health_sync["409"]["content"]["application/json"]["examples"]
    assert (
        "payload_too_large" in supplement_analyze["413"]["content"]["application/json"]["examples"]
    )
    assert (
        "unsupported_media_type"
        in supplement_analyze["415"]["content"]["application/json"]["examples"]
    )
