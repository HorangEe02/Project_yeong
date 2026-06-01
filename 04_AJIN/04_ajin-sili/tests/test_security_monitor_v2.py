"""tests/test_security_monitor_v2.py — PR-E5.

신규 4 이상 패턴 + 7-패턴 통합 anomaly feed + 5-차원 dashboard 검증.

audit.db / auth.db 는 tmp_path 에 격리 생성 후 monkeypatch 로 모듈 경로 치환.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────
# Fixture: tmp audit.db + auth.db
# ─────────────────────────────────────────────────────────

def _make_audit_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
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
    conn.commit()
    conn.close()


def _make_auth_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE roles (
            role_id INTEGER PRIMARY KEY,
            role_name TEXT,
            role_level INTEGER
        );
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE,
            username TEXT,
            role_id INTEGER,
            is_active INTEGER DEFAULT 1
        );
        INSERT INTO roles (role_id, role_name, role_level) VALUES
            (1, 'EMPLOYEE', 1),
            (4, 'HR_ADMIN', 4),
            (5, 'SYS_ADMIN', 5);
    """)
    conn.commit()
    conn.close()


def _insert_audit(db: Path, rows: list[tuple]) -> None:
    conn = sqlite3.connect(str(db))
    conn.executemany(
        "INSERT INTO api_audit_log "
        "(employee_id, name, department, role, endpoint, method, status_code, detail, ip_address, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def _insert_user(db: Path, employee_id: str, username: str, role_id: int, is_active: int = 1) -> None:
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO users (employee_id, username, role_id, is_active) VALUES (?, ?, ?, ?)",
        (employee_id, username, role_id, is_active),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def isolated_dbs(tmp_path: Path, monkeypatch):
    """audit.db + auth.db 를 tmp 에 만들고 security_monitor 의 경로 상수를 치환."""
    audit_db = tmp_path / "audit.db"
    auth_db = tmp_path / "auth.db"
    _make_audit_db(audit_db)
    _make_auth_db(auth_db)

    from features.admin import security_monitor as sm
    monkeypatch.setattr(sm, "AUDIT_DB", str(audit_db))
    monkeypatch.setattr(sm, "AUTH_DB", str(auth_db))
    return audit_db, auth_db


# ─────────────────────────────────────────────────────────
# K6 — privilege_escalation
# ─────────────────────────────────────────────────────────

def test_detect_privilege_escalation(isolated_dbs):
    audit_db, auth_db = isolated_dbs
    # role_level=1 (EMPLOYEE) 사용자가 /api/admin/* 5회 시도
    _insert_user(auth_db, "EMP-001", "Junior Lee", role_id=1)
    _insert_user(auth_db, "HR-001", "HR Admin", role_id=4)
    now = datetime.now()
    rows = []
    for i in range(5):
        rows.append((
            "EMP-001", "Junior Lee", "IT전략팀", "EMPLOYEE",
            "/api/admin/users", "GET", 403, "denied", "10.0.0.1",
            (now - timedelta(minutes=i * 5)).isoformat(),
        ))
    # HR_ADMIN(L4) 의 정상 /admin/* 접근은 제외돼야 함
    rows.append((
        "HR-001", "HR Admin", "총무인사팀", "HR_ADMIN",
        "/api/admin/users", "GET", 200, "ok", "10.0.0.2",
        now.isoformat(),
    ))
    _insert_audit(audit_db, rows)

    from features.admin.security_monitor import detect_privilege_escalation
    out = detect_privilege_escalation(window_hours=24)
    assert len(out) == 1
    assert out[0]["employee_id"] == "EMP-001"
    assert out[0]["attempts"] == 5
    assert out[0]["role_level"] == 1
    assert out[0]["blocked"] is True


# ─────────────────────────────────────────────────────────
# K7 — mass_export
# ─────────────────────────────────────────────────────────

def test_detect_mass_export(isolated_dbs):
    audit_db, _ = isolated_dbs
    now = datetime.now()
    rows = []
    for i in range(25):
        rows.append((
            "EMP-002", "Big Downloader", "재무팀", "EMPLOYEE",
            f"/api/download/file_{i}", "GET", 200, "", "10.0.0.3",
            (now - timedelta(minutes=i)).isoformat(),
        ))
    # noise: 다른 사용자 5건
    for i in range(5):
        rows.append((
            "EMP-003", "Normal User", "재무팀", "EMPLOYEE",
            "/api/download/x", "GET", 200, "", "10.0.0.4",
            (now - timedelta(minutes=i)).isoformat(),
        ))
    _insert_audit(audit_db, rows)

    from features.admin.security_monitor import detect_mass_export
    out = detect_mass_export(window_hours=1, threshold=20)
    assert len(out) == 1
    assert out[0]["employee_id"] == "EMP-002"
    assert out[0]["download_count"] == 25


# ─────────────────────────────────────────────────────────
# K8 — off_hours_export
# ─────────────────────────────────────────────────────────

def test_off_hours_export(isolated_dbs):
    audit_db, _ = isolated_dbs
    today = datetime.now().date()
    # 23:00 메일 발송 (off-hours)
    ts_offhours = datetime.combine(today, datetime.min.time()).replace(hour=23, minute=15).isoformat()
    # 14:00 메일 발송 (정상 시간)
    ts_normal = datetime.combine(today, datetime.min.time()).replace(hour=14, minute=0).isoformat()
    rows = [
        ("EMP-004", "Late Mailer", "법무팀", "EMPLOYEE",
         "/api/draft/send", "POST", 200, "", "10.0.0.5", ts_offhours),
        ("EMP-005", "Normal Mailer", "법무팀", "EMPLOYEE",
         "/api/draft/send", "POST", 200, "", "10.0.0.6", ts_normal),
    ]
    _insert_audit(audit_db, rows)

    from features.admin.security_monitor import detect_off_hours_export
    out = detect_off_hours_export(off_hours=("22:00", "06:00"), window_hours=48)
    # 23:00 이벤트만 캡처
    assert len(out) == 1
    assert out[0]["employee_id"] == "EMP-004"
    assert out[0]["hour"] == 23
    assert out[0]["action"] == "mail_send"


# ─────────────────────────────────────────────────────────
# K9 — deprecated_account_active
# ─────────────────────────────────────────────────────────

def test_deprecated_account_active(isolated_dbs):
    audit_db, auth_db = isolated_dbs
    # is_active=0 사용자
    _insert_user(auth_db, "EMP-RETIRED", "Old Timer", role_id=1, is_active=0)
    _insert_user(auth_db, "EMP-ACTIVE", "Current User", role_id=1, is_active=1)
    now = datetime.now()
    rows = [
        ("EMP-RETIRED", "Old Timer", "공정팀", "EMPLOYEE",
         "/api/employee", "GET", 200, "", "10.0.0.7",
         (now - timedelta(minutes=10)).isoformat()),
        ("EMP-ACTIVE", "Current User", "공정팀", "EMPLOYEE",
         "/api/employee", "GET", 200, "", "10.0.0.8",
         (now - timedelta(minutes=5)).isoformat()),
    ]
    _insert_audit(audit_db, rows)

    from features.admin.security_monitor import detect_deprecated_account_active
    out = detect_deprecated_account_active(grace_days=7, window_hours=24)
    assert len(out) == 1
    assert out[0]["employee_id"] == "EMP-RETIRED"
    assert out[0]["username"] == "Old Timer"


# ─────────────────────────────────────────────────────────
# 통합 anomaly feed (7 패턴)
# ─────────────────────────────────────────────────────────

def test_anomaly_feed_integration(isolated_dbs):
    audit_db, auth_db = isolated_dbs
    # privilege_escalation seed
    _insert_user(auth_db, "EMP-PE", "PE User", role_id=1)
    # mass_export seed
    _insert_user(auth_db, "EMP-ME", "ME User", role_id=1)
    # deprecated seed
    _insert_user(auth_db, "EMP-DEP", "Dep User", role_id=1, is_active=0)
    now = datetime.now()
    rows = []
    # PE: 4건 /admin/*
    for i in range(4):
        rows.append(("EMP-PE", "PE User", "", "EMPLOYEE",
                     "/api/admin/users", "GET", 403, "", "10.0.0.10",
                     (now - timedelta(minutes=i)).isoformat()))
    # ME: 22건 download
    for i in range(22):
        rows.append(("EMP-ME", "ME User", "", "EMPLOYEE",
                     "/api/download/x", "GET", 200, "", "10.0.0.11",
                     (now - timedelta(minutes=i)).isoformat()))
    # off-hours export
    ts_offhours = datetime.combine(now.date(), datetime.min.time()).replace(hour=2).isoformat()
    rows.append(("EMP-OFF", "Off User", "", "EMPLOYEE",
                 "/api/draft/send", "POST", 200, "", "10.0.0.12", ts_offhours))
    # deprecated active
    rows.append(("EMP-DEP", "Dep User", "", "EMPLOYEE",
                 "/api/employee", "GET", 200, "", "10.0.0.13",
                 (now - timedelta(minutes=2)).isoformat()))
    _insert_audit(audit_db, rows)

    from features.admin.security_monitor import build_anomaly_feed
    feed = build_anomaly_feed(window_hours=24)
    patterns = {item["pattern"] for item in feed}
    assert "privilege_escalation" in patterns
    assert "mass_export" in patterns
    assert "deprecated_account_active" in patterns
    # off_hours_export 도 포함 (오전 2시)
    assert "off_hours_export" in patterns

    # severity DESC 정렬 검증: CRITICAL → HIGH → MEDIUM → LOW
    rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    severities = [rank[i["severity"]] for i in feed]
    assert severities == sorted(severities), f"feed must be sorted by severity, got {severities}"


def test_anomaly_feed_empty_state(isolated_dbs):
    """audit.db / auth.db 가 비어있어도 정상 동작 (빈 배열 반환)."""
    from features.admin.security_monitor import (
        build_anomaly_feed,
        detect_privilege_escalation,
        detect_mass_export,
        detect_off_hours_export,
        detect_deprecated_account_active,
    )
    assert detect_privilege_escalation(window_hours=24) == []
    assert detect_mass_export(window_hours=1, threshold=20) == []
    assert detect_off_hours_export(window_hours=24) == []
    assert detect_deprecated_account_active(window_hours=24) == []
    assert build_anomaly_feed(window_hours=24) == []


# ─────────────────────────────────────────────────────────
# 5-차원 dashboard
# ─────────────────────────────────────────────────────────

def test_dashboard_5_dimensions(isolated_dbs):
    audit_db, auth_db = isolated_dbs
    now = datetime.now()
    rows = [
        # permission violation
        ("EMP-X", "X", "재무팀", "EMPLOYEE",
         "/api/admin/users", "GET", 403, "denied", "10.0.0.20",
         (now - timedelta(minutes=10)).isoformat()),
        # change audit (PUT)
        ("HR-A", "HR A", "총무인사팀", "HR_ADMIN",
         "/api/admin/users/EMP-1", "PUT", 200, "username", "10.0.0.21",
         (now - timedelta(minutes=20)).isoformat()),
        # change audit (bulk-role)
        ("HR-A", "HR A", "총무인사팀", "HR_ADMIN",
         "/api/admin/users/bulk-role", "POST", 200, "target=L4", "10.0.0.21",
         (now - timedelta(minutes=30)).isoformat()),
        # time_pattern source
        ("EMP-T", "T", "IT전략팀", "EMPLOYEE",
         "/api/search", "POST", 200, "", "10.0.0.22",
         (now - timedelta(minutes=5)).isoformat()),
    ]
    _insert_audit(audit_db, rows)

    from features.admin.security_monitor import build_dashboard
    dash = build_dashboard(period="week")
    assert dash["period"] == "week"
    assert "time_pattern" in dash
    assert "anomalies" in dash
    assert "permission_violations" in dash
    assert "feature_usage" in dash
    assert "change_audit" in dash

    # permission_violations 1건 (403)
    assert len(dash["permission_violations"]) == 1
    assert dash["permission_violations"][0]["status_code"] == 403

    # change_audit: PUT + bulk-role = 2건
    assert len(dash["change_audit"]) == 2
    actions = {r["action"] for r in dash["change_audit"]}
    assert "put" in actions or "role_change" in actions

    # time_pattern: 4개 row → 최소 1개 bucket
    assert len(dash["time_pattern"]) >= 1

    # feature_usage: A~F 6개 키 항상 존재
    assert len(dash["feature_usage"]) == 6
