"""Privacy API route tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.api.v1 import privacy
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.db.privacy import ConsentRecord, DeletionRequest
from src.models.schemas.privacy import ConsentType, DeletionRequestStatus, DeletionRequestType
from src.security.auth import AuthenticatedUser


async def _fake_session_dependency() -> AsyncIterator[object]:
    """Yield a fake session for API tests.

    Yields:
        Fake session object.
    """
    yield object()


def _consent_record(*, granted: bool = True) -> ConsentRecord:
    """Return a consent record fixture.

    Args:
        granted: Whether the consent event is a grant (True) or revocation (False).

    Returns:
        Consent record ORM object.
    """
    now = datetime.now(UTC)
    return ConsentRecord(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        consent_type=ConsentType.SENSITIVE_HEALTH_ANALYSIS.value,
        policy_version="2026-05-11",
        granted=granted,
        occurred_at=now,
        revoked_at=None if granted else now,
        created_at=now,
        updated_at=now,
    )


def _deletion_request() -> DeletionRequest:
    """Return a deletion request fixture.

    Returns:
        Deletion request ORM object.
    """
    now = datetime.now(UTC)
    return DeletionRequest(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        request_type=DeletionRequestType.ALL_USER_DATA.value,
        status=DeletionRequestStatus.COMPLETED.value,
        requested_at=now,
        completed_at=now,
        deleted_counts={"analysis_results": 1, "consent_records": 1},
        created_at=now,
        updated_at=now,
    )


def test_grant_consent_route_returns_policy_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify consent grant route uses the current user and returns action state."""
    captured: dict[str, object] = {}

    async def fake_grant(
        _session: object,
        user: AuthenticatedUser,
        consent_type: ConsentType,
        *_args: object,
    ) -> ConsentRecord:
        """Capture grant route inputs and return a fake consent record.

        Args:
            _session: Fake session dependency.
            user: Authenticated user passed by the route.
            consent_type: Requested consent type.
            *_args: Request and settings arguments.

        Returns:
            Fake consent record.
        """
        captured["subject"] = user.subject
        captured["consent_type"] = consent_type
        return _consent_record()

    monkeypatch.setattr(privacy, "grant_consent", fake_grant)
    app = create_app()
    # grant_consent route adopted get_rls_context_session (ambient-tx Step 6b).
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.post("/api/v1/me/privacy/consents/sensitive_health_analysis")

    assert response.status_code == status.HTTP_201_CREATED
    assert captured["subject"] == "local-dev-user"
    assert captured["consent_type"] == ConsentType.SENSITIVE_HEALTH_ANALYSIS
    assert response.json()["granted"] is True


def test_revoke_consent_route_returns_revocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify consent revoke route adopted get_rls_context_session and returns the revocation."""
    captured: dict[str, object] = {}

    async def fake_revoke(
        _session: object,
        user: AuthenticatedUser,
        consent_type: ConsentType,
        *_args: object,
    ) -> ConsentRecord:
        """Capture revoke route inputs and return a fake revoked consent record.

        Args:
            _session: Fake session dependency.
            user: Authenticated user passed by the route.
            consent_type: Requested consent type.
            *_args: Request and settings arguments.

        Returns:
            Fake revoked consent record.
        """
        captured["subject"] = user.subject
        captured["consent_type"] = consent_type
        return _consent_record(granted=False)

    monkeypatch.setattr(privacy, "revoke_consent", fake_revoke)
    app = create_app()
    # revoke_consent route adopted get_rls_context_session (ambient-tx Step 6b).
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.delete("/api/v1/me/privacy/consents/sensitive_health_analysis")

    assert response.status_code == status.HTTP_200_OK
    assert captured["subject"] == "local-dev-user"
    assert captured["consent_type"] == ConsentType.SENSITIVE_HEALTH_ANALYSIS
    assert response.json()["granted"] is False


def test_create_deletion_request_route_returns_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify deletion request route delegates owner-scoped deletion."""
    captured: dict[str, object] = {}

    async def fake_delete_all(
        _session: object,
        user: AuthenticatedUser,
        *_args: object,
    ) -> DeletionRequest:
        """Capture delete-all route inputs and return a fake deletion request.

        Args:
            _session: Fake session dependency.
            user: Authenticated user passed by the route.
            *_args: Request and settings arguments.

        Returns:
            Fake deletion request.
        """
        captured["subject"] = user.subject
        return _deletion_request()

    monkeypatch.setattr(privacy, "create_delete_all_user_data_request", fake_delete_all)
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    client = TestClient(app)

    response = client.post(
        "/api/v1/me/data-deletion-requests", json={"request_type": "all_user_data"}
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert captured["subject"] == "local-dev-user"
    assert response.json()["status"] == "completed"
    assert response.json()["deleted_counts"] == {"analysis_results": 1, "consent_records": 1}
