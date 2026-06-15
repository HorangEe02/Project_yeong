"""Feature D legal-review guardrail tests."""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace


def _client(monkeypatch, tmp_path, user):
    """Create a compliance router test client with isolated change storage."""

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.dependencies import get_current_user
    from backend.routers import compliance
    import features.compliance.change_detector as change_detector

    monkeypatch.setattr(change_detector, "CHANGE_DB_PATH", str(tmp_path / "changes.db"))
    app = FastAPI()
    app.include_router(compliance.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False), change_detector


def _user(level: int, role: str, user_id: str):
    """Build a minimal user context."""

    return SimpleNamespace(
        employee_id=user_id,
        user_id=user_id,
        username=user_id,
        email=f"{user_id}@example.invalid",
        role=role,
        role_level=level,
    )


def _seed_change(change_detector, *, audit_trail: list[dict] | None = None) -> int:
    """Insert a high-risk legal change row."""

    change_detector.init_change_db()
    conn = sqlite3.connect(change_detector.CHANGE_DB_PATH)
    try:
        cur = conn.execute(
            """INSERT INTO regulation_changes(
                   detected_at, regulation_type, change_type, item_id, item_title,
                   old_value, new_value, severity, status, audit_trail, summary_ko,
                   grade, affected_departments, affected_plants, legal_class,
                   penalty_severity_krw_mn
               ) VALUES (
                   '2026-05-21T00:00:00', 'domestic_law', 'modified', 'LAW-1',
                   '고위험 법규', 'old', 'new', 'critical', 'pending', ?,
                   '요약', 'HIGH', '[]', '[]', ?, 100
               )""",
            (
                json.dumps(audit_trail or [], ensure_ascii=False),
                json.dumps(["administrative"], ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def test_high_risk_final_transition_requires_independent_review(monkeypatch, tmp_path) -> None:
    """L4 users cannot finalize high-risk changes without independent review."""

    client, change_detector = _client(monkeypatch, tmp_path, _user(4, "HR_ADMIN", "legal-1"))
    change_id = _seed_change(change_detector)

    res = client.post(
        f"/api/compliance/changes/{change_id}/transition",
        json={"new_status": "announced"},
    )

    assert res.status_code == 409
    assert res.json()["detail"] == "legal_review_required"


def test_high_risk_final_transition_accepts_independent_review(monkeypatch, tmp_path) -> None:
    """A different reviewer in audit trail satisfies the human-review gate."""

    client, change_detector = _client(monkeypatch, tmp_path, _user(4, "HR_ADMIN", "legal-1"))
    change_id = _seed_change(
        change_detector,
        audit_trail=[{"action": "transition", "to": "reviewing", "user": "reviewer-2"}],
    )

    res = client.post(
        f"/api/compliance/changes/{change_id}/transition",
        json={"new_status": "announced"},
    )

    assert res.status_code == 200
    assert res.json()["review_required"] is True
    assert res.json()["override_used"] is False


def test_l5_override_requires_and_records_reason(monkeypatch, tmp_path) -> None:
    """L5 override is allowed only with an auditable reason."""

    client, change_detector = _client(monkeypatch, tmp_path, _user(5, "SYS_ADMIN", "admin-1"))
    change_id = _seed_change(change_detector)

    missing_reason = client.post(
        f"/api/compliance/changes/{change_id}/transition",
        json={"new_status": "done"},
    )
    assert missing_reason.status_code == 409
    assert missing_reason.json()["detail"] == "override_reason_required"

    ok = client.post(
        f"/api/compliance/changes/{change_id}/transition",
        json={"new_status": "done", "override_reason": "긴급 고객 감사 대응"},
    )
    assert ok.status_code == 200
    assert ok.json()["override_used"] is True

    conn = sqlite3.connect(change_detector.CHANGE_DB_PATH)
    try:
        row = conn.execute(
            "SELECT audit_trail FROM regulation_changes WHERE id = ?",
            (change_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    trail = json.loads(row[0])
    assert any(item.get("action") == "legal_admin_override" for item in trail)


def test_legal_disclaimer_is_wired_into_digest_and_verifier() -> None:
    """Digest/report guardrails should use the canonical legal disclaimer."""

    import scripts.verify_feature_d_release as verifier
    from backend.services.notify.dispatcher import _build_digest_text
    from features.compliance.alerts.legal_guard import COMPLIANCE_AI_DISCLAIMER
    from features.compliance.learning.exec_report import _AJIN_BRAND

    _, digest = _build_digest_text([])
    assert COMPLIANCE_AI_DISCLAIMER in digest
    assert _AJIN_BRAND["disclaimer"] == COMPLIANCE_AI_DISCLAIMER
    assert verifier.verify_legal_guardrail_policy(verifier.FeatureDConfig()).status == "pass"
