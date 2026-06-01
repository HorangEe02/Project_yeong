"""scenarios.db 초기화 + 시드 마이그레이션.

기존 features/onboarding/collaboration_guide.py 의 COLLABORATION_SCENARIOS 5종을
DB 의 collaboration_scenarios 테이블로 이관 (is_system_default=1).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

SCENARIOS_DB_PATH = Path(__file__).parent.parent.parent / "data" / "scenarios.db"


def get_scenarios_db() -> sqlite3.Connection:
    """scenarios.db 연결을 반환한다."""
    SCENARIOS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SCENARIOS_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_scenarios_db() -> None:
    """scenarios.db 스키마를 초기화하고 (없으면) 시드 5종을 적재한다."""
    conn = get_scenarios_db()

    conn.executescript("""
    -- ── Phase 1 ───────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS collaboration_scenarios (
        scenario_id        TEXT PRIMARY KEY,
        is_system_default  INTEGER NOT NULL DEFAULT 0,
        trigger_keywords   TEXT NOT NULL DEFAULT '[]',
        situation          TEXT NOT NULL DEFAULT '',
        requesting_dept    TEXT NOT NULL DEFAULT '',
        my_actions         TEXT NOT NULL DEFAULT '[]',
        hand_off_to        TEXT NOT NULL DEFAULT '',
        hand_off_items     TEXT NOT NULL DEFAULT '[]',
        deadline_info      TEXT NOT NULL DEFAULT '',
        related_sop_id     TEXT NOT NULL DEFAULT '',
        tips               TEXT NOT NULL DEFAULT '[]',
        priority           INTEGER NOT NULL DEFAULT 100,
        scope_division     TEXT NOT NULL DEFAULT '',
        lang               TEXT NOT NULL DEFAULT 'ko',
        created_by         TEXT NOT NULL DEFAULT '',
        updated_by         TEXT NOT NULL DEFAULT '',
        created_at         TEXT DEFAULT (datetime('now')),
        updated_at         TEXT DEFAULT (datetime('now')),
        is_active          INTEGER NOT NULL DEFAULT 1
    );

    CREATE INDEX IF NOT EXISTS idx_scenarios_active
      ON collaboration_scenarios(is_active, scope_division, lang);

    CREATE TABLE IF NOT EXISTS scenario_history (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        scenario_id   TEXT NOT NULL,
        action        TEXT NOT NULL,
        changed_by    TEXT NOT NULL DEFAULT '',
        changed_at    TEXT DEFAULT (datetime('now')),
        before_json   TEXT NOT NULL DEFAULT '',
        after_json    TEXT NOT NULL DEFAULT ''
    );

    CREATE INDEX IF NOT EXISTS idx_history_scenario
      ON scenario_history(scenario_id, changed_at DESC);

    -- ── Phase 3 ───────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS scenario_favorites (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id   TEXT NOT NULL,
        scenario_id   TEXT NOT NULL,
        note          TEXT NOT NULL DEFAULT '',
        created_at    TEXT DEFAULT (datetime('now')),
        UNIQUE(employee_id, scenario_id)
    );

    CREATE TABLE IF NOT EXISTS scenario_usage (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        scenario_id   TEXT NOT NULL,
        matched_by    TEXT NOT NULL DEFAULT '',
        matched_at    TEXT DEFAULT (datetime('now')),
        query_text    TEXT NOT NULL DEFAULT ''
    );

    CREATE INDEX IF NOT EXISTS idx_usage_scenario
      ON scenario_usage(scenario_id, matched_at DESC);
    """)
    conn.commit()
    conn.close()

    seed_default_scenarios()


def seed_default_scenarios() -> int:
    """collaboration_guide.py 의 5종을 DB 에 INSERT (이미 있으면 skip)."""
    from features.onboarding.collaboration_guide import COLLABORATION_SCENARIOS

    conn = get_scenarios_db()
    inserted = 0

    for sc in COLLABORATION_SCENARIOS:
        existing = conn.execute(
            "SELECT 1 FROM collaboration_scenarios WHERE scenario_id = ?",
            (sc.id,),
        ).fetchone()
        if existing:
            continue

        conn.execute(
            """INSERT INTO collaboration_scenarios
                 (scenario_id, is_system_default, trigger_keywords, situation,
                  requesting_dept, my_actions, hand_off_to, hand_off_items,
                  deadline_info, related_sop_id, tips, priority,
                  scope_division, lang, created_by, updated_by, is_active)
               VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 100, '', 'ko', 'system', 'system', 1)""",
            (
                sc.id,
                json.dumps(sc.trigger_keywords, ensure_ascii=False),
                sc.situation,
                sc.requesting_dept,
                json.dumps(sc.my_actions, ensure_ascii=False),
                sc.hand_off_to,
                json.dumps(sc.hand_off_items, ensure_ascii=False),
                sc.deadline_info,
                sc.related_sop_id,
                json.dumps(sc.tips, ensure_ascii=False),
            ),
        )
        inserted += 1

    if inserted:
        logger.info("scenarios.db: seeded %d default scenarios", inserted)
    conn.commit()
    conn.close()
    return inserted
