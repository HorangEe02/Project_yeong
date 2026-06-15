"""
보안 모니터링 + 이상 접근 감지
- 로그인 실패 패턴 분석 (무차별 대입)
- 비정상 시간대 접근 감지 (22시~06시)
- 비활성 계정 접근 시도 감지
- 로그인 통계 + 감사 로그 요약
"""

import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from core.data_lineage import should_include_non_real_data

AUTH_DB = "data/auth.db"
AUDIT_DB = "data/audit.db"


@dataclass
class SecurityAlert:
    """보안 알림"""
    alert_type: str         # brute_force / unusual_hour / inactive_access
    severity: str           # critical / warning / info
    title: str
    description: str
    employee_id: str = ""
    timestamp: str = ""
    details: Dict = field(default_factory=dict)


def _has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    """Return whether a SQLite table has a column.

    Args:
        conn: Open SQLite connection.
        table_name: Table to inspect.
        column_name: Column name to check.

    Returns:
        True when the column exists.
    """
    try:
        return column_name in {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    except Exception:
        return False


def _login_real_filter(conn: sqlite3.Connection, alias: str = "") -> str:
    """Build the login_history real-data predicate for analytics.

    Args:
        conn: Open auth.db connection.
        alias: Optional table alias.

    Returns:
        SQL predicate. Missing lineage columns fall back to ``1=1``.
    """
    if should_include_non_real_data() or not _has_column(conn, "login_history", "data_class"):
        return "1=1"
    prefix = f"{alias}." if alias else ""
    return f"{prefix}data_class = 'real'"


def detect_anomalies(hours: int = 24) -> List[SecurityAlert]:
    """최근 N시간 이상 접근 패턴 감지"""
    alerts = []
    alerts.extend(_detect_brute_force(hours))
    alerts.extend(_detect_unusual_hours(hours))
    alerts.extend(_detect_inactive_access(hours))

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 3))
    return alerts


def _detect_brute_force(hours: int) -> List[SecurityAlert]:
    """무차별 대입 시도 감지 (동일 계정 3회+ 실패)"""
    if not Path(AUTH_DB).exists():
        return []
    conn = sqlite3.connect(AUTH_DB)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    real_filter = _login_real_filter(conn)

    try:
        cursor = conn.execute(f"""
            SELECT employee_id, COUNT(*) as fail_count, MAX(timestamp) as last_attempt,
                   GROUP_CONCAT(DISTINCT ip_address) as ips
            FROM login_history
            WHERE success = 0 AND timestamp >= ? AND {real_filter}
            GROUP BY employee_id
            HAVING fail_count >= 3
            ORDER BY fail_count DESC
        """, (cutoff,))

        alerts = []
        for row in cursor.fetchall():
            emp_id, fail_count, last_time, ips = row
            severity = "critical" if fail_count >= 5 else "warning"
            ip_display = ips if ips and ips.strip() else "로컬"
            alerts.append(SecurityAlert(
                alert_type="brute_force", severity=severity,
                title=f"반복 로그인 실패: {emp_id}",
                description=f"{fail_count}회 실패 (IP: {ip_display})",
                employee_id=emp_id, timestamp=last_time or "",
                details={"fail_count": fail_count, "ips": ip_display},
            ))
    except Exception:
        alerts = []
    finally:
        conn.close()
    return alerts


def _detect_unusual_hours(hours: int) -> List[SecurityAlert]:
    """비정상 시간대 접근 감지 (22시~06시)"""
    if not Path(AUTH_DB).exists():
        return []
    conn = sqlite3.connect(AUTH_DB)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    real_filter = _login_real_filter(conn)

    try:
        cursor = conn.execute(f"""
            SELECT employee_id, timestamp, ip_address, success
            FROM login_history
            WHERE timestamp >= ?
              AND {real_filter}
              AND (CAST(substr(timestamp, 12, 2) AS INTEGER) >= 22
                   OR CAST(substr(timestamp, 12, 2) AS INTEGER) < 6)
            ORDER BY timestamp DESC
        """, (cutoff,))

        alerts = []
        for row in cursor.fetchall():
            emp_id, ts, ip, success = row
            ip_display = ip if ip and ip.strip() else "로컬"
            alerts.append(SecurityAlert(
                alert_type="unusual_hour", severity="warning",
                title=f"야간 접근: {emp_id}",
                description=f"{'성공' if success else '실패'} | {ts} | IP: {ip_display}",
                employee_id=emp_id, timestamp=ts or "",
                details={"ip": ip_display, "success": bool(success)},
            ))
    except Exception:
        alerts = []
    finally:
        conn.close()
    return alerts


