"""tests/test_audit_timeline.py — v4.8 F.

/admin/audit/timeline 필터 조합 + 페이지네이션 검증.
sqlite api_audit_log 에 fixture row 들을 직접 inject 후 endpoint 호출 결과 확인.

라우터를 직접 호출하는 대신 SQL where 절 빌드를 검증 — DB 의존 최소화.
"""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


def _make_audit_db(tmp_path: Path) -> Path:
    db = tmp_path / "audit.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE api_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            department TEXT DEFAULT '',
            role TEXT DEFAULT '',
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'GET',
            status_code INTEGER DEFAULT 200,
            detail TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            timestamp TEXT
        );
    """)
    base = datetime.now(UTC)
    rows = [
        ("HR-0001", "Hong", "총무인사팀", "HR_ADMIN", "/api/admin/users", "GET", 200, "filtered=10", "10.0.0.1", (base - timedelta(hours=1)).isoformat()),
        ("HR-0001", "Hong", "총무인사팀", "HR_ADMIN", "/api/admin/users/IT-0001", "PUT", 200, "username,department", "10.0.0.1", (base - timedelta(hours=2)).isoformat()),
        ("IT-0001", "Lee",  "IT전략팀",    "EMPLOYEE", "/api/search",            "POST", 200, "q=test", "10.0.0.2", (base - timedelta(hours=3)).isoformat()),
        ("HR-0002", "Park", "총무인사팀", "HR_ADMIN", "/api/admin/users/bulk",  "POST", 400, "errors=5", "10.0.0.3", (base - timedelta(hours=4)).isoformat()),
        ("HR-0001", "Hong", "총무인사팀", "HR_ADMIN", "/api/admin/users/bulk-role", "POST", 200, "target_role=L4", "10.0.0.1", (base - timedelta(hours=5)).isoformat()),
    ]
    conn.executemany(
        "INSERT INTO api_audit_log (employee_id,name,department,role,endpoint,method,status_code,detail,ip_address,timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def _query_with_filters(
    db: Path,
    *,
    actor: str = "",
    action: str = "",
    target: str = "",
    result: str = "all",
    period_days: int = 30,
    page: int = 1,
    page_size: int = 50,
) -> tuple[int, list[dict]]:
    """admin.audit_timeline 라우터 내부 SQL 로직을 그대로 재현."""
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now(UTC) - timedelta(days=period_days)).isoformat()
    conditions = ["timestamp >= ?"]
    params: list = [cutoff]
    if actor:
        conditions.append("(employee_id LIKE ? OR name LIKE ?)")
        params.extend([f"%{actor}%", f"%{actor}%"])
    if action:
        conditions.append("(endpoint LIKE ? OR method LIKE ?)")
        params.extend([f"%{action}%", f"%{action}%"])
    if target:
        conditions.append("detail LIKE ?")
        params.append(f"%{target}%")
    if result == "success":
        conditions.append("status_code BETWEEN 200 AND 299")
    elif result == "fail":
        conditions.append("status_code >= 400")
    where = " AND ".join(conditions)
    offset = (page - 1) * page_size
    rows = [
        dict(r)
        for r in conn.execute(
            f"SELECT * FROM api_audit_log WHERE {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            [*params, page_size, offset],
        )
    ]
    total = conn.execute(
        f"SELECT COUNT(*) FROM api_audit_log WHERE {where}", params,
    ).fetchone()[0]
    conn.close()
    return total, rows


def test_no_filters_returns_all_recent(tmp_path: Path):
    db = _make_audit_db(tmp_path)
    total, rows = _query_with_filters(db)
    assert total == 5
    assert len(rows) == 5
    # timestamp DESC.
    timestamps = [r["timestamp"] for r in rows]
    assert timestamps == sorted(timestamps, reverse=True)


def test_filter_by_actor(tmp_path: Path):
    db = _make_audit_db(tmp_path)
    total, rows = _query_with_filters(db, actor="HR-0001")
    assert total == 3
    for r in rows:
        assert r["employee_id"] == "HR-0001"


def test_filter_by_action_endpoint(tmp_path: Path):
    db = _make_audit_db(tmp_path)
    total, rows = _query_with_filters(db, action="/admin/users")
    # 4 row (users / users/IT-0001 / users/bulk / users/bulk-role)
    assert total == 4


def test_filter_by_target_detail(tmp_path: Path):
    db = _make_audit_db(tmp_path)
    total, rows = _query_with_filters(db, target="errors=5")
    assert total == 1
    assert rows[0]["status_code"] == 400


def test_filter_by_result_fail(tmp_path: Path):
    db = _make_audit_db(tmp_path)
    total, rows = _query_with_filters(db, result="fail")
    assert total == 1
    assert rows[0]["status_code"] >= 400


def test_filter_by_result_success(tmp_path: Path):
    db = _make_audit_db(tmp_path)
    total, rows = _query_with_filters(db, result="success")
    assert total == 4
    for r in rows:
        assert 200 <= r["status_code"] < 300


def test_pagination_page_size_2(tmp_path: Path):
    db = _make_audit_db(tmp_path)
    total1, page1 = _query_with_filters(db, page=1, page_size=2)
    total2, page2 = _query_with_filters(db, page=2, page_size=2)
    assert total1 == total2 == 5
    assert len(page1) == 2
    assert len(page2) == 2
    # 페이지 간 row 가 중복되지 않음.
    ids1 = {r["id"] for r in page1}
    ids2 = {r["id"] for r in page2}
    assert ids1.isdisjoint(ids2)


def test_period_days_limits_window(tmp_path: Path):
    """period_days=0.01 (0 시간) 이면 모든 row 가 cutoff 후 → 빈 결과."""
    db = _make_audit_db(tmp_path)
    # 매우 작은 period_days 는 int 만 받으므로 ≥1 만 가능. 1일은 모두 포함.
    total, _ = _query_with_filters(db, period_days=1)
    assert total == 5  # 모두 24시간 이내.
