"""Feature D RBAC tests for D1 mutation endpoints."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace


def _client(monkeypatch, tmp_path, user):
    """Create a compliance router test client with isolated auth and DB."""

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.dependencies import get_current_user
    from backend.routers import compliance
    import features.compliance.change_detector as change_detector

    monkeypatch.setattr(change_detector, "CHANGE_DB_PATH", str(tmp_path / "changes.db"))
    app = FastAPI()
    app.include_router(compliance.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False), compliance, change_detector


def _user(level: int, role: str = "EMPLOYEE", user_id: str = "u1"):
    """Build a minimal user context for RBAC dependency tests."""

    return SimpleNamespace(
        employee_id=user_id,
        user_id=user_id,
        username=user_id,
        email=f"{user_id}@example.invalid",
        role=role,
        role_level=level,
    )


def _seed_change(change_detector, *, grade: str = "LOW", legal_class: str = "[]") -> int:
    """Insert one regulation change row into the isolated SQLite DB."""

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
                   '테스트 법규', 'old', 'new', 'warning', 'pending', '[]',
                   '요약', ?, '[]', '[]', ?, 0
               )""",
            (grade, legal_class),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def test_l1_cannot_run_d1_mutations(monkeypatch, tmp_path) -> None:
    """L1 users can read D1 but cannot run crawler or transition mutations."""

    client, _, _ = _client(monkeypatch, tmp_path, _user(1, "EMPLOYEE", "l1"))

    assert client.post("/api/compliance/crawl/run-all").status_code == 403
    assert client.post(
        "/api/compliance/changes/1/transition",
        json={"new_status": "reviewing"},
    ).status_code == 403


def test_l3_can_run_crawler_mutation(monkeypatch, tmp_path) -> None:
    """L3 users can trigger D1 crawler operations."""

    from backend.schemas.compliance import CrawlRunResponse

    client, compliance, _ = _client(monkeypatch, tmp_path, _user(3, "TEAM_LEAD", "l3"))

    async def fake_run_one(name: str, trigger_source: str = "api", user_id: str = ""):
        return CrawlRunResponse(name=name, source_type="live", crawled_at="2026-05-21T00:00:00")

    monkeypatch.setattr(compliance, "_run_one_crawler", fake_run_one)

    res = client.post("/api/compliance/crawl/run-all")

    assert res.status_code == 200
    assert sorted(res.json()["crawlers"]) == sorted(compliance._CRAWLER_KEYS)


def test_l3_cannot_set_final_change_status(monkeypatch, tmp_path) -> None:
    """Final legal workflow states require L4 even for low-risk changes."""

    client, _, change_detector = _client(monkeypatch, tmp_path, _user(3, "TEAM_LEAD", "l3"))
    change_id = _seed_change(change_detector, grade="LOW")

    res = client.post(
        f"/api/compliance/changes/{change_id}/transition",
        json={"new_status": "done"},
    )

    assert res.status_code == 403
    assert res.json()["detail"] == "legal_final_status_requires_l4"