def _detect_inactive_access(hours: int) -> List[SecurityAlert]:
    """비활성 계정 접근 시도 감지"""
    if not Path(AUTH_DB).exists():
        return []
    conn = sqlite3.connect(AUTH_DB)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    real_filter = _login_real_filter(conn, "lh")

    try:
        cursor = conn.execute(f"""
            SELECT lh.employee_id, lh.timestamp, lh.ip_address, u.username, u.is_active
            FROM login_history lh
            LEFT JOIN users u ON lh.employee_id = u.employee_id
            WHERE lh.timestamp >= ? AND u.is_active = 0 AND {real_filter}
            ORDER BY lh.timestamp DESC
        """, (cutoff,))

        alerts = []
        for row in cursor.fetchall():
            emp_id, ts, ip, name, is_active = row
            alerts.append(SecurityAlert(
                alert_type="inactive_access", severity="critical",
                title=f"비활성 계정 접근: {name or emp_id}",
                description=f"비활성 계정으로 로그인 시도 | IP: {ip or '로컬'}",
                employee_id=emp_id, timestamp=ts or "",
            ))
    except Exception:
        alerts = []
    finally:
        conn.close()
    return alerts


def get_login_stats(days: int = 30) -> Dict:
    """로그인 통계. Postgres audit 우선, 빈 결과면 legacy fallback."""
    try:
        from core.auth.postgres_audit import read_login_stats
        pg = read_login_stats(days)
        if pg["total"] > 0:
            return {
                "total_logins": pg["total"],
                "successful": pg["success"],
                "failed": pg["failed"],
                "success_rate": round(pg["success_rate"] * 100, 1),
                "unique_users": pg["unique_users"],
                "locked_accounts": 0,
            }
    except Exception:
        pass

    # Legacy Firestore fallback — 기본 비활성
    try:
        from core.auth.firestore_audit import read_login_stats
        fs = read_login_stats(days)
        if fs["total"] > 0:
            # locked_accounts 는 users 테이블 의존 → SQLite 에서 별도 조회
            locked = 0
            if Path(AUTH_DB).exists():
                try:
                    _c = sqlite3.connect(AUTH_DB)
                    locked = _c.execute(
                        "SELECT COUNT(*) FROM users WHERE locked_until IS NOT NULL AND locked_until > datetime('now')"
                    ).fetchone()[0]
                    _c.close()
                except Exception:
                    pass
            return {
                "total_logins": fs["total"],
                "successful": fs["success"],
                "failed": fs["failed"],
                "success_rate": round(fs["success_rate"] * 100, 1),
                "unique_users": fs["unique_users"],
                "locked_accounts": locked,
            }
    except Exception:
        pass

    if not Path(AUTH_DB).exists():
        return {"total_logins": 0, "successful": 0, "failed": 0, "success_rate": 0, "unique_users": 0, "locked_accounts": 0}

    conn = sqlite3.connect(AUTH_DB)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    real_filter = _login_real_filter(conn)

    total = conn.execute(f"SELECT COUNT(*) FROM login_history WHERE timestamp >= ? AND {real_filter}", (cutoff,)).fetchone()[0]
    success = conn.execute(f"SELECT COUNT(*) FROM login_history WHERE timestamp >= ? AND success=1 AND {real_filter}", (cutoff,)).fetchone()[0]
    unique = conn.execute(f"SELECT COUNT(DISTINCT employee_id) FROM login_history WHERE timestamp >= ? AND success=1 AND {real_filter}", (cutoff,)).fetchone()[0]

    try:
        locked = conn.execute("SELECT COUNT(*) FROM users WHERE locked_until IS NOT NULL AND locked_until > datetime('now')").fetchone()[0]
    except Exception:
        locked = 0

    conn.close()

    return {
        "total_logins": total,
        "successful": success,
        "failed": total - success,
        "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        "unique_users": unique,
        "locked_accounts": locked,
    }


