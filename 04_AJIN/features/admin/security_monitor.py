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

    try:
        cursor = conn.execute("""
            SELECT employee_id, COUNT(*) as fail_count, MAX(timestamp) as last_attempt,
                   GROUP_CONCAT(DISTINCT ip_address) as ips
            FROM login_history
            WHERE success = 0 AND timestamp >= ?
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

    try:
        cursor = conn.execute("""
            SELECT employee_id, timestamp, ip_address, success
            FROM login_history
            WHERE timestamp >= ?
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

    try:
        cursor = conn.execute("""
            SELECT lh.employee_id, lh.timestamp, lh.ip_address, u.username, u.is_active
            FROM login_history lh
            LEFT JOIN users u ON lh.employee_id = u.employee_id
            WHERE lh.timestamp >= ? AND u.is_active = 0
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
    """로그인 통계"""
    if not Path(AUTH_DB).exists():
        return {"total_logins": 0, "successful": 0, "failed": 0, "success_rate": 0, "unique_users": 0, "locked_accounts": 0}

    conn = sqlite3.connect(AUTH_DB)
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    total = conn.execute("SELECT COUNT(*) FROM login_history WHERE timestamp >= ?", (cutoff,)).fetchone()[0]
    success = conn.execute("SELECT COUNT(*) FROM login_history WHERE timestamp >= ? AND success=1", (cutoff,)).fetchone()[0]
    unique = conn.execute("SELECT COUNT(DISTINCT employee_id) FROM login_history WHERE timestamp >= ? AND success=1", (cutoff,)).fetchone()[0]

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

    try:
        cursor = conn.execute("""
            SELECT DATE(timestamp) as day,
                   SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                   SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fail
            FROM login_history WHERE timestamp >= ?
            GROUP BY DATE(timestamp) ORDER BY day
        """, (cutoff,))
        results = [{"date": r[0], "success": r[1], "failed": r[2]} for r in cursor.fetchall()]
    except Exception:
        results = []
    conn.close()
    return results


def get_login_hour_distribution(days: int = 30) -> List[Dict]:
    """시간대별 로그인 분포"""
    if not Path(AUTH_DB).exists():
        return [{"hour": h, "count": 0, "failed": 0} for h in range(24)]

    conn = sqlite3.connect(AUTH_DB)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    hour_data = defaultdict(lambda: {"count": 0, "failed": 0})

    try:
        cursor = conn.execute("SELECT timestamp, success FROM login_history WHERE timestamp >= ?", (cutoff,))
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


def get_recent_logins(limit: int = 30) -> List[Dict]:
    """최근 로그인 이력"""
    if not Path(AUTH_DB).exists():
        return []
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("""
            SELECT lh.employee_id, u.username, lh.action, lh.success,
                   lh.ip_address, lh.timestamp
            FROM login_history lh
            LEFT JOIN users u ON lh.user_id = u.user_id
            ORDER BY lh.timestamp DESC LIMIT ?
        """, (limit,))
        results = [dict(r) for r in cursor.fetchall()]
    except Exception:
        results = []
    conn.close()
    return results
