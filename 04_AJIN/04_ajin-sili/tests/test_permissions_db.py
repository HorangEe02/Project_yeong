"""v4.7 PR-E7 — permissions.db CRUD + dict-fallback + migration 검증."""

from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path

import pytest


@pytest.fixture
def temp_permissions_db(tmp_path, monkeypatch):
    """permissions_db 의 DB 경로를 tmp 로 격리. 모듈 reload 로 PERMISSIONS_DB_PATH 갱신."""
    db_path = tmp_path / "permissions.db"

    # 모듈 import 후 상수만 patch (재import 없이도 _connect 가 항상 상수를 참조).
    import core.auth.permissions_db as pdb

    monkeypatch.setattr(pdb, "PERMISSIONS_DB_PATH", db_path)
    pdb.init_permissions_db()
    yield pdb
    # cleanup is automatic (tmp_path)


def _sample_perm(key: str = "test.demo", min_role: str = "EMPLOYEE") -> dict:
    return {
        "key": key,
        "description": f"테스트 권한 {key}",
        "min_role": min_role,
        "departments": {"품질보증팀", "ESG경영팀"},
        "allow_same_division": False,
        "min_position_level": 0,
    }


# ── DB init / CRUD ──────────────────────────────────────────────────────────


def test_init_permissions_db_idempotent(temp_permissions_db):
    pdb = temp_permissions_db
    pdb.init_permissions_db()
    pdb.init_permissions_db()
    # 테이블 3개 존재 확인
    conn = sqlite3.connect(str(pdb.PERMISSIONS_DB_PATH))
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    conn.close()
    names = {r[0] for r in rows}
    assert "permissions" in names
    assert "permission_change_requests" in names
    assert "permission_audit" in names


def test_upsert_permission_creates_row_and_audit(temp_permissions_db):
    pdb = temp_permissions_db
    pdb.upsert_permission(_sample_perm(), actor="alice")

    row = pdb.get_permission("test.demo")
    assert row is not None
    assert row["min_role"] == "EMPLOYEE"
    assert row["departments"] == {"품질보증팀", "ESG경영팀"}
    assert row["updated_by"] == "alice"

    audit = pdb.list_audit(permission_key="test.demo")
    assert len(audit) == 1
    assert audit[0]["action"] == "create"
    assert audit[0]["diff"]["before"] is None
    assert audit[0]["diff"]["after"]["min_role"] == "EMPLOYEE"


def test_get_permission_nonexistent_returns_none(temp_permissions_db):
    assert temp_permissions_db.get_permission("does.not.exist") is None


def test_list_permissions_sorted(temp_permissions_db):
    pdb = temp_permissions_db
    pdb.upsert_permission(_sample_perm("b.key"), actor="sys")
    pdb.upsert_permission(_sample_perm("a.key"), actor="sys")
    rows = pdb.list_permissions()
    keys = [r["key"] for r in rows]
    assert keys == ["a.key", "b.key"]


def test_delete_permission_records_audit(temp_permissions_db):
    pdb = temp_permissions_db
    pdb.upsert_permission(_sample_perm(), actor="bob")
    deleted = pdb.delete_permission("test.demo", actor="bob")
    assert deleted is True
    assert pdb.get_permission("test.demo") is None

    audit = pdb.list_audit(permission_key="test.demo")
    actions = [a["action"] for a in audit]
    assert "create" in actions and "delete" in actions

    # 없는 키는 False
    assert pdb.delete_permission("missing.key", actor="bob") is False


def test_upsert_permission_update_records_before_and_after_diff(temp_permissions_db):
    pdb = temp_permissions_db
    pdb.upsert_permission(_sample_perm(), actor="alice")
    updated = _sample_perm()
    updated["min_role"] = "MANAGER"
    updated["min_position_level"] = 4
    pdb.upsert_permission(updated, actor="bob")

    row = pdb.get_permission("test.demo")
    assert row["min_role"] == "MANAGER"
    assert row["min_position_level"] == 4
    assert row["updated_by"] == "bob"

    audit = pdb.list_audit(permission_key="test.demo")
    update_audit = next(a for a in audit if a["action"] == "update")
    assert update_audit["diff"]["before"]["min_role"] == "EMPLOYEE"
    assert update_audit["diff"]["after"]["min_role"] == "MANAGER"


# ── dict fallback ──────────────────────────────────────────────────────────