def get_failed_login_trend(days: int = 30) -> List[Dict]:
    """일별 실패 로그인 추이"""
    if not Path(AUTH_DB).exists():
        return []
    conn = sqlite3.connect(AUTH_DB)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    real_filter = _login_real_filter(conn)

    try:
        cursor = conn.execute(f"""
            SELECT DATE(timestamp) as day,
                   SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                   SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fail
            FROM login_history WHERE timestamp >= ? AND {real_filter}
            GROUP BY DATE(timestamp) ORDER BY day
        """, (cutoff,))
        results = [{"date": r[0], "success": r[1], "failed": r[2]} for r in cursor.fetchall()]
    except Exception:
        results = []
    conn.close()
    return results


def get_login_hour_distribution(days: int = 30) -> List[Dict]:
    """시간대별 로그인 분포. Postgres audit 우선."""
    try:
        from core.auth.postgres_audit import read_hour_distribution
        pg = read_hour_distribution(days)
        if sum(pg.values()) > 0:
            return [{"hour": h, "count": pg.get(h, 0), "failed": 0} for h in range(24)]
    except Exception:
        pass

    # Legacy Firestore fallback (성공 로그인만 집계, SecurityTab UX 일관 유지)
    try:
        from core.auth.firestore_audit import read_hour_distribution
        fs = read_hour_distribution(days)
        if sum(fs.values()) > 0:
            return [{"hour": h, "count": fs.get(h, 0), "failed": 0} for h in range(24)]
    except Exception:
        pass

    if not Path(AUTH_DB).exists():
        return [{"hour": h, "count": 0, "failed": 0} for h in range(24)]

    conn = sqlite3.connect(AUTH_DB)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    hour_data = defaultdict(lambda: {"count": 0, "failed": 0})
    real_filter = _login_real_filter(conn)

    try:
        cursor = conn.execute(f"SELECT timestamp, success FROM login_history WHERE timestamp >= ? AND {real_filter}", (cutoff,))
        for row in cursor.fetchall():
            try:
                hour = int(row[0][11:13])
                hour_data[hour]["count"] += 1
                if not row[1]:
                    hour_data[hour]["failed"] += 1
            except (ValueError, IndexError):
                pass
    except Exception:
        pass
    conn.close()

    return [{"hour": h, "count": hour_data[h]["count"], "failed": hour_data[h]["failed"]} for h in range(24)]


def get_login_daily_counts(days: int = 30) -> List[Dict]:
    """일자별 로그인 시도 카운트 (v4.9 — SecurityTab 달력 히트맵용)."""
    if not Path(AUTH_DB).exists():
        return []

    conn = sqlite3.connect(AUTH_DB)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    daily = defaultdict(lambda: {"count": 0, "failed": 0})
    real_filter = _login_real_filter(conn)

    try:
        cursor = conn.execute(
            f"SELECT timestamp, success FROM login_history WHERE timestamp >= ? AND {real_filter}",
            (cutoff,),
        )
        for row in cursor.fetchall():
            try:
                d = row[0][:10]   # YYYY-MM-DD
                daily[d]["count"] += 1
                if not row[1]:
                    daily[d]["failed"] += 1
            except (ValueError, IndexError):
                pass
    except Exception:
        pass
    conn.close()

    # 정렬된 일자 리스트 반환
    return [
        {"date": d, "count": daily[d]["count"], "failed": daily[d]["failed"]}
        for d in sorted(daily.keys())
    ]


# ════════════════════════════════════════════════════════════════
# PR-E5 — 4 신규 이상 패턴 (audit.db 기반)
# K6 (privilege escalation) / K7 (mass export) / K8 (off-hours export) /
# K9 (deprecated account active) 모니터링.
#
# audit.db / users 테이블이 비어있거나 미존재해도 정상 동작 (빈 배열 반환).
# ════════════════════════════════════════════════════════════════


def _audit_table_name(conn: sqlite3.Connection) -> str:
    """audit.db 의 실제 테이블명 (api_audit_log / audit_log) 탐지."""
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if "api_audit_log" in tables:
            return "api_audit_log"
        if "audit_log" in tables:
            return "audit_log"
    except Exception:
        pass
    return "api_audit_log"


def _user_role_levels() -> Dict[str, int]:
    """employee_id → role_level 룩업 (auth.db users + roles)."""
    if not Path(AUTH_DB).exists():
        return {}
    conn = sqlite3.connect(AUTH_DB)
    try:
        rows = conn.execute("""
            SELECT u.employee_id, COALESCE(r.role_level, 1)
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.role_id
        """).fetchall()
        return {eid: int(lvl) for eid, lvl in rows if eid}
    except Exception:
        return {}
    finally:
        conn.close()


