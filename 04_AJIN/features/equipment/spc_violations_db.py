"""v4.7 Sprint 2 P0 (축 ③) — SPC 위반 영속화 (미니 버전).

본 모듈은 spc_realtime 의 enrich_violations() 가 생성한 NelsonViolation 결과를
data/spc_violations.db SQLite 에 영속하여, 후속 처리(메일 초안 prefill, 통계,
GS-SLA 측정 등)에서 위반 1건을 ID 로 조회 가능하게 한다.

스키마는 액션 3 트랙 A(plc_ingest 본격 도입)가 들어와도 호환되도록 컬럼만
정의 — INSERT 는 본 PR 에서는 spc_realtime 의 alarm push 시점에 함께 호출.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.data_lineage import ensure_lineage_columns, lineage_values

DB_PATH = Path(__file__).parent.parent.parent / "data" / "spc_violations.db"


def _ensure_parent() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    _ensure_parent()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """멱등 스키마 초기화. 본 PR 에서 도입한 미니 영속 — 액션 3 트랙 A 흡수 호환."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS spc_violations (
              id TEXT PRIMARY KEY,
              process TEXT NOT NULL,
              lot_id TEXT NOT NULL,
              rule_number INTEGER NOT NULL,
              rule_name TEXT NOT NULL,
              violating_count INTEGER NOT NULL,
              severity TEXT NOT NULL,
              recommended_action TEXT NOT NULL,
              detected_at TEXT NOT NULL,
              alarm_id TEXT,
              draft_created INTEGER DEFAULT 0,
              draft_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_spc_violations_detected_at
              ON spc_violations(detected_at);
            CREATE INDEX IF NOT EXISTS idx_spc_violations_process
              ON spc_violations(process);
            """
        )
        ensure_lineage_columns(conn, "spc_violations")
        lineage = lineage_values("real", "plc_ingest", "plc_ingest")
        conn.execute(
            """UPDATE spc_violations
                  SET data_class = ?,
                      source_system = ?,
                      source_label = ?,
                      source_updated_at = ?
                WHERE data_class IS NULL OR data_class = '' OR data_class = 'unknown'""",
            (
                lineage["data_class"],
                lineage["source_system"],
                lineage["source_label"],
                lineage["source_updated_at"],
            ),
        )
        conn.commit()


def insert_violation(
    violation_id: str,
    process: str,
    lot_id: str,
    rule_number: int,
    rule_name: str,
    violating_count: int,
    severity: str,
    recommended_action: str,
    detected_at: str | None = None,
    alarm_id: str | None = None,
    data_class: str = "real",
    source_system: str = "plc_ingest",
    source_label: str = "plc_ingest",
) -> str:
    """위반 1건을 INSERT. 동일 id 면 무시(INSERT OR IGNORE).

    Returns: 입력된 violation_id.
    """
    init_db()
    detected = detected_at or datetime.now(timezone.utc).isoformat()
    lineage = lineage_values(data_class, source_system, source_label)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO spc_violations
              (id, process, lot_id, rule_number, rule_name, violating_count,
               severity, recommended_action, detected_at, alarm_id,
               data_class, source_system, source_label, source_updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                violation_id,
                process,
                lot_id,
                int(rule_number),
                rule_name,
                int(violating_count),
                severity,
                recommended_action,
                detected,
                alarm_id,
                lineage["data_class"],
                lineage["source_system"],
                lineage["source_label"],
                lineage["source_updated_at"],
            ),
        )
        conn.commit()
    return violation_id


def get_by_id(violation_id: str) -> dict[str, Any] | None:
    """ID 로 위반 1건 조회. 없으면 None."""
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM spc_violations WHERE id = ?", (violation_id,)
        ).fetchone()
    return dict(row) if row else None


def mark_draft_created(violation_id: str, draft_id: str) -> None:
    """메일 초안 발송이 완료되면 draft_created=1 + draft_id 기록."""
    init_db()
    with get_conn() as conn:
        conn.execute(
            "UPDATE spc_violations SET draft_created = 1, draft_id = ? WHERE id = ?",
            (draft_id, violation_id),
        )
        conn.commit()


def list_recent(limit: int = 20) -> list[dict[str, Any]]:
    """최근 위반 N건."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM spc_violations ORDER BY detected_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]
