"""F12 — 크롤 실행 감사(audit) 테이블.

기존 `crawl_history` 는 데이터 스냅샷(언제 어떤 항목을 어디서 받아왔는가) 용도.
본 모듈의 `crawl_runs` 는 **실행 단위** 감사 — 누가/언제 트리거했고, 얼마나 걸렸고,
HTTP 응답 메타(ETag, Last-Modified)는 무엇이며, 결과 ok/실패 인지를 1줄로 기록.

페르소나 가치:
- 현직자: incident 회고 시 "지난주 어느 크롤이 실패했는지" 단일 쿼리.
- 신입: 일일 다이제스트 첨부 "지난 24시간 크롤 N회 (실패 M건)" 학습 자료.

F8 (real HTTP), F9 (ETag), F10 (cron fan-out) 모두 이 테이블에 결과를 적재한다.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR
from features.compliance.crawlers.sla import CRAWLER_SLA_POLICIES, CrawlerSlaPolicy

DB_PATH = DATA_DIR / "compliance.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table() -> None:
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS crawl_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                crawler_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                elapsed_ms INTEGER NOT NULL DEFAULT 0,
                ok INTEGER NOT NULL DEFAULT 1,
                updates_found INTEGER DEFAULT 0,
                errors TEXT DEFAULT '',
                trigger_source TEXT DEFAULT '',
                http_status INTEGER,
                http_etag TEXT DEFAULT '',
                http_last_modified TEXT DEFAULT '',
                user_id TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_crawl_runs_name ON crawl_runs(crawler_name);
            CREATE INDEX IF NOT EXISTS idx_crawl_runs_started ON crawl_runs(started_at);
            CREATE INDEX IF NOT EXISTS idx_crawl_runs_ok ON crawl_runs(ok);
        """)
        conn.commit()
    finally:
        conn.close()


