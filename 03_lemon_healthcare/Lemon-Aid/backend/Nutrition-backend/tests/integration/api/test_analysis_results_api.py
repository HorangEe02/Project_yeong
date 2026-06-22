"""Persisted analysis result API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import analysis_results
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.db.analysis_result import AnalysisResult
from src.models.schemas.algorithm import ActivityScoreRequest
from src.models.schemas.analysis_result import AnalysisType
from src.security.auth import AuthenticatedUser
from src.services.privacy import ConsentRequiredError


async def _fake_session_dependency() -> AsyncIterator[object]:
    """Yield a fake session for API tests.

    Yields:
        Fake session object.
    """
    yield object()


def _jwt_settings() -> Settings:
    """Return JWT-enabled settings for authentication failure tests.

    Returns:
        Settings configured for JWT auth.
    """
    return Settings(
        auth_mode="jwt",
        jwt_issuer="https://auth.example.com/",
        jwt_audience="lemon-api",
        jwt_jwks_url="https://auth.example.com/.well-known/jwks.json",
    )


def _activity_payload() -> dict[str, object]:
    """Return a valid activity result creation payload.

    Returns:
        JSON payload dictionary.
    """
    return {
        "profile": {
            "age": 50,
            "sex": "female",
            "height_cm": 160,
            "weight_kg": 68,
            "chronic_diseases": ["diabetes"],
        },
        "daily_steps": 7000,
        "target_hr_minutes": 20,
    }


def _record() -> AnalysisResult:
    """Return a persisted analysis result fixture.

    Returns:
        Analysis result ORM object.
    """
    return AnalysisResult(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        analysis_type=AnalysisType.ACTIVITY_SCORE.value,
        algorithm_version="activity-v1.0.0",
        input_snapshot={"daily_steps": 7000},
        result_snapshot={"recommended_steps": 7524, "v4_score": 90.0},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def _allow_consent(*_args: object, **_kwargs: object) -> None:
    """No-op consent dependency for route tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.
    """


async def _record_noop_audit(*_args: object, **_kwargs: object) -> None:
    """No-op audit writer for route tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.
    """


def test_create_analysis_result_requires_authentication() -> None:
    """Verify protected storage endpoints reject missing JWT credentials in JWT mode."""
    app = create_app(settings=_jwt_settings())
    app.dependency_overrides[get_settings] = _jwt_settings
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.post("/api/v1/analysis-results/activity-score", json=_activity_payload())

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_activity_result_uses_current_user_and_ignores_mass_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify client-supplied owner/output fields cannot drive persisted ownership or results."""
    captured: dict[str, object] = {}

    async def fake_store(
        _session: object,
        user: AuthenticatedUser,
        request: ActivityScoreRequest,
    ) -> AnalysisResult:
        """Capture route inputs and return a fake stored row.

        Args:
            _session: Fake session dependency.
            user: Authenticated user passed by the route.
            request: Validated request body.

        Returns:
            Fake persisted row.
        """
        captured["subject"] = user.subject
        captured["has_owner_subject"] = hasattr(request, "owner_subject")
        captured["has_result_snapshot"] = hasattr(request, "result_snapshot")
        return _record()

    monkeypatch.setattr(analysis_results, "store_activity_score_result", fake_store)
    monkeypatch.setattr(analysis_results, "require_user_consent", _allow_consent)
    monkeypatch.setattr(analysis_results, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)
    payload = {
        **_activity_payload(),
        "owner_subject": "attacker",
        "result_snapshot": {"v4_score": 100},
    }

    response = client.post("/api/v1/analysis-results/activity-score", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert captured == {
        "subject": "local-dev-user",
        "has_owner_subject": False,
        "has_result_snapshot": False,
    }
    body = response.json()
    assert "owner_subject" not in body
    assert "input_snapshot" not in body
    assert body["result_snapshot"]["recommended_steps"] == 7524


def test_create_activity_result_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify analysis result storage fails closed when sensitive-health consent is absent."""

    async def deny_consent(*_args: object, **_kwargs: object) -> None:
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

    monkeypatch.setattr(analysis_results, "require_user_consent", deny_consent)
    monkeypatch.setattr(analysis_results, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.post("/api/v1/analysis-results/activity-score", json=_activity_payload())

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Consent is required."


def test_get_analysis_result_returns_404_for_non_owner_or_missing_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify result detail route uses a not-found response for inaccessible rows."""

    async def fake_get(
        _session: object,
        _user: AuthenticatedUser,
        _result_id: object,
    ) -> None:
        """Return no row for an inaccessible result.

        Args:
            _session: Fake session dependency.
            _user: Authenticated user passed by the route.
            _result_id: Requested result identifier.

        Returns:
            None to simulate an owner-scoped miss.
        """

    monkeypatch.setattr(analysis_results, "get_analysis_result", fake_get)
    monkeypatch.setattr(analysis_results, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.get(f"/api/v1/analysis-results/{uuid4()}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_analysis_result_returns_204_when_owned_row_is_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify delete route delegates owner-scoped deletion and returns an empty success response."""
    captured: dict[str, object] = {}

    async def fake_delete(
        _session: object,
        user: AuthenticatedUser,
        result_id: object,
        *_args: object,
    ) -> bool:
        """Capture delete route inputs and simulate a successful delete.

        Args:
            _session: Fake session dependency.
            user: Authenticated user passed by the route.
            result_id: Requested result identifier.
            *_args: Request and settings arguments.

        Returns:
            True to simulate a deleted row.
        """
        captured["subject"] = user.subject
        captured["result_id"] = result_id
        return True

    monkeypatch.setattr(analysis_results, "delete_analysis_result_for_user", fake_delete)
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)
    result_id = uuid4()

    response = client.delete(f"/api/v1/analysis-results/{result_id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert captured["subject"] == "local-dev-user"
    assert captured["result_id"] == result_id
