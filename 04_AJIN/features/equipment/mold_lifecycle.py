"""
금형 수명 관리 DB — 타수 추적 + 불량률 기록 + 교체 예측
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

MOLD_DB_PATH = Path("data/equipment/mold_lifecycle.db")


def init_mold_db(db_path: Path = MOLD_DB_PATH) -> None:
    """금형 DB 초기화"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS molds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mold_id TEXT UNIQUE NOT NULL,
            mold_name TEXT NOT NULL,
            mold_type TEXT DEFAULT '',
            part_name TEXT DEFAULT '',
            part_number TEXT DEFAULT '',
            material TEXT DEFAULT '',
            max_shots INTEGER DEFAULT 0,
            current_shots INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            location TEXT DEFAULT '',
            last_maintenance TEXT,
            next_maintenance TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS mold_shot_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mold_id TEXT NOT NULL,
            shots_added INTEGER NOT NULL,
            defect_count INTEGER DEFAULT 0,
            defect_rate REAL DEFAULT 0.0,
            operator TEXT DEFAULT '',
            machine TEXT DEFAULT '',
            note TEXT DEFAULT '',
            logged_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (mold_id) REFERENCES molds(mold_id)
        );

        CREATE TABLE IF NOT EXISTS mold_maintenance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mold_id TEXT NOT NULL,
            maintenance_type TEXT NOT NULL,
            description TEXT DEFAULT '',
            cost REAL DEFAULT 0.0,
            performed_by TEXT DEFAULT '',
            performed_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (mold_id) REFERENCES molds(mold_id)
        );

        CREATE INDEX IF NOT EXISTS idx_mold_shots ON mold_shot_logs(mold_id, logged_at);
        CREATE INDEX IF NOT EXISTS idx_mold_maint ON mold_maintenance_logs(mold_id);
    """)
    conn.commit()
    conn.close()


def register_mold(
    mold_id: str, mold_name: str, max_shots: int,
    mold_type: str = "", part_name: str = "", part_number: str = "",
    material: str = "", location: str = "",
    db_path: Path = MOLD_DB_PATH,
) -> None:
    """금형 등록"""
    init_mold_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT OR REPLACE INTO molds
           (mold_id, mold_name, mold_type, part_name, part_number,
            material, max_shots, location)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (mold_id, mold_name, mold_type, part_name, part_number,
         material, max_shots, location),
    )
    conn.commit()
    conn.close()


def add_shot_log(
    mold_id: str, shots: int,
    defect_count: int = 0, operator: str = "", machine: str = "", note: str = "",
    db_path: Path = MOLD_DB_PATH,
) -> dict:
    """타수 기록 추가. Returns: 업데이트된 금형 상태"""
    init_mold_db(db_path)
    conn = sqlite3.connect(str(db_path))

    defect_rate = round(defect_count / shots * 100, 2) if shots > 0 else 0

    conn.execute(
        """INSERT INTO mold_shot_logs
           (mold_id, shots_added, defect_count, defect_rate, operator, machine, note)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (mold_id, shots, defect_count, defect_rate, operator, machine, note),
    )

    conn.execute(
        """UPDATE molds
           SET current_shots = current_shots + ?,
               updated_at = datetime('now', 'localtime')
           WHERE mold_id = ?""",
        (shots, mold_id),
    )

    conn.commit()
    conn.close()

    return get_mold(mold_id, db_path)


def get_mold(mold_id: str, db_path: Path = MOLD_DB_PATH) -> Optional[dict]:
    """금형 상태 조회"""
    init_mold_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM molds WHERE mold_id = ?", (mold_id,)).fetchone()
    conn.close()
    if not row:
        return None
    mold = dict(row)
    mold["life_percent"] = round(mold["current_shots"] / mold["max_shots"] * 100, 1) if mold["max_shots"] > 0 else 0
    mold["remaining_shots"] = max(0, mold["max_shots"] - mold["current_shots"])
    return mold