def record_run(
    crawler_name: str,
    started_at: str,
    elapsed_ms: int,
    ok: bool,
    updates_found: int = 0,
    errors: list[str] | str = "",
    trigger_source: str = "api",
    http_status: int | None = None,
    http_etag: str = "",
    http_last_modified: str = "",
    user_id: str = "",
) -> int:
    """크롤 1회 실행 결과를 기록. run_id 반환."""
    ensure_table()
    if isinstance(errors, list):
        errors_str = " | ".join(str(e) for e in errors[:5])
    else:
        errors_str = str(errors)[:500]

    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO crawl_runs(crawler_name, started_at, elapsed_ms, ok, "
            "updates_found, errors, trigger_source, http_status, http_etag, "
            "http_last_modified, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                crawler_name,
                started_at,
                int(elapsed_ms),
                1 if ok else 0,
                int(updates_found or 0),
                errors_str,
                trigger_source,
                http_status,
                http_etag,
                http_last_modified,
                user_id,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_runs(
    limit: int = 50,
    crawler_name: str | None = None,
    only_failed: bool = False,
    since_iso: str | None = None,
) -> list[dict[str, Any]]:
    ensure_table()
    sql = "SELECT * FROM crawl_runs WHERE 1=1"
    params: list[Any] = []
    if crawler_name:
        sql += " AND crawler_name = ?"
        params.append(crawler_name)
    if only_failed:
        sql += " AND ok = 0"
    if since_iso:
        sql += " AND started_at >= ?"
        params.append(since_iso)
    sql += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an ISO datetime into UTC for SLA age checks.

    Args:
        value: ISO datetime string from crawler output or audit rows.

    Returns:
        datetime | None: Timezone-aware UTC datetime, or None when invalid.
    """

    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_run(
    conn: sqlite3.Connection,
    crawler_name: str,
    *,
    ok_only: bool = False,
) -> dict[str, Any] | None:
    """Load the latest audit row for a crawler.

    Args:
        conn: SQLite connection with row factory.
        crawler_name: Crawler key.
        ok_only: Whether to restrict to successful rows.

    Returns:
        dict[str, Any] | None: Latest row as a dict when present.
    """

    where = "crawler_name = ?"
    params: list[Any] = [crawler_name]
    if ok_only:
        where += " AND ok = 1"
    row = conn.execute(
        f"SELECT * FROM crawl_runs WHERE {where} ORDER BY started_at DESC, run_id DESC LIMIT 1",
        params,
    ).fetchone()
    return dict(row) if row is not None else None


def _result_source_type(policy: CrawlerSlaPolicy) -> str:
    """Read the latest crawler result file source type.

    Args:
        policy: Crawler SLA policy.

    Returns:
        str: ``live``, ``curated``, or ``unknown``.
    """

    path = DATA_DIR / "crawled" / policy.result_file
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "unknown"
    source_type = str(data.get("source_type") or "").lower() if isinstance(data, dict) else ""
    return source_type if source_type in {"live", "curated"} else "unknown"


def _crawler_sla_snapshot(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """Build secret-safe crawler SLA status from audit rows and result files.

    Args:
        conn: SQLite connection with row factory.

    Returns:
        dict[str, dict[str, Any]]: SLA status keyed by crawler name.
    """

    now = datetime.now(timezone.utc)
    out: dict[str, dict[str, Any]] = {}
    for name, policy in CRAWLER_SLA_POLICIES.items():
        latest_any = _latest_run(conn, name)
        latest_success = _latest_run(conn, name, ok_only=True)
        source_type = _result_source_type(policy)
        credential_present = (
            bool(os.environ.get(policy.required_credential, "").strip())
            if policy.required_credential else True
        )
        status = "degraded"
        age_hours: float | None = None
        if policy.required_credential and not credential_present:
            status = "missing_credential"
        elif latest_success:
            last_success_at = _parse_iso_datetime(str(latest_success.get("started_at") or ""))
            if last_success_at:
                age_hours = max(0.0, (now - last_success_at).total_seconds() / 3600)
            if age_hours is not None and age_hours > policy.max_stale_hours:
                status = "stale"
            elif source_type == "curated":
                status = "degraded"
            else:
                status = "fresh"

        out[name] = {
            "status": status,
            "official_source": policy.official_source,
            "cadence": policy.cadence,
            "max_stale_hours": policy.max_stale_hours,
            "fallback_allowed": policy.fallback_allowed,
            "official_domains": list(policy.official_domain_allowlist),
            "credential_required": bool(policy.required_credential),
            "credential_present": credential_present,
            "source_type": source_type,
            "last_success_at": latest_success.get("started_at") if latest_success else "",
            "last_run_at": latest_any.get("started_at") if latest_any else "",
            "last_http_status": latest_success.get("http_status") if latest_success else None,
            "last_http_etag": latest_success.get("http_etag") if latest_success else "",
            "last_http_last_modified": latest_success.get("http_last_modified") if latest_success else "",
            "age_hours": round(age_hours, 2) if age_hours is not None else None,
        }
    return out


def stats_24h() -> dict[str, Any]:
    """다이제스트용 — 지난 24시간 실행 통계."""
    ensure_table()
    cutoff = (datetime.now().replace(microsecond=0)).isoformat()
    # 단순 빠른 KPI — full window 미사용 시 last 24h 시뮬은 호출자 책임.
    conn = _connect()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM crawl_runs WHERE started_at >= datetime('now', '-1 day', 'localtime')"
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM crawl_runs WHERE ok = 0 "
            "AND started_at >= datetime('now', '-1 day', 'localtime')"
        ).fetchone()[0]
        per_crawler = conn.execute(
            "SELECT crawler_name, COUNT(*) AS cnt, SUM(ok) AS ok_cnt "
            "FROM crawl_runs WHERE started_at >= datetime('now', '-1 day', 'localtime') "
            "GROUP BY crawler_name ORDER BY cnt DESC"
        ).fetchall()
        return {
            "window": "24h",
            "total_runs": total,
            "failed_runs": failed,
            "per_crawler": [dict(r) for r in per_crawler],
            "sla": _crawler_sla_snapshot(conn),
            "queried_at": cutoff,
        }
    finally:
        conn.close()
