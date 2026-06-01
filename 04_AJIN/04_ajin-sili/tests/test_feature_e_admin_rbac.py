"""Feature E admin RBAC and hard-delete guard tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.routers import admin as admin_router


def test_admin_role_guard_accepts_role_level_only_user() -> None:
    """Admin router uses the shared role_level resolver."""

    user = SimpleNamespace(employee_id="HR-0001", role_level=4)

    assert admin_router._require_hr_admin(user) is None


def test_admin_role_guard_falls_back_to_role_name() -> None:
    """Legacy/test user contexts without role_level still use role fallback."""

    user = SimpleNamespace(employee_id="HR-0001", role="HR_ADMIN")

    assert admin_router._require_hr_admin(user) is None


def test_admin_role_guard_fails_closed_without_role() -> None:
    """Missing role_level and role is L0 and rejected."""

    with pytest.raises(HTTPException) as exc:
        admin_router._require_hr_admin(SimpleNamespace(employee_id="E001"))

    assert exc.value.status_code == 403


def test_hard_delete_is_disabled_by_default(monkeypatch) -> None:
    """SYS_ADMIN hard delete requires explicit AUTH_ALLOW_HARD_DELETE."""

    monkeypatch.delenv("AUTH_ALLOW_HARD_DELETE", raising=False)
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api")
    app.dependency_overrides[admin_router.get_current_user] = lambda: SimpleNamespace(
        employee_id="SYS-0001",
        role="SYS_ADMIN",
        role_level=5,
        name="sys",
        department="IT전략팀",
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.request(
        "DELETE",
        "/api/admin/users/E001",
        json={"confirm_employee_id": "E001", "reason": "retention exception"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "hard_delete_disabled"


def test_hard_delete_requires_reason_before_policy_check(monkeypatch) -> None:
    """Hard delete requests must include a human reason for auditability."""

    monkeypatch.setenv("AUTH_ALLOW_HARD_DELETE", "true")
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api")
    app.dependency_overrides[admin_router.get_current_user] = lambda: SimpleNamespace(
        employee_id="SYS-0001",
        role="SYS_ADMIN",
        role_level=5,
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.request(
        "DELETE",
        "/api/admin/users/E001",
        json={"confirm_employee_id": "E001", "reason": ""},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "hard_delete_reason_required"
