"""부록 6 P4-1 + P4-3 — Firestore draft history aggregation.

매일 04:00 KST Celery 잡이 Firestore `/documents/{uid}/items/*` 를 읽어
- 부서별 docType 사용 카운트 (`draft_dept_usage`)
- 사용자별 docType 사용 카운트 (`draft_user_picks`)
2 테이블을 SQLite compliance.db 에 적재.

페르소나: 신입 (부서 표준 학습), 시니어 (개인 자동 정렬).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from config import DATA_DIR

DB_PATH = DATA_DIR / "compliance.db"
AUTH_DB_PATH = DATA_DIR / "auth.db"

logger = logging.getLogger(__name__)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables() -> None:
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS draft_dept_usage (
                department TEXT NOT NULL,
                doc_type_id TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                last_aggregated_at TEXT,
                PRIMARY KEY (department, doc_type_id)
            );
            CREATE INDEX IF NOT EXISTS idx_dept_usage_dept ON draft_dept_usage(department);

            CREATE TABLE IF NOT EXISTS draft_user_picks (
                user_id TEXT NOT NULL,
                doc_type_id TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                last_picked_at TEXT,
                PRIMARY KEY (user_id, doc_type_id)
            );
            CREATE INDEX IF NOT EXISTS idx_user_picks_user ON draft_user_picks(user_id);

            CREATE TABLE IF NOT EXISTS draft_agg_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                elapsed_ms INTEGER,
                docs_scanned INTEGER,
                dept_rows INTEGER,
                user_rows INTEGER,
                ok INTEGER DEFAULT 1,
                error TEXT DEFAULT ''
            );
        """)
        conn.commit()
    finally:
        conn.close()


def _uid_to_dept_map() -> dict[str, str]:
    """auth.db users 테이블에서 user_uid → department 매핑 로드 (1회 캐시)."""
    if not AUTH_DB_PATH.exists():
        return {}
    conn = sqlite3.connect(AUTH_DB_PATH)
    try:
        # auth.db 에는 employee_id 가 PK. Firestore user_uid 도 employee_id 기준으로 매핑한다.
        rows = conn.execute(
            "SELECT employee_id, department FROM users WHERE department IS NOT NULL"
        ).fetchall()
        return {r[0]: r[1] for r in rows if r[0] and r[1]}
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()


