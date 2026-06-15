"""tests/test_permissions_endpoints.py — PR-E8 신규 endpoint 검증.

5 케이스:
1. test_list_endpoint_returns_empty_initially — DB 빈 상태 → items=[]
2. test_list_endpoint_returns_seeded_permission — upsert 후 list 에 노출
3. test_get_endpoint_returns_404_for_missing   — 미존재 key → 404
4. test_preview_endpoint_returns_diff           — before/after 응답 구조
5. test_endpoints_require_hr_admin              — role<4 → 403
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """permissions_db PATH 격리."""
    import core.auth.permissions_db as pdb
    monkeypatch.setattr(pdb, "PERMISSIONS_DB_PATH", tmp_path / "permissions.db")
    pdb.init_permissions_db()
    return pdb


def _make_client(role_level: int = 4):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.dependencies import get_current_user
    from backend.routers.admin import router

    mock_user = MagicMock()
    mock_user.role = "HR_ADMIN" if role_level == 4 else "SYS_ADMIN" if role_level >= 5 else "EMPLOYEE"
    mock_user.employee_id = "HR-0001"
    mock_user.position = ""

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    patcher = patch("core.auth.rbac.get_role_level", return_value=role_level)
    patcher.start()
    client = TestClient(app, raise_server_exceptions=False)
    return client, patcher


# ════════════════════════════════════════════════════════════
# 1. GET /permissions/list — 빈 상태
# ════════════════════════════════════════════════════════════


def test_list_endpoint_returns_empty_initially(isolated_db):
    client, patcher = _make_client(role_level=4)
    try:
        r = client.get("/api/admin/permissions/list")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []
    finally:
        patcher.stop()


# ════════════════════════════════════════════════════════════
# 2. GET /permissions/list — seeded permission 노출
# ════════════════════════════════════════════════════════════


def test_list_endpoint_returns_seeded_permission(isolated_db):
    isolated_db.upsert_permission(
        {
            "key": "compliance.read",
            "description": "Read compliance docs",
            "min_role": "MANAGER",
            "departments": ["품질경영팀"],
            "allow_same_division": False,
            "min_position_level": 0,
        },
        actor="seed",
    )
    client, patcher = _make_client(role_level=4)
    try:
        r = client.get("/api/admin/permissions/list")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["key"] == "compliance.read"
        assert item["min_role"] == "MANAGER"
        # departments set → sorted list
        assert item["departments"] == ["품질경영팀"]
    finally:
        patcher.stop()


# ════════════════════════════════════════════════════════════
# 3. GET /permissions/{key} — missing → 404
# ════════════════════════════════════════════════════════════


def test_get_endpoint_returns_404_for_missing(isolated_db):
    client, patcher = _make_client(role_level=4)
    try:
        r = client.get("/api/admin/permissions/does.not.exist")
        assert r.status_code == 404
    finally:
        patcher.stop()


# ════════════════════════════════════════════════════════════
# 4. POST /permissions/preview — diff 구조
# ════════════════════════════════════════════════════════════


def test_preview_endpoint_returns_diff(isolated_db):
    isolated_db.upsert_permission(
        {
            "key": "feature.x",
            "description": "old desc",
            "min_role": "EMPLOYEE",
            "departments": None,
        },
        actor="seed",
    )
    client, patcher = _make_client(role_level=4)
    try:
        body = {
            "permission_key": "feature.x",
            "new_value": {
                "key": "feature.x",
                "description": "new desc",
                "min_role": "MANAGER",
                "departments": ["품질보증팀"],
            },
            "reason": "권한 강화",
        }
        r = client.post("/api/admin/permissions/preview", json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["permission_key"] == "feature.x"
        assert data["is_new"] is False
        assert data["before"]["description"] == "old desc"
        assert data["after"]["min_role"] == "MANAGER"
        assert data["reason"] == "권한 강화"
    finally:
        patcher.stop()


# ════════════════════════════════════════════════════════════
# 5. role < 4 → 403
# ════════════════════════════════════════════════════════════


def test_endpoints_require_hr_admin(isolated_db):
    client, patcher = _make_client(role_level=2)  # MANAGER (L2) — HR_ADMIN 미만
    try:
        r = client.get("/api/admin/permissions/list")
        assert r.status_code == 403
        r2 = client.get("/api/admin/permissions/any.key")
        assert r2.status_code == 403
        r3 = client.post(
            "/api/admin/permissions/preview",
            json={"permission_key": "x", "new_value": {}, "reason": "y"},
        )
        assert r3.status_code == 403
    finally:
        patcher.stop()