def detect_privilege_escalation(window_hours: int = 24) -> List[Dict]:
    """role_level < 4 사용자가 /admin/* 경로 접근 시도 (K6).

    Returns: list of {user_id, employee_id, attempts, last_attempt_ts, blocked}
    """
    if not Path(AUDIT_DB).exists():
        return []
    role_levels = _user_role_levels()
    conn = sqlite3.connect(AUDIT_DB)
    cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
    table = _audit_table_name(conn)
    results: List[Dict] = []
    try:
        cursor = conn.execute(
            f"""SELECT employee_id, COUNT(*) AS attempts, MAX(timestamp) AS last_ts,
                       MAX(status_code) AS last_status
                  FROM {table}
                 WHERE timestamp >= ?
                   AND endpoint LIKE '/api/admin/%'
                 GROUP BY employee_id""",
            (cutoff,),
        )
        for emp_id, attempts, last_ts, last_status in cursor.fetchall():
            if not emp_id:
                continue
            level = role_levels.get(emp_id, 1)
            if level >= 4:
                continue
            blocked = (last_status or 0) in (401, 403)
            results.append({
                "employee_id": emp_id,
                "user_id": emp_id,
                "attempts": int(attempts or 0),
                "last_attempt_ts": last_ts or "",
                "role_level": level,
                "blocked": bool(blocked),
            })
    except Exception:
        pass
    finally:
        conn.close()
    results.sort(key=lambda r: r["attempts"], reverse=True)
    return results


def detect_mass_export(window_hours: int = 1, threshold: int = 20) -> List[Dict]:
    """1 시간 내 N+ 다운로드 (K7 정보 유출 의심).

    'download' 행위는 endpoint 키워드 (/download, /export, /api/download) 또는
    method=GET + endpoint contains 'export|download' 로 식별.
    """
    if not Path(AUDIT_DB).exists():
        return []
    conn = sqlite3.connect(AUDIT_DB)
    cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
    table = _audit_table_name(conn)
    results: List[Dict] = []
    try:
        cursor = conn.execute(
            f"""SELECT employee_id, COUNT(*) AS cnt, MAX(timestamp) AS last_ts
                  FROM {table}
                 WHERE timestamp >= ?
                   AND (endpoint LIKE '%/download%'
                        OR endpoint LIKE '%/export%'
                        OR endpoint LIKE '%/api/download%'
                        OR detail LIKE '%action=download%')
                 GROUP BY employee_id
                HAVING cnt >= ?""",
            (cutoff, int(threshold)),
        )
        for emp_id, cnt, last_ts in cursor.fetchall():
            if not emp_id:
                continue
            results.append({
                "employee_id": emp_id,
                "user_id": emp_id,
                "download_count": int(cnt or 0),
                "window_hours": window_hours,
                "threshold": int(threshold),
                "last_attempt_ts": last_ts or "",
            })
    except Exception:
        pass
    finally:
        conn.close()
    results.sort(key=lambda r: r["download_count"], reverse=True)
    return results


def detect_off_hours_export(
    off_hours: tuple = ("22:00", "06:00"),
    window_hours: int = 24,
) -> List[Dict]:
    """업무 외 시간 메일 발송 또는 다운로드 (K8).

    off_hours=("22:00","06:00") 의미: 22시 ~ 23시, 0시 ~ 5시 (06시 직전).
    """
    if not Path(AUDIT_DB).exists():
        return []
    try:
        start_h = int(off_hours[0].split(":")[0])
        end_h = int(off_hours[1].split(":")[0])
    except (ValueError, IndexError):
        start_h, end_h = 22, 6

    conn = sqlite3.connect(AUDIT_DB)
    cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
    table = _audit_table_name(conn)
    results: List[Dict] = []
    try:
        cursor = conn.execute(
            f"""SELECT employee_id, endpoint, method, timestamp, status_code
                  FROM {table}
                 WHERE timestamp >= ?
                   AND (endpoint LIKE '%/mail%'
                        OR endpoint LIKE '%/draft/send%'
                        OR endpoint LIKE '%/download%'
                        OR endpoint LIKE '%/export%')""",
            (cutoff,),
        )
        for emp_id, endpoint, method, ts, status in cursor.fetchall():
            if not emp_id or not ts:
                continue
            try:
                hour = int(ts[11:13])
            except (ValueError, IndexError):
                continue
            # off-hours: start_h..23 OR 0..end_h-1
            in_off = (hour >= start_h) or (hour < end_h)
            if not in_off:
                continue
            action = "mail_send" if ("/mail" in endpoint or "/draft/send" in endpoint) else "download"
            results.append({
                "employee_id": emp_id,
                "user_id": emp_id,
                "action": action,
                "endpoint": endpoint or "",
                "method": method or "GET",
                "timestamp": ts,
                "hour": hour,
                "status_code": int(status or 200),
            })
    except Exception:
        pass
    finally:
        conn.close()
    results.sort(key=lambda r: r["timestamp"], reverse=True)
    return results


