"""
에러 발생 이력 DB (v3.4)

에러코드별 과거 발생 이력을 저장하고 요약 통계를 제공한다.
- SQLite 기반 (data/equipment/error_history.db)
- 검색 결과에 "최근 3개월 발생 N회, 평균 복구 M분" 요약 표시에 사용
"""

from __future__ import annotations

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path


DB_PATH = Path("data/equipment/error_history.db")


class ErrorHistoryDB:
    """에러 발생 이력 관리"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DB_PATH)
        _dirname = os.path.dirname(self.db_path)
        if _dirname:
            os.makedirs(_dirname, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_code TEXT NOT NULL,
                    equipment_type TEXT NOT NULL,
                    equipment_id TEXT,
                    occurred_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolution_minutes INTEGER,
                    root_cause TEXT,
                    action_taken TEXT,
                    operator_name TEXT,
                    shift TEXT,
                    plant TEXT DEFAULT '경산본사',
                    severity TEXT DEFAULT 'MEDIUM',
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_eh_code ON error_history(error_code)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_eh_occurred ON error_history(occurred_at)")

    def add_record(self, error_code: str, equipment_type: str,
                   equipment_id: str = "", occurred_at: str = "",
                   resolved_at: str = "", resolution_minutes: int = 0,
                   root_cause: str = "", action_taken: str = "",
                   operator_name: str = "", shift: str = "",
                   plant: str = "경산본사", severity: str = "MEDIUM") -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("""
                INSERT INTO error_history
                (error_code, equipment_type, equipment_id, occurred_at,
                 resolved_at, resolution_minutes, root_cause, action_taken,
                 operator_name, shift, plant, severity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (error_code, equipment_type, equipment_id, occurred_at,
                  resolved_at, resolution_minutes, root_cause, action_taken,
                  operator_name, shift, plant, severity))
            return cur.lastrowid

    def get_summary(self, error_code: str, months: int = 3) -> dict:
        """에러코드별 요약 통계 (최근 N개월)"""
        cutoff = (datetime.now() - timedelta(days=months * 30)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute("""
                SELECT COUNT(*) as cnt, AVG(resolution_minutes) as avg_min,
                       MAX(occurred_at) as last_occurred
                FROM error_history
                WHERE error_code = ? AND occurred_at >= ?
            """, (error_code, cutoff)).fetchone()

            if not row or row["cnt"] == 0:
                return {"error_code": error_code, "total_count": 0,
                        "avg_resolution_min": 0, "last_occurred": None,
                        "top_causes": [], "trend": "none"}

            # TOP-3 원인
            causes = conn.execute("""
                SELECT root_cause, COUNT(*) as c FROM error_history
                WHERE error_code = ? AND occurred_at >= ? AND root_cause != ''
                GROUP BY root_cause ORDER BY c DESC LIMIT 3
            """, (error_code, cutoff)).fetchall()

            # 추세 (전반기 vs 후반기)
            mid = (datetime.now() - timedelta(days=months * 15)).isoformat()
            first = conn.execute(
                "SELECT COUNT(*) FROM error_history WHERE error_code=? AND occurred_at>=? AND occurred_at<?",
                (error_code, cutoff, mid)).fetchone()[0]
            second = conn.execute(
                "SELECT COUNT(*) FROM error_history WHERE error_code=? AND occurred_at>=?",
                (error_code, mid)).fetchone()[0]

            if second > first * 1.5:
                trend = "increasing"
            elif first > second * 1.5:
                trend = "decreasing"
            else:
                trend = "stable"

            return {
                "error_code": error_code,
                "total_count": row["cnt"],
                "avg_resolution_min": round(row["avg_min"] or 0),
                "last_occurred": row["last_occurred"],
                "top_causes": [r["root_cause"] for r in causes],
                "trend": trend,
            }

    def get_recent_records(self, error_code: str, limit: int = 5) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM error_history WHERE error_code = ?
                ORDER BY occurred_at DESC LIMIT ?
            """, (error_code, limit)).fetchall()
            return [dict(r) for r in rows]


# 싱글턴
_db_instance: Optional[ErrorHistoryDB] = None


def get_error_history_db() -> ErrorHistoryDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = ErrorHistoryDB()
    return _db_instance