def test_db_first_lookup_with_dict_fallback(monkeypatch, tmp_path):
    """DB 가 비어있을 때 dict fallback 이 동작."""
    import core.auth.permissions as perms
    import core.auth.permissions_db as pdb

    empty_db = tmp_path / "empty.db"
    monkeypatch.setattr(pdb, "PERMISSIONS_DB_PATH", empty_db)
    pdb.init_permissions_db()

    # DB miss → dict fallback (compliance.view_dashboard 는 _CODE_DICT_PERMISSIONS 에 존재)
    p = perms.get_permission_def("compliance.view_dashboard")
    assert p is not None
    assert p.key == "compliance.view_dashboard"

    # DB hit 우선 — 동일 key 를 DB 에 다른 값으로 upsert 하면 DB 값 반환
    pdb.upsert_permission({
        "key": "compliance.view_dashboard",
        "description": "OVERRIDE",
        "min_role": "SYS_ADMIN",
        "departments": None,
        "allow_same_division": False,
        "min_position_level": 0,
    }, actor="test")
    p2 = perms.get_permission_def("compliance.view_dashboard")
    assert p2.description == "OVERRIDE"
    assert p2.min_role == "SYS_ADMIN"


# ── migration script ────────────────────────────────────────────────────────


def test_migration_script_dry_run_then_apply(monkeypatch, tmp_path):
    import core.auth.permissions_db as pdb
    from scripts import migrate_permissions_dict_to_db as mig

    db_path = tmp_path / "perm_mig.db"
    monkeypatch.setattr(pdb, "PERMISSIONS_DB_PATH", db_path)

    out_dry = mig.run(dry_run=True, apply=False)
    assert out_dry["mode"] == "dry-run"
    assert out_dry["new"] > 0
    assert out_dry["skip"] == 0
    # dry-run 은 DB 에 아무것도 쓰지 않음
    assert pdb.list_permissions() == []

    out_apply = mig.run(dry_run=False, apply=True)
    assert out_apply["mode"] == "apply"
    assert out_apply["new"] == out_dry["new"]
    assert out_apply["skip"] == 0
    rows = pdb.list_permissions()
    assert len(rows) == out_apply["new"]


def test_migration_script_idempotent(monkeypatch, tmp_path):
    import core.auth.permissions_db as pdb
    from scripts import migrate_permissions_dict_to_db as mig

    db_path = tmp_path / "perm_mig_idem.db"
    monkeypatch.setattr(pdb, "PERMISSIONS_DB_PATH", db_path)

    first = mig.run(dry_run=False, apply=True)
    second = mig.run(dry_run=False, apply=True)
    assert second["new"] == 0
    assert second["skip"] == first["new"]


# ── change_request lifecycle (status transitions) ───────────────────────────


def test_change_request_status_transitions(temp_permissions_db):
    """pending → security_approved → executive_approved → applied."""
    pdb = temp_permissions_db
    rid = pdb.insert_change_request(
        permission_key="test.demo",
        requested_by="req-001",
        old_value=None,
        new_value=_sample_perm(),
        reason="for testing transitions",
    )
    assert isinstance(rid, int) and rid > 0

    r0 = pdb.get_change_request(rid)
    assert r0["status"] == "pending"
    assert r0["requested_by"] == "req-001"
    assert r0["reason"] == "for testing transitions"

    pdb.update_change_request_status(rid, "security_approved", security_approver="sec-1")
    r1 = pdb.get_change_request(rid)
    assert r1["status"] == "security_approved"
    assert r1["security_approver"] == "sec-1"

    pdb.update_change_request_status(rid, "executive_approved", executive_approver="exec-1")
    r2 = pdb.get_change_request(rid)
    assert r2["status"] == "executive_approved"
    assert r2["executive_approver"] == "exec-1"

    pdb.update_change_request_status(rid, "applied", applied_at="2026-01-01T00:00:00+00:00")
    r3 = pdb.get_change_request(rid)
    assert r3["status"] == "applied"
    assert r3["applied_at"] == "2026-01-01T00:00:00+00:00"


def test_list_change_requests_by_status(temp_permissions_db):
    pdb = temp_permissions_db
    rid_a = pdb.insert_change_request("k.a", "req", None, _sample_perm("k.a"), "ra")
    rid_b = pdb.insert_change_request("k.b", "req", None, _sample_perm("k.b"), "rb")
    pdb.update_change_request_status(rid_a, "security_approved", security_approver="s")

    pending = pdb.list_change_requests(status_filter="pending")
    assert {r["request_id"] for r in pending} == {rid_b}

    sec = pdb.list_change_requests(status_filter="security_approved")
    assert {r["request_id"] for r in sec} == {rid_a}

    all_r = pdb.list_change_requests()
    assert {r["request_id"] for r in all_r} == {rid_a, rid_b}
