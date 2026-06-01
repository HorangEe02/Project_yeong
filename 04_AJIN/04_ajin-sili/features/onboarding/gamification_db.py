"""v4.7 C-4 — 게이미피케이션 DB 스키마 + CRUD.

테이블 5종 (모두 `data/learning.db` 단일 SQLite):
  - quiz_attempts          : 퀴즈 정/오답 누적 (배지 평가 source)
  - sop_progress           : 사용자별 SOP 단계 완료 (frontend useSopStore 백엔드 영속화)
  - user_badges            : 획득 배지 영속화
  - user_daily_activity    : 일별 활동 요약 (streak / 리더보드 산식 source)
  - dept_leaderboard_snapshots : 주/월 리더보드 스냅샷

`init_gamification_db()` 는 멱등 — 매 호출 시 CREATE TABLE IF NOT EXISTS.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("data/learning.db")


def _resolve_db_path(db_path: Optional[Path]) -> Path:
    """모듈 레벨 DB_PATH 를 동적으로 조회 (테스트 monkeypatch 가 default 값 캡처를 우회하도록).

    호출자가 명시한 db_path 가 있으면 우선 사용, 없으면 모듈 현재 DB_PATH 사용.
    """
    if db_path is not None:
        return db_path
    # 모듈 레벨 DB_PATH 를 import 시점 캡처 대신 호출 시점에 읽기
    import sys

    mod = sys.modules[__name__]
    return getattr(mod, "DB_PATH", DB_PATH)


@contextmanager
def get_conn(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    p = _resolve_db_path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_gamification_db(db_path: Optional[Path] = None) -> None:
    """5 테이블 멱등 생성. 모듈 import 시 한 번 호출 권장 (또는 lifespan)."""
    with get_conn(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_attempts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id TEXT NOT NULL,
              user_department TEXT DEFAULT '',
              sop_id TEXT DEFAULT '',
              category TEXT NOT NULL,
              difficulty TEXT NOT NULL,
              is_correct INTEGER NOT NULL,
              source_id TEXT DEFAULT '',
              related_step INTEGER DEFAULT 0,
              created_at TEXT DEFAULT (datetime('now','localtime'))
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_quiz_user_date ON quiz_attempts(user_id, created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_quiz_difficulty ON quiz_attempts(difficulty)")

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS sop_progress (
              user_id TEXT NOT NULL,
              sop_id TEXT NOT NULL,
              step_number INTEGER NOT NULL,
              completed_at TEXT NOT NULL,
              PRIMARY KEY (user_id, sop_id, step_number)
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_sop_user ON sop_progress(user_id, completed_at)")

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS user_badges (
              user_id TEXT NOT NULL,
              badge_id TEXT NOT NULL,
              earned_at TEXT NOT NULL,
              metadata TEXT DEFAULT '{}',
              PRIMARY KEY (user_id, badge_id)
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_badge_earned ON user_badges(earned_at)")

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS user_daily_activity (
              user_id TEXT NOT NULL,
              date TEXT NOT NULL,
              user_department TEXT DEFAULT '',
              chat_count INTEGER DEFAULT 0,
              quiz_total INTEGER DEFAULT 0,
              quiz_correct INTEGER DEFAULT 0,
              sop_steps_completed INTEGER DEFAULT 0,
              positive_feedback INTEGER DEFAULT 0,
              glossary_lookups INTEGER DEFAULT 0,
              PRIMARY KEY (user_id, date)
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS dept_leaderboard_snapshots (
              dept TEXT NOT NULL,
              period TEXT NOT NULL,
              top_users_json TEXT NOT NULL,
              computed_at TEXT NOT NULL,
              PRIMARY KEY (dept, period)
            )
            """
        )


# ── quiz_attempts ──────────────────────────────────────────────