def get_all_molds(status: str = None, db_path: Path = MOLD_DB_PATH) -> list[dict]:
    """전체 금형 목록"""
    init_mold_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    if status:
        rows = conn.execute("SELECT * FROM molds WHERE status = ? ORDER BY mold_id", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM molds ORDER BY mold_id").fetchall()
    conn.close()

    molds = []
    for r in rows:
        m = dict(r)
        m["life_percent"] = round(m["current_shots"] / m["max_shots"] * 100, 1) if m["max_shots"] > 0 else 0
        m["remaining_shots"] = max(0, m["max_shots"] - m["current_shots"])
        molds.append(m)
    return molds


def get_shot_history(mold_id: str, limit: int = 50, db_path: Path = MOLD_DB_PATH) -> list[dict]:
    """타수 이력 조회"""
    init_mold_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM mold_shot_logs WHERE mold_id = ? ORDER BY logged_at DESC LIMIT ?",
        (mold_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_maintenance_history(mold_id: str, limit: int = 20, db_path: Path = MOLD_DB_PATH) -> list[dict]:
    """정비 이력 조회"""
    init_mold_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM mold_maintenance_logs WHERE mold_id = ? ORDER BY performed_at DESC LIMIT ?",
        (mold_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_maintenance_log(
    mold_id: str, maintenance_type: str, description: str = "",
    cost: float = 0.0, performed_by: str = "",
    db_path: Path = MOLD_DB_PATH,
) -> None:
    """정비 이력 추가"""
    init_mold_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO mold_maintenance_logs
           (mold_id, maintenance_type, description, cost, performed_by)
           VALUES (?, ?, ?, ?, ?)""",
        (mold_id, maintenance_type, description, cost, performed_by),
    )
    conn.execute(
        """UPDATE molds
           SET last_maintenance = datetime('now', 'localtime'),
               updated_at = datetime('now', 'localtime')
           WHERE mold_id = ?""",
        (mold_id,),
    )
    conn.commit()
    conn.close()


def predict_replacement_date(
    mold_id: str, db_path: Path = MOLD_DB_PATH,
) -> Optional[dict]:
    """금형 교체 시기를 과거 타수 데이터 기반으로 예측합니다."""
    mold = get_mold(mold_id, db_path)
    if not mold:
        return None

    history = get_shot_history(mold_id, limit=30, db_path=db_path)
    if len(history) < 3:
        return {"prediction": "데이터 부족 (최소 3건 필요)", "confidence": "low"}

    total_shots = sum(h["shots_added"] for h in history)
    first_log = history[-1]["logged_at"][:10]
    last_log = history[0]["logged_at"][:10]

    try:
        first_date = datetime.strptime(first_log, "%Y-%m-%d")
        last_date = datetime.strptime(last_log, "%Y-%m-%d")
        days = (last_date - first_date).days or 1
    except ValueError:
        days = len(history)

    daily_avg = total_shots / days if days > 0 else 0

    if daily_avg <= 0:
        return {"prediction": "타수 증가 없음", "confidence": "low"}

    remaining = mold["remaining_shots"]
    days_remaining = int(remaining / daily_avg)
    predicted_date = datetime.now() + timedelta(days=days_remaining)

    recent_defect_rates = [h["defect_rate"] for h in history[:10] if h["defect_rate"] > 0]
    avg_defect_rate = sum(recent_defect_rates) / len(recent_defect_rates) if recent_defect_rates else 0

    return {
        "mold_id": mold_id,
        "current_shots": mold["current_shots"],
        "max_shots": mold["max_shots"],
        "life_percent": mold["life_percent"],
        "remaining_shots": remaining,
        "daily_avg_shots": round(daily_avg),
        "days_remaining": days_remaining,
        "predicted_date": predicted_date.strftime("%Y-%m-%d"),
        "avg_defect_rate": round(avg_defect_rate, 2),
        "confidence": "high" if len(history) >= 10 else "medium",
        "warning": "수명 80% 초과" if mold["life_percent"] >= 80 else "",
    }


def get_mold_stats(db_path: Path = MOLD_DB_PATH) -> dict:
    """금형 DB 통계"""
    init_mold_db(db_path)
    conn = sqlite3.connect(str(db_path))
    total = conn.execute("SELECT COUNT(*) FROM molds").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM molds WHERE status = 'active'").fetchone()[0]
    warning = conn.execute("SELECT COUNT(*) FROM molds WHERE current_shots >= max_shots * 0.8 AND status = 'active'").fetchone()[0]
    conn.close()
    return {"total": total, "active": active, "warning_80pct": warning}
