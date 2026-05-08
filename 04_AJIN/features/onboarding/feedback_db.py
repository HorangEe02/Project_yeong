"""
챗봇 응답 피드백 DB — 👍👎 수집 + 만족도 분석

v3.0: 사용자 피드백을 수집하여 응답 품질 개선 방향을 도출합니다.
"""
import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FEEDBACK_DB_PATH = Path("data/feedback.db")


def _get_conn(db_path: Path = FEEDBACK_DB_PATH) -> sqlite3.Connection:
    """DB 연결 + 초기화"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT DEFAULT '',
            query TEXT NOT NULL,
            response_preview TEXT DEFAULT '',
            intent TEXT DEFAULT '',
            is_positive INTEGER NOT NULL,
            user_department TEXT DEFAULT '',
            user_position TEXT DEFAULT '',
            comment TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fb_created ON chat_feedback(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fb_intent ON chat_feedback(intent)")
    conn.commit()
    return conn


def save_feedback(
    query: str,
    is_positive: bool,
    session_id: str = "",
    intent: str = "",
    response_preview: str = "",
    user_department: str = "",
    user_position: str = "",
    comment: str = "",
    db_path: Path = FEEDBACK_DB_PATH,
) -> int:
    """피드백 1건 저장. Returns: ID"""
    conn = _get_conn(db_path)
    cursor = conn.execute(
        """INSERT INTO chat_feedback
           (session_id, query, response_preview, intent, is_positive,
            user_department, user_position, comment)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, query, response_preview[:300] if response_preview else "",
         intent, 1 if is_positive else 0,
         user_department, user_position, comment),
    )
    conn.commit()
    fb_id = cursor.lastrowid
    conn.close()
    return fb_id


def get_satisfaction_stats(days: int = 30, db_path: Path = FEEDBACK_DB_PATH) -> dict:
    """전체 만족도 통계"""
    conn = _get_conn(db_path)
    row = conn.execute(
        """SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_positive = 1 THEN 1 ELSE 0 END) as positive,
            SUM(CASE WHEN is_positive = 0 THEN 1 ELSE 0 END) as negative
           FROM chat_feedback
           WHERE created_at >= datetime('now', 'localtime', ?)""",
        (f"-{days} days",),
    ).fetchone()
    conn.close()

    total = row["total"] or 0
    positive = row["positive"] or 0
    rate = round(positive / total * 100, 1) if total > 0 else 0

    return {
        "total": total,
        "positive": positive,
        "negative": row["negative"] or 0,
        "satisfaction_rate": rate,
    }


def get_intent_satisfaction(days: int = 30, db_path: Path = FEEDBACK_DB_PATH) -> list[dict]:
    """인텐트별 만족도"""
    conn = _get_conn(db_path)
    rows = conn.execute(
        """SELECT
            intent,
            COUNT(*) as total,
            SUM(CASE WHEN is_positive = 1 THEN 1 ELSE 0 END) as positive
           FROM chat_feedback
           WHERE created_at >= datetime('now', 'localtime', ?) AND intent != ''
           GROUP BY intent
           ORDER BY total DESC""",
        (f"-{days} days",),
    ).fetchall()
    conn.close()

    return [
        {
            "intent": r["intent"],
            "total": r["total"],
            "positive": r["positive"],
            "satisfaction_rate": round(r["positive"] / r["total"] * 100, 1) if r["total"] > 0 else 0,
        }
        for r in rows
    ]


def get_department_satisfaction(days: int = 30, db_path: Path = FEEDBACK_DB_PATH) -> list[dict]:
    """부서별 만족도"""
    conn = _get_conn(db_path)
    rows = conn.execute(
        """SELECT
            user_department,
            COUNT(*) as total,
            SUM(CASE WHEN is_positive = 1 THEN 1 ELSE 0 END) as positive
           FROM chat_feedback
           WHERE created_at >= datetime('now', 'localtime', ?) AND user_department != ''
           GROUP BY user_department
           ORDER BY total DESC""",
        (f"-{days} days",),
    ).fetchall()
    conn.close()

    return [
        {
            "department": r["user_department"],
            "total": r["total"],
            "positive": r["positive"],
            "satisfaction_rate": round(r["positive"] / r["total"] * 100, 1) if r["total"] > 0 else 0,
        }
        for r in rows
    ]


def get_recent_negative(limit: int = 10, db_path: Path = FEEDBACK_DB_PATH) -> list[dict]:
    """최근 부정 피드백 목록 (개선 우선순위 도출용)"""
    conn = _get_conn(db_path)
    rows = conn.execute(
        """SELECT * FROM chat_feedback
           WHERE is_positive = 0
           ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