def detect_deprecated_account_active(
    grace_days: int = 7,
    window_hours: int = 24,
) -> List[Dict]:
    """is_active=0 OR deprecated_at 설정된 계정으로 접근 (K9)."""
    if not Path(AUDIT_DB).exists() or not Path(AUTH_DB).exists():
        return []
    # 1) auth.db: 비활성 사용자 + (선택) deprecated_at
    conn_auth = sqlite3.connect(AUTH_DB)
    deprecated: Dict[str, Dict] = {}
    try:
        # deprecated_at 컬럼은 존재하지 않을 수 있음 → fallback
        try:
            rows = conn_auth.execute(
                "SELECT employee_id, username, is_active, deprecated_at FROM users WHERE is_active = 0"
            ).fetchall()
            for emp_id, name, is_active, dep_at in rows:
                if emp_id:
                    deprecated[emp_id] = {
                        "employee_id": emp_id,
                        "username": name or "",
                        "is_active": int(is_active or 0),
                        "deprecated_at": dep_at or "",
                    }
        except sqlite3.OperationalError:
            rows = conn_auth.execute(
                "SELECT employee_id, username, is_active FROM users WHERE is_active = 0"
            ).fetchall()
            for emp_id, name, is_active in rows:
                if emp_id:
                    deprecated[emp_id] = {
                        "employee_id": emp_id,
                        "username": name or "",
                        "is_active": int(is_active or 0),
                        "deprecated_at": "",
                    }
    except Exception:
        pass
    finally:
        conn_auth.close()

    if not deprecated:
        return []

    # 2) audit.db: 해당 employee_id 의 최근 활동 row
    conn_audit = sqlite3.connect(AUDIT_DB)
    cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
    table = _audit_table_name(conn_audit)
    results: List[Dict] = []
    try:
        placeholders = ",".join("?" for _ in deprecated)
        cursor = conn_audit.execute(
            f"""SELECT employee_id, endpoint, method, timestamp, status_code
                  FROM {table}
                 WHERE timestamp >= ?
                   AND employee_id IN ({placeholders})""",
            (cutoff, *deprecated.keys()),
        )
        for emp_id, endpoint, method, ts, status in cursor.fetchall():
            meta = deprecated.get(emp_id, {})
            dep_at = meta.get("deprecated_at") or ""
            # grace_days 적용: deprecated_at + grace_days 이후 활동만 alert
            if dep_at:
                try:
                    dep_dt = datetime.fromisoformat(dep_at.replace("Z", ""))
                    grace_until = dep_dt + timedelta(days=grace_days)
                    ts_dt = datetime.fromisoformat(ts.replace("Z", "")) if ts else None
                    if ts_dt and ts_dt < grace_until:
                        continue
                except (ValueError, TypeError):
                    pass
            results.append({
                "employee_id": emp_id,
                "user_id": emp_id,
                "username": meta.get("username", ""),
                "endpoint": endpoint or "",
                "method": method or "GET",
                "timestamp": ts or "",
                "status_code": int(status or 200),
                "deprecated_at": dep_at,
            })
    except Exception:
        pass
    finally:
        conn_audit.close()
    results.sort(key=lambda r: r["timestamp"], reverse=True)
    return results


# ════════════════════════════════════════════════════════════════
# PR-E5 — 통합 7-패턴 anomaly feed
# ════════════════════════════════════════════════════════════════

_SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _classify_severity(pattern: str, payload: Dict) -> str:
    """패턴별 severity 분류 (CRITICAL/HIGH/MEDIUM/LOW)."""
    if pattern == "brute_force":
        return "CRITICAL" if payload.get("attempts", 0) >= 5 else "HIGH"
    if pattern == "unusual_hour":
        return "MEDIUM"
    if pattern == "inactive_access":
        return "CRITICAL"
    if pattern == "privilege_escalation":
        return "CRITICAL" if payload.get("attempts", 0) >= 3 else "HIGH"
    if pattern == "mass_export":
        return "HIGH"
    if pattern == "off_hours_export":
        return "MEDIUM"
    if pattern == "deprecated_account_active":
        return "CRITICAL"
    return "LOW"


def build_anomaly_feed(window_hours: int = 24) -> List[Dict]:
    """7-패턴 (기존 3 + 신규 4) 통합 알람 피드 — severity DESC 정렬."""
    feed: List[Dict] = []

    # 1) 기존 3 패턴 (SecurityAlert dataclass → dict)
    legacy = detect_anomalies(hours=window_hours)
    for a in legacy:
        # 기존 severity (critical/warning/info) → CAPS 매핑
        sev_map = {"critical": "CRITICAL", "warning": "HIGH", "info": "MEDIUM"}
        feed.append({
            "pattern": a.alert_type,
            "severity": sev_map.get(a.severity, "LOW"),
            "title": a.title,
            "description": a.description,
            "employee_id": a.employee_id,
            "timestamp": a.timestamp,
            "details": a.details,
        })

    # 2) K6 — privilege_escalation
    for r in detect_privilege_escalation(window_hours=window_hours):
        feed.append({
            "pattern": "privilege_escalation",
            "severity": _classify_severity("privilege_escalation", r),
            "title": f"권한 상승 시도: {r['employee_id']}",
            "description": (
                f"L{r['role_level']} 사용자가 /admin/* 경로 {r['attempts']}회 시도"
                f"{' (차단됨)' if r['blocked'] else ''}"
            ),
            "employee_id": r["employee_id"],
            "timestamp": r["last_attempt_ts"],
            "details": r,
        })

    # 3) K7 — mass_export
    for r in detect_mass_export(window_hours=1):
        feed.append({
            "pattern": "mass_export",
            "severity": _classify_severity("mass_export", r),
            "title": f"대량 다운로드: {r['employee_id']}",
            "description": f"{r['window_hours']}h 내 {r['download_count']}건 (임계치 {r['threshold']})",
            "employee_id": r["employee_id"],
            "timestamp": r["last_attempt_ts"],
            "details": r,
        })

    # 4) K8 — off_hours_export
    for r in detect_off_hours_export(window_hours=window_hours):
        feed.append({
            "pattern": "off_hours_export",
            "severity": _classify_severity("off_hours_export", r),
            "title": f"야간 {('메일 발송' if r['action'] == 'mail_send' else '다운로드')}: {r['employee_id']}",
            "description": f"{r['hour']:02d}시 — {r['endpoint']}",
            "employee_id": r["employee_id"],
            "timestamp": r["timestamp"],
            "details": r,
        })

    # 5) K9 — deprecated_account_active
    for r in detect_deprecated_account_active(window_hours=window_hours):
        feed.append({
            "pattern": "deprecated_account_active",
            "severity": _classify_severity("deprecated_account_active", r),
            "title": f"퇴직 계정 활동: {r.get('username') or r['employee_id']}",
            "description": f"{r['endpoint']} (deprecated_at={r.get('deprecated_at') or 'N/A'})",
            "employee_id": r["employee_id"],
            "timestamp": r["timestamp"],
            "details": r,
        })

    # 안정 정렬: severity 1차 (CRITICAL→HIGH→MEDIUM→LOW), timestamp DESC 2차.
    # Python 의 sort 안정성 이용 — secondary key 를 먼저 정렬, primary 를 다음.
    feed.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    feed.sort(key=lambda x: _SEVERITY_RANK.get(x["severity"], 9))
    return feed


# ════════════════════════════════════════════════════════════════
# PR-E5 — 5-차원 dashboard summary
# (시간 / 이상 / 위반 / ROI / 변경)
# ════════════════════════════════════════════════════════════════


def _period_to_hours(period: str) -> int:
    return {"day": 24, "week": 168, "month": 720}.get(period, 24)