def run_aggregation(window_hours: int = 24) -> dict[str, Any]:
    """Firestore draft history → SQLite aggregation. 어제 window_hours 시간만 incremental.

    Returns: {docs_scanned, dept_rows, user_rows, elapsed_ms, ok}
    """
    ensure_tables()
    started = datetime.now()
    started_iso = started.isoformat(timespec="seconds")
    cutoff_ms = int((started - timedelta(hours=window_hours)).timestamp() * 1000)

    try:
        from firebase_admin import firestore  # type: ignore
        import firebase_admin
        try:
            db = firestore.client()
        except ValueError:
            # firebase_admin 미초기화 — 인증 시스템이 firebase 모드일 때만 init 되어있음
            logger.warning("firebase_admin not initialized — draft aggregation skip")
            return {"ok": False, "error": "firebase_admin not initialized"}
    except ImportError:
        logger.warning("firebase-admin 미설치 — aggregation skip")
        return {"ok": False, "error": "firebase-admin missing"}

    uid_to_dept = _uid_to_dept_map()
    dept_counts: dict[tuple[str, str], int] = {}
    user_counts: dict[tuple[str, str], int] = {}
    user_last: dict[tuple[str, str], int] = {}
    docs_scanned = 0

    try:
        # collection_group("items") — 모든 사용자의 items 횡단 조회
        # updated_at filter 로 incremental
        query = (
            db.collection_group("items")
            .where("updated_at", ">=", cutoff_ms)
            .limit(5000)
        )
        for doc_snap in query.stream():
            data = doc_snap.to_dict() or {}
            uid = data.get("user_uid") or ""
            doc_type = data.get("doc_type") or ""
            if not uid or not doc_type:
                continue
            docs_scanned += 1

            updated_at = int(data.get("updated_at") or 0)
            dept = uid_to_dept.get(uid, "")

            if dept:
                key_d = (dept, doc_type)
                dept_counts[key_d] = dept_counts.get(key_d, 0) + 1
            key_u = (uid, doc_type)
            user_counts[key_u] = user_counts.get(key_u, 0) + 1
            if updated_at > user_last.get(key_u, 0):
                user_last[key_u] = updated_at
    except Exception as e:
        logger.exception("Firestore stream 실패: %s", e)
        _record_run(started_iso, 0, docs_scanned, 0, 0, ok=False, error=str(e)[:200])
        return {"ok": False, "error": str(e)[:200]}

    # SQLite 적재
    conn = _connect()
    try:
        for (dept, dt), cnt in dept_counts.items():
            conn.execute(
                "INSERT INTO draft_dept_usage(department, doc_type_id, count, last_aggregated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(department, doc_type_id) DO UPDATE SET "
                "count = count + excluded.count, last_aggregated_at = excluded.last_aggregated_at",
                (dept, dt, cnt, started_iso),
            )
        for (uid, dt), cnt in user_counts.items():
            last_ms = user_last.get((uid, dt), 0)
            last_iso = (
                datetime.fromtimestamp(last_ms / 1000).isoformat(timespec="seconds")
                if last_ms else started_iso
            )
            conn.execute(
                "INSERT INTO draft_user_picks(user_id, doc_type_id, count, last_picked_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, doc_type_id) DO UPDATE SET "
                "count = count + excluded.count, last_picked_at = excluded.last_picked_at",
                (uid, dt, cnt, last_iso),
            )
        conn.commit()
    finally:
        conn.close()

    elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
    _record_run(started_iso, elapsed_ms, docs_scanned, len(dept_counts), len(user_counts), ok=True)
    return {
        "ok": True,
        "docs_scanned": docs_scanned,
        "dept_rows": len(dept_counts),
        "user_rows": len(user_counts),
        "elapsed_ms": elapsed_ms,
    }


def _record_run(
    started_at: str, elapsed_ms: int, docs_scanned: int,
    dept_rows: int, user_rows: int, ok: bool, error: str = "",
) -> None:
    ensure_tables()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO draft_agg_runs(started_at, elapsed_ms, docs_scanned, "
            "dept_rows, user_rows, ok, error) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (started_at, elapsed_ms, docs_scanned, dept_rows, user_rows,
             1 if ok else 0, error),
        )
        conn.commit()
    finally:
        conn.close()


def get_dept_recommendations(department: str, top_k: int = 3) -> list[dict[str, Any]]:
    """부서 기준 자주 쓰는 docType top-K. 빈 부서면 빈 리스트."""
    if not department:
        return []
    ensure_tables()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT doc_type_id, count FROM draft_dept_usage "
            "WHERE department = ? AND count > 0 "
            "ORDER BY count DESC LIMIT ?",
            (department, top_k),
        ).fetchall()
        return [{"doc_type_id": r["doc_type_id"], "count": int(r["count"])} for r in rows]
    finally:
        conn.close()


def get_personal_picks(user_id: str, top_k: int = 5, min_count: int = 3) -> list[dict[str, Any]]:
    """사용자 개인 빈도 top-K. count >= min_count 이상만 (데이터 부족 시 빈 결과)."""
    if not user_id:
        return []
    ensure_tables()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT doc_type_id, count, last_picked_at FROM draft_user_picks "
            "WHERE user_id = ? AND count >= ? "
            "ORDER BY count DESC LIMIT ?",
            (user_id, min_count, top_k),
        ).fetchall()
        return [
            {
                "doc_type_id": r["doc_type_id"],
                "count": int(r["count"]),
                "last_picked_at": r["last_picked_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()
