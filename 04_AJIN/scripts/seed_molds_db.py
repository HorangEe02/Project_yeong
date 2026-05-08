"""data/equipment/molds.db 시드 — 25기 금형 자산.

PLANT 분포: KS-HQ 12기, KS-2 5기, GJ 8기
종류: 프레스 / 사출 / 금형정비 / 단조

사용:
  python scripts/seed_molds_db.py
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import random

DB_PATH = Path(__file__).parent.parent / "data" / "equipment" / "molds.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS molds (
    mold_id              TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    model                TEXT,
    plant_id             TEXT NOT NULL,
    type                 TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'active',
    last_pm_date         TEXT,
    next_pm_date         TEXT,
    expected_lifecycle   INTEGER DEFAULT 1000000,
    current_shots        INTEGER DEFAULT 0,
    health_score         REAL DEFAULT 100.0,
    created_at           TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_plant ON molds(plant_id);
CREATE INDEX IF NOT EXISTS idx_status ON molds(status);
"""

MOLDS = [
    # PLANT-KS-HQ — 프레스 라인 + 조립 (12기)
    ("MOLD-KS-HQ-001", "쿼터 패널 LH 프레스 금형", "PRS-A1", "PLANT-KS-HQ", "프레스",  "active",   "2026-03-15", "2026-09-15"),
    ("MOLD-KS-HQ-002", "쿼터 패널 RH 프레스 금형", "PRS-A1", "PLANT-KS-HQ", "프레스",  "active",   "2026-03-15", "2026-09-15"),
    ("MOLD-KS-HQ-003", "대시 패널 컴플 금형",        "PRS-B2", "PLANT-KS-HQ", "프레스",  "active",   "2026-02-20", "2026-08-20"),
    ("MOLD-KS-HQ-004", "리어 플로어 컴플 금형",     "PRS-B2", "PLANT-KS-HQ", "프레스",  "active",   "2026-02-20", "2026-08-20"),
    ("MOLD-KS-HQ-005", "리어 패키지 트레이 금형",   "PRS-C3", "PLANT-KS-HQ", "프레스",  "active",   "2026-04-01", "2026-10-01"),
    ("MOLD-KS-HQ-006", "프론트 사이드 멤버 금형",   "PRS-C3", "PLANT-KS-HQ", "프레스",  "active",   "2026-04-01", "2026-10-01"),
    ("MOLD-KS-HQ-007", "B 필러 강화재 금형",        "PRS-D4", "PLANT-KS-HQ", "프레스",  "maintenance", "2026-04-15", "2026-10-15"),
    ("MOLD-KS-HQ-008", "도어 인너 패널 금형",       "PRS-D4", "PLANT-KS-HQ", "프레스",  "active",   "2026-03-25", "2026-09-25"),
    ("MOLD-KS-HQ-009", "후드 어셈블리 금형",        "PRS-E5", "PLANT-KS-HQ", "프레스",  "active",   "2026-03-30", "2026-09-30"),
    ("MOLD-KS-HQ-010", "트렁크 패널 금형",          "PRS-E5", "PLANT-KS-HQ", "프레스",  "active",   "2026-04-05", "2026-10-05"),
    ("MOLD-KS-HQ-011", "사이드 실 금형",            "PRS-F6", "PLANT-KS-HQ", "프레스",  "active",   "2026-04-10", "2026-10-10"),
    ("MOLD-KS-HQ-012", "범퍼 빔 보강재 금형",       "PRS-F6", "PLANT-KS-HQ", "프레스",  "active",   "2026-04-12", "2026-10-12"),

    # PLANT-KS-2 — 카울 멤버 라인 (5기)
    ("MOLD-KS-2-001",  "카울 멤버 메인 금형",       "PRS-G7", "PLANT-KS-2",  "프레스",  "active",   "2026-03-10", "2026-09-10"),
    ("MOLD-KS-2-002",  "카울 사이드 보강 금형",     "PRS-G7", "PLANT-KS-2",  "프레스",  "active",   "2026-03-10", "2026-09-10"),
    ("MOLD-KS-2-003",  "카울 크로스 멤버 금형",     "PRS-H8", "PLANT-KS-2",  "프레스",  "active",   "2026-03-22", "2026-09-22"),
    ("MOLD-KS-2-004",  "카울 사이드 LH 금형",        "PRS-H8", "PLANT-KS-2",  "프레스",  "maintenance", "2026-04-18", "2026-10-18"),
    ("MOLD-KS-2-005",  "카울 사이드 RH 금형",        "PRS-H8", "PLANT-KS-2",  "프레스",  "active",   "2026-04-20", "2026-10-20"),

    # PLANT-GJ — 차체 보강 패널 (8기)
    ("MOLD-GJ-001",    "프론트 휠 하우스 금형",     "PRS-J9",  "PLANT-GJ",    "프레스",  "active",   "2026-03-05", "2026-09-05"),
    ("MOLD-GJ-002",    "리어 휠 하우스 금형",       "PRS-J9",  "PLANT-GJ",    "프레스",  "active",   "2026-03-05", "2026-09-05"),
    ("MOLD-GJ-003",    "센터 필러 보강 금형",       "PRS-K10", "PLANT-GJ",    "프레스",  "active",   "2026-04-02", "2026-10-02"),
    ("MOLD-GJ-004",    "프론트 라디에이터 서포트", "PRS-K10", "PLANT-GJ",    "프레스",  "active",   "2026-04-02", "2026-10-02"),
    ("MOLD-GJ-005",    "리어 사이드 패널 금형",     "PRS-L11", "PLANT-GJ",    "프레스",  "active",   "2026-03-28", "2026-09-28"),
    ("MOLD-GJ-006",    "사이드 멤버 강화재 금형",   "PRS-L11", "PLANT-GJ",    "프레스",  "retired",  "2026-01-15", None),
    ("MOLD-GJ-007",    "범퍼 백빔 금형",            "PRS-M12", "PLANT-GJ",    "프레스",  "active",   "2026-04-08", "2026-10-08"),
    ("MOLD-GJ-008",    "도어 빔 강화재 금형",       "PRS-M12", "PLANT-GJ",    "프레스",  "active",   "2026-04-08", "2026-10-08"),
]


def seed():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA)

    rng = random.Random(42)  # 결정적
    inserted = 0

    for row in MOLDS:
        mold_id, name, model, plant, mtype, status, last_pm, next_pm = row
        # 결정적이지만 그럴듯한 health/shots
        shots = rng.randint(50_000, 850_000)
        health = round(100.0 - (shots / 1_000_000) * 30.0, 1)  # 70~100 사이

        conn.execute(
            """INSERT OR REPLACE INTO molds
               (mold_id, name, model, plant_id, type, status,
                last_pm_date, next_pm_date, expected_lifecycle, current_shots, health_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mold_id, name, model, plant, mtype, status,
             last_pm, next_pm, 1_000_000, shots, health),
        )
        inserted += 1

    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM molds").fetchone()[0]
    by_plant = list(conn.execute(
        "SELECT plant_id, COUNT(*) FROM molds GROUP BY plant_id ORDER BY plant_id"
    ))
    by_status = list(conn.execute(
        "SELECT status, COUNT(*) FROM molds GROUP BY status"
    ))
    conn.close()

    print(f"✓ {DB_PATH} 시드 완료")
    print(f"  inserted: {inserted}, total: {n}")
    print(f"  by plant: {by_plant}")
    print(f"  by status: {by_status}")


if __name__ == "__main__":
    seed()