def get_time_pattern(period: str = "week") -> List[Dict]:
    """시간(0-23) × 요일(0=월..6=일) × 부서 사용량 — heatmap source."""
    if not Path(AUDIT_DB).exists():
        return []
    conn = sqlite3.connect(AUDIT_DB)
    hours = _period_to_hours(period)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    table = _audit_table_name(conn)
    bins: Dict[tuple, int] = defaultdict(int)
    try:
        cursor = conn.execute(
            f"SELECT timestamp, department FROM {table} WHERE timestamp >= ?",
            (cutoff,),
        )
        for ts, dept in cursor.fetchall():
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", ""))
                key = (dt.hour, dt.weekday(), dept or "미분류")
                bins[key] += 1
            except (ValueError, TypeError):
                continue
    except Exception:
        pass
    finally:
        conn.close()
    return [
        {"hour": h, "weekday": w, "department": d, "count": c}
        for (h, w, d), c in sorted(bins.items())
    ]


def get_permission_violations(period: str = "week") -> List[Dict]:
    """audit.db status_code IN (401,403) 행 — K4 권한 위반 표."""
    if not Path(AUDIT_DB).exists():
        return []
    conn = sqlite3.connect(AUDIT_DB)
    hours = _period_to_hours(period)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    table = _audit_table_name(conn)
    rows: List[Dict] = []
    try:
        cursor = conn.execute(
            f"""SELECT timestamp, employee_id, name, department, role,
                       endpoint, method, status_code, detail, ip_address
                  FROM {table}
                 WHERE timestamp >= ?
                   AND status_code IN (401, 403)
                 ORDER BY timestamp DESC
                 LIMIT 200""",
            (cutoff,),
        )
        for r in cursor.fetchall():
            rows.append({
                "timestamp": r[0] or "",
                "employee_id": r[1] or "",
                "name": r[2] or "",
                "department": r[3] or "",
                "role": r[4] or "",
                "endpoint": r[5] or "",
                "method": r[6] or "GET",
                "status_code": int(r[7] or 0),
                "detail": r[8] or "",
                "ip_address": r[9] or "",
            })
    except Exception:
        pass
    finally:
        conn.close()
    return rows


