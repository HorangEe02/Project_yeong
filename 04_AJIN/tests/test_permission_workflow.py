"""v4.7 PR-E7 — 2단계 결재 워크플로우 검증."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def isolated_workflow(tmp_path, monkeypatch):
    """permissions_db 의 DB 를 tmp 로 격리. workflow + db 모두 영향."""
    import core.auth.permissions_db as pdb
    db_path = tmp_path / "permissions.db"
    monkeypatch.setattr(pdb, "PERMISSIONS_DB_PATH", db_path)
    pdb.init_permissions_db()

    from features.admin import permission_workflow as wf
    return wf, pdb


def _new_value(min_role: str = "MANAGER") -> dict:
    return {
        "key": "test.new_perm",
        "description": "테스트용 신규 권한",
        "min_role": min_role,
        "departments": ["품질보증팀"],
        "allow_same_division": False,
        "min_position_level": 0,
    }


# ── 요청 생성 ───────────────────────────────────────────────────────────────


def test_create_change_request_basic(isolated_workflow):
    wf, _ = isolated_workflow
    rid = wf.create_change_request(
        permission_key="test.new_perm",
        new_value=_new_value(),
        reason="신규 권한 추가",
        actor="emp-001",
    )
    assert isinstance(rid, int) and rid > 0


def test_create_change_request_requires_reason(isolated_workflow):
    wf, _ = isolated_workflow
    with pytest.raises(wf.WorkflowError):
        wf.create_change_request(
            permission_key="test.new_perm",
            new_value=_new_value(),
            reason="",
            actor="emp-001",
        )


# ── 승인 단계 ───────────────────────────────────────────────────────────────


def test_security_approval_changes_status(isolated_workflow):
    wf, pdb = isolated_workflow
    rid = wf.create_change_request("test.new_perm", _new_value(), "reason", "req")
    out = wf.approve_by_security(rid, approver="sec-1")
    assert out["status"] == wf.STATUS_SECURITY_APPROVED
    assert out["security_approver"] == "sec-1"

    # audit 기록
    audit = pdb.list_audit(permission_key="test.new_perm")
    assert any(a["action"] == "approve_security" for a in audit)


def test_executive_approval_applies_permission(isolated_workflow):
    wf, pdb = isolated_workflow
    rid = wf.create_change_request("test.new_perm", _new_value("TEAM_LEAD"), "r", "req")
    wf.approve_by_security(rid, approver="sec-1")
    out = wf.approve_by_executive(rid, approver="exec-1")

    # status applied
    assert out["status"] == wf.STATUS_APPLIED
    assert out["executive_approver"] == "exec-1"
    assert out["applied_at"]

    # permissions table UPDATE 확인
    p = pdb.get_permission("test.new_perm")
    assert p is not None
    assert p["min_role"] == "TEAM_LEAD"
    assert p["departments"] == {"품질보증팀"}
    assert p["updated_by"] == "exec-1"

    # audit 기록: request_create, approve_security, approve_executive, create(perm), apply
    audit = pdb.list_audit(permission_key="test.new_perm")
    actions = {a["action"] for a in audit}
    assert {"request_create", "approve_security", "approve_executive", "create", "apply"} <= actions


def test_executive_cannot_approve_before_security(isolated_workflow):
    wf, _ = isolated_workflow
    rid = wf.create_change_request("test.new_perm", _new_value(), "r", "req")
    with pytest.raises(wf.WorkflowError):
        wf.approve_by_executive(rid, approver="exec-1")


def test_security_cannot_approve_twice(isolated_workflow):
    wf, _ = isolated_workflow
    rid = wf.create_change_request("test.new_perm", _new_value(), "r", "req")
    wf.approve_by_security(rid, approver="sec-1")
    with pytest.raises(wf.WorkflowError):
        wf.approve_by_security(rid, approver="sec-2")


# ── 반려 ────────────────────────────────────────────────────────────────────


def test_rejection_at_security_stage(isolated_workflow):
    wf, pdb = isolated_workflow
    rid = wf.create_change_request("test.new_perm", _new_value(), "r", "req")
    out = wf.reject(rid, approver="sec-1", reason="규정 미달")
    assert out["status"] == wf.STATUS_REJECTED

    # permissions table 미적용
    assert pdb.get_permission("test.new_perm") is None

    audit = pdb.list_audit(permission_key="test.new_perm")
    reject_audit = next(a for a in audit if a["action"] == "reject")
    assert reject_audit["diff"]["stage"] == "pending"


def test_rejection_at_executive_stage(isolated_workflow):
    wf, pdb = isolated_workflow
    rid = wf.create_change_request("test.new_perm", _new_value(), "r", "req")
    wf.approve_by_security(rid, approver="sec-1")
    out = wf.reject(rid, approver="exec-1", reason="비즈니스 영향 큼")
    assert out["status"] == wf.STATUS_REJECTED
    assert pdb.get_permission("test.new_perm") is None

    audit = pdb.list_audit(permission_key="test.new_perm")
    reject_audit = next(a for a in audit if a["action"] == "reject")
    assert reject_audit["diff"]["stage"] == "security_approved"


def test_reject_requires_reason(isolated_workflow):
    wf, _ = isolated_workflow
    rid = wf.create_change_request("test.new_perm", _new_value(), "r", "req")
    with pytest.raises(wf.WorkflowError):
        wf.reject(rid, approver="sec-1", reason="")


def test_reject_terminal_request_fails(isolated_workflow):
    wf, _ = isolated_workflow
    rid = wf.create_change_request("test.new_perm", _new_value(), "r", "req")
    wf.approve_by_security(rid, approver="sec-1")
    wf.approve_by_executive(rid, approver="exec-1")
    with pytest.raises(wf.WorkflowError):
        wf.reject(rid, approver="sec-1", reason="이미 적용됨")


# ── escalation ──────────────────────────────────────────────────────────────


def test_escalate_overdue_24h(isolated_workflow):
    wf, pdb = isolated_workflow
    rid = wf.create_change_request("test.new_perm", _new_value(), "r", "req")

    # requested_at 을 25시간 전으로 backdate (직접 DB 조작).
    import sqlite3
    backdated = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    conn = sqlite3.connect(str(pdb.PERMISSIONS_DB_PATH))
    conn.execute(
        "UPDATE permission_change_requests SET requested_at=? WHERE request_id=?",
        (backdated, rid),
    )
    conn.commit()
    conn.close()

    overdue = wf.escalate_overdue(threshold_hours=24)
    assert len(overdue) == 1
    assert overdue[0]["request_id"] == rid
    assert overdue[0]["hours_pending"] >= 24


def test_escalate_no_overdue_returns_empty(isolated_workflow):
    wf, _ = isolated_workflow
    # 방금 만든 요청은 24h 안 됨
    wf.create_change_request("test.new_perm", _new_value(), "r", "req")
    assert wf.escalate_overdue(threshold_hours=24) == []


# ── 조회 ────────────────────────────────────────────────────────────────────


def test_queue_filter_by_status(isolated_workflow):
    wf, _ = isolated_workflow
    rid_a = wf.create_change_request("k.a", _new_value(), "r", "req")
    rid_b = wf.create_change_request("k.b", _new_value(), "r", "req")
    wf.approve_by_security(rid_a, approver="sec-1")

    pending = wf.get_queue(status_filter=wf.STATUS_PENDING)
    assert [r["request_id"] for r in pending] == [rid_b]

    sec = wf.get_queue(status_filter=wf.STATUS_SECURITY_APPROVED)
    assert [r["request_id"] for r in sec] == [rid_a]


def test_history_includes_applied_and_rejected(isolated_workflow):
    wf, _ = isolated_workflow
    rid_a = wf.create_change_request("k.a", _new_value(), "r1", "req")
    rid_b = wf.create_change_request("k.b", _new_value(), "r2", "req")
    rid_c = wf.create_change_request("k.c", _new_value(), "r3", "req")

    # a: applied
    wf.approve_by_security(rid_a, approver="sec")
    wf.approve_by_executive(rid_a, approver="exec")
    # b: rejected
    wf.reject(rid_b, approver="sec", reason="reject reason")
    # c: still pending (history 에서 제외)

    history = wf.get_history(limit=50)
    rids = {r["request_id"] for r in history}
    assert rids == {rid_a, rid_b}
    assert rid_c not in rids


def test_audit_log_records_all_transitions(isolated_workflow):
    wf, pdb = isolated_workflow
    rid = wf.create_change_request("test.new_perm", _new_value(), "r", "req")
    wf.approve_by_security(rid, approver="sec")
    wf.approve_by_executive(rid, approver="exec")

    audit = pdb.list_audit(permission_key="test.new_perm")
    actions = [a["action"] for a in audit]
    assert "request_create" in actions
    assert "approve_security" in actions
    assert "approve_executive" in actions
    assert "create" in actions  # upsert_permission 이 기록
    assert "apply" in actions


def test_invalid_request_id_raises(isolated_workflow):
    wf, _ = isolated_workflow
    with pytest.raises(wf.WorkflowError):
        wf.approve_by_security(99999, approver="sec")