def record_quiz_attempt(
    user_id: str,
    *,
    is_correct: bool,
    category: str,
    difficulty: str = "basic",
    sop_id: str = "",
    source_id: str = "",
    related_step: int = 0,
    user_department: str = "",
    db_path: Optional[Path] = None,
) -> int:
    """퀴즈 1건 INSERT. Returns: id"""
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO quiz_attempts
              (user_id, user_department, sop_id, category, difficulty, is_correct, source_id, related_step)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                user_department,
                sop_id,
                category,
                difficulty,
                1 if is_correct else 0,
                source_id,
                related_step,
            ),
        )
        return cur.lastrowid


def count_correct_quizzes(
    user_id: str, *, difficulty: Optional[str] = None, db_path: Optional[Path] = None
) -> int:
    with get_conn(db_path) as conn:
        if difficulty:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM quiz_attempts WHERE user_id=? AND is_correct=1 AND difficulty=?",
                (user_id, difficulty),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM quiz_attempts WHERE user_id=? AND is_correct=1",
                (user_id,),
            ).fetchone()
        return row["n"] if row else 0


def count_total_quizzes(user_id: str, db_path: Optional[Path] = None) -> int:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM quiz_attempts WHERE user_id=?",
            (user_id,),
        ).fetchone()
        return row["n"] if row else 0


# ── sop_progress ───────────────────────────────────────────────


def record_sop_step(
    user_id: str, sop_id: str, step_number: int, completed_at: str = "", db_path: Optional[Path] = None
) -> None:
    """UPSERT 단계 완료."""
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO sop_progress (user_id, sop_id, step_number, completed_at)
               VALUES (?, ?, ?, COALESCE(NULLIF(?, ''), datetime('now','localtime')))""",
            (user_id, sop_id, step_number, completed_at),
        )


def count_completed_sops(user_id: str, total_steps_by_sop: dict[str, int], db_path: Optional[Path] = None) -> int:
    """전 단계 완료된 SOP 개수.

    total_steps_by_sop: {sop_id: total_step_count} — features.sop_guide.get_all_sops 에서 산출.
    """
    if not total_steps_by_sop:
        return 0
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """SELECT sop_id, COUNT(DISTINCT step_number) AS done_steps
               FROM sop_progress WHERE user_id=? GROUP BY sop_id""",
            (user_id,),
        ).fetchall()
    completed = 0
    for r in rows:
        sop_id = r["sop_id"]
        if sop_id in total_steps_by_sop and r["done_steps"] >= total_steps_by_sop[sop_id]:
            completed += 1
    return completed


def get_sop_progress(user_id: str, db_path: Optional[Path] = None) -> dict[str, list[int]]:
    """{sop_id: [step_number, ...]} 사용자별 완료 단계 매핑."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT sop_id, step_number FROM sop_progress WHERE user_id=?",
            (user_id,),
        ).fetchall()
    out: dict[str, list[int]] = {}
    for r in rows:
        out.setdefault(r["sop_id"], []).append(r["step_number"])
    return out


# ── user_badges ────────────────────────────────────────────────


def get_earned_badges(user_id: str, db_path: Optional[Path] = None) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT badge_id, earned_at, metadata FROM user_badges WHERE user_id=? ORDER BY earned_at DESC",
            (user_id,),
        ).fetchall()
    return [
        {"badge_id": r["badge_id"], "earned_at": r["earned_at"], "metadata": _safe_json(r["metadata"])}
        for r in rows
    ]