def get_feature_usage_summary(period: str = "week") -> List[Dict]:
    """기능별 (A/B/C/D/E/F) 사용량 + 만족도 (feedback.db 연계)."""
    # 사용량 (usage_analytics.get_usage_by_feature 재사용 — DRY)
    try:
        from features.admin.usage_analytics import (
            get_usage_by_feature, FEATURE_NAMES,
        )
        hours = _period_to_hours(period)
        days = max(1, hours // 24)
        usage = get_usage_by_feature(days=days)
    except Exception:
        usage = [{"feature": f, "name": "", "count": 0} for f in "ABCDEF"]

    # 만족도 (feedback.db)
    satisfaction: Dict[str, Dict] = {}
    fb_path = Path("data/feedback.db")
    if fb_path.exists():
        try:
            conn = sqlite3.connect(str(fb_path))
            try:
                cursor = conn.execute("""
                    SELECT feature, AVG(rating) AS avg_rating, COUNT(*) AS cnt
                      FROM feedback
                     GROUP BY feature
                """)
                for f, avg_r, cnt in cursor.fetchall():
                    satisfaction[(f or "").upper()] = {
                        "avg_rating": round(float(avg_r or 0), 2),
                        "count": int(cnt or 0),
                    }
            except sqlite3.OperationalError:
                # feedback 테이블 schema 가 다르면 무시
                pass
            finally:
                conn.close()
        except Exception:
            pass

    return [
        {
            "feature": u["feature"],
            "name": u.get("name", ""),
            "count": u.get("count", 0),
            "avg_rating": satisfaction.get(u["feature"], {}).get("avg_rating", 0.0),
            "feedback_count": satisfaction.get(u["feature"], {}).get("count", 0),
        }
        for u in usage
    ]


def get_change_audit_timeline(period: str = "week") -> List[Dict]:
    """데이터 변경 (PUT/DELETE/POST + grant/revoke 키워드) 시간순."""
    if not Path(AUDIT_DB).exists():
        return []
    conn = sqlite3.connect(AUDIT_DB)
    hours = _period_to_hours(period)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    table = _audit_table_name(conn)
    rows: List[Dict] = []
    try:
        cursor = conn.execute(
            f"""SELECT timestamp, employee_id, name, role,
                       endpoint, method, status_code, detail
                  FROM {table}
                 WHERE timestamp >= ?
                   AND (method IN ('PUT', 'DELETE', 'PATCH')
                        OR endpoint LIKE '%/grant%'
                        OR endpoint LIKE '%/revoke%'
                        OR endpoint LIKE '%/bulk-role%')
                 ORDER BY timestamp DESC
                 LIMIT 200""",
            (cutoff,),
        )
        for r in cursor.fetchall():
            endpoint = r[4] or ""
            method = r[5] or ""
            action = method.lower()
            if "grant" in endpoint:
                action = "grant"
            elif "revoke" in endpoint:
                action = "revoke"
            elif "bulk-role" in endpoint:
                action = "role_change"
            rows.append({
                "timestamp": r[0] or "",
                "actor": r[1] or "",
                "actor_name": r[2] or "",
                "actor_role": r[3] or "",
                "action": action,
                "endpoint": endpoint,
                "method": method,
                "status_code": int(r[6] or 200),
                "detail": r[7] or "",
            })
    except Exception:
        pass
    finally:
        conn.close()
    return rows


def build_dashboard(period: str = "week") -> Dict:
    """5-차원 대시보드 통합 응답 (audit dashboard endpoint)."""
    return {
        "period": period,
        "time_pattern": get_time_pattern(period),
        "anomalies": build_anomaly_feed(window_hours=_period_to_hours(period)),
        "permission_violations": get_permission_violations(period),
        "feature_usage": get_feature_usage_summary(period),
        "change_audit": get_change_audit_timeline(period),
    }


def get_recent_logins(limit: int = 30) -> List[Dict]:
    """최근 로그인 이력. Postgres audit 우선.

    v4.9.1 — department + role_name 응답 포함 (employees JOIN).
    """
    try:
        from core.auth.postgres_audit import read_recent_logins
        pg = read_recent_logins(limit)
        if pg:
            return [{
                "employee_id": r.get("employee_id", ""),
                "username": "",
                "action": r.get("action", "login"),
                "success": r.get("success", 1),
                "ip_address": r.get("ip_address", ""),
                "timestamp": r.get("timestamp", ""),
                "department": "",
                "role_name": "",
            } for r in pg]
    except Exception:
        pass

    # Legacy Firestore fallback (Firestore audit엔 dept/role 없으므로 SQLite 보강)
    try:
        from core.auth.firestore_audit import read_recent_logins
        fs = read_recent_logins(limit)
        if fs:
            # employee_id → (department, role_name) 룩업 (SQLite users + roles)
            emp_meta: Dict[str, Dict[str, str]] = {}
            if Path(AUTH_DB).exists():
                conn = sqlite3.connect(AUTH_DB)
                try:
                    rows = conn.execute("""
                        SELECT u.employee_id, u.department, r.role_name
                        FROM users u
                        LEFT JOIN roles r ON u.role_id = r.role_id
                    """).fetchall()
                    for eid, dept, rname in rows:
                        emp_meta[eid] = {"department": dept or "", "role_name": rname or ""}
                except Exception:
                    pass
                finally:
                    conn.close()
            return [{
                "employee_id": r.get("employee_id", ""),
                "username": "",
                "action": r.get("action", "login"),
                "success": r.get("success", 1),
                "ip_address": r.get("ip_address", ""),
                "timestamp": r.get("timestamp", ""),
                "department": emp_meta.get(r.get("employee_id", ""), {}).get("department", ""),
                "role_name": emp_meta.get(r.get("employee_id", ""), {}).get("role_name", ""),
            } for r in fs]
    except Exception:
        pass

    if not Path(AUTH_DB).exists():
        return []
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("""
            SELECT lh.employee_id, u.username, lh.action, lh.success,
                   lh.ip_address, lh.timestamp,
                   u.department, r.role_name
            FROM login_history lh
            LEFT JOIN users u ON lh.user_id = u.user_id
            LEFT JOIN roles r ON u.role_id = r.role_id
            ORDER BY lh.timestamp DESC LIMIT ?
        """, (limit,))
        results = [
            {
                **dict(r),
                "department": r["department"] or "",
                "role_name": r["role_name"] or "",
            }
            for r in cursor.fetchall()
        ]
    except Exception:
        results = []
    conn.close()
    return results