def persist_badge(
    user_id: str, badge_id: str, metadata: Optional[dict] = None, db_path: Optional[Path] = None
) -> bool:
    """배지 1건 INSERT OR IGNORE. Returns: True 신규 획득, False 이미 보유."""
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO user_badges (user_id, badge_id, earned_at, metadata)
               VALUES (?, ?, datetime('now','localtime'), ?)""",
            (user_id, badge_id, json.dumps(metadata or {}, ensure_ascii=False)),
        )
        return cur.rowcount > 0


# ── user_daily_activity ────────────────────────────────────────


def upsert_daily(user_id: str, *, field: str, delta: int = 1, user_department: str = "", db_path: Optional[Path] = None) -> None:
    """daily_activity 의 단일 카운터 증가. field 화이트리스트로 SQL injection 방어."""
    allowed = {"chat_count", "quiz_total", "quiz_correct", "sop_steps_completed", "positive_feedback", "glossary_lookups"}
    if field not in allowed:
        raise ValueError(f"unsupported field: {field}")
    with get_conn(db_path) as conn:
        # 1) ensure row
        conn.execute(
            """INSERT OR IGNORE INTO user_daily_activity (user_id, date, user_department)
               VALUES (?, date('now','localtime'), ?)""",
            (user_id, user_department),
        )
        # 2) delta — field 는 위 화이트리스트로 안전
        conn.execute(
            f"UPDATE user_daily_activity SET {field} = {field} + ?, user_department = COALESCE(NULLIF(user_department, ''), ?) "
            f"WHERE user_id=? AND date=date('now','localtime')",
            (delta, user_department, user_id),
        )


def count_streak_days(user_id: str, *, days_window: int = 30, db_path: Optional[Path] = None) -> int:
    """현재 연속 사용 일수 — 오늘 거꾸로 days_window 내 chat_count>0 연속 카운트."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """SELECT date FROM user_daily_activity
               WHERE user_id=? AND chat_count > 0
               ORDER BY date DESC
               LIMIT ?""",
            (user_id, days_window + 5),
        ).fetchall()
    if not rows:
        return 0
    # 오늘부터 거꾸로 연속 일수 카운트 (ISO date 형식 가정 YYYY-MM-DD)
    from datetime import datetime, timedelta

    dates = [r["date"] for r in rows]
    streak = 0
    cur_d = datetime.now().date()
    for d in dates:
        try:
            dt = datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            continue
        if dt == cur_d or dt == cur_d - timedelta(days=streak):
            if streak == 0 and dt == cur_d:
                streak = 1
            elif dt == cur_d - timedelta(days=streak):
                streak += 1
            else:
                continue
        else:
            break
    return streak


def get_positive_feedback_count(user_id: str, db_path: Optional[Path] = None) -> int:
    """피드백 누적 — feedback_db 가 별도 DB 라 user_daily_activity.positive_feedback 의 합으로 계산.

    피드백 → save_feedback 시 evaluate_badges 트리거에서 upsert_daily(positive_feedback) 가 일어남.
    """
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(positive_feedback),0) AS n FROM user_daily_activity WHERE user_id=?",
            (user_id,),
        ).fetchone()
    return row["n"] if row else 0


def get_glossary_lookup_count(user_id: str, db_path: Optional[Path] = None) -> int:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(glossary_lookups),0) AS n FROM user_daily_activity WHERE user_id=?",
            (user_id,),
        ).fetchone()
    return row["n"] if row else 0


# ── leaderboard ────────────────────────────────────────────────


def save_leaderboard_snapshot(
    dept: str, period: str, top_users: list[dict], db_path: Optional[Path] = None
) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO dept_leaderboard_snapshots (dept, period, top_users_json, computed_at)
               VALUES (?, ?, ?, datetime('now','localtime'))""",
            (dept, period, json.dumps(top_users, ensure_ascii=False)),
        )


def load_leaderboard_snapshot(dept: str, period: str, db_path: Optional[Path] = None) -> Optional[dict]:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT top_users_json, computed_at FROM dept_leaderboard_snapshots WHERE dept=? AND period=?",
            (dept, period),
        ).fetchone()
    if not row:
        return None
    return {
        "top_users": _safe_json(row["top_users_json"]),
        "computed_at": row["computed_at"],
    }


def get_dept_active_users(dept: str, since_days: int = 7, db_path: Optional[Path] = None) -> list[str]:
    """최근 N일 dept 내 활성 사용자 user_id 목록."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT user_id FROM user_daily_activity
               WHERE user_department=? AND date >= date('now','localtime', ?)""",
            (dept, f"-{since_days} days"),
        ).fetchall()
    return [r["user_id"] for r in rows]


# ── util ───────────────────────────────────────────────────────


def _safe_json(s: Any) -> Any:
    if not s:
        return {}
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return {}
