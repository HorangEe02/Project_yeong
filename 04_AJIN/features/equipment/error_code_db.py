"""
설비 에러코드 사전 — 에러코드 입력 시 즉시 원인/조치 방법 반환
RAG 검색보다 빠른 직접 조회 경로 (O(1) lookup)
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ERROR_DB_PATH = Path("data/equipment/error_codes.db")


def init_error_db(db_path: Path = ERROR_DB_PATH) -> None:
    """에러코드 DB 초기화"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS error_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_type TEXT NOT NULL,
            equipment_model TEXT DEFAULT '',
            error_code TEXT NOT NULL,
            error_name TEXT NOT NULL,
            severity TEXT DEFAULT 'warning',
            cause TEXT NOT NULL,
            action TEXT NOT NULL,
            prevention TEXT DEFAULT '',
            reference_page TEXT DEFAULT '',
            language TEXT DEFAULT 'ko',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_error_code
        ON error_codes(error_code);

        CREATE INDEX IF NOT EXISTS idx_error_equip
        ON error_codes(equipment_type, error_code);
    """)
    conn.commit()
    conn.close()


def lookup_error(
    error_code: str,
    equipment_type: str = None,
    db_path: Path = ERROR_DB_PATH,
) -> list[dict]:
    """
    에러코드로 직접 조회합니다.

    Args:
        error_code: 에러코드 (예: "E-001", "ALM-012")
        equipment_type: 설비 유형 (선택, 예: "프레스", "용접기")

    Returns:
        매칭된 에러코드 정보 리스트
    """
    init_error_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    code_upper = error_code.strip().upper()

    if equipment_type:
        rows = conn.execute(
            """SELECT * FROM error_codes
               WHERE UPPER(error_code) = ? AND equipment_type = ?""",
            (code_upper, equipment_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM error_codes WHERE UPPER(error_code) = ?",
            (code_upper,),
        ).fetchall()

    # 부분 매칭 폴백
    if not rows:
        rows = conn.execute(
            "SELECT * FROM error_codes WHERE UPPER(error_code) LIKE ?",
            (f"%{code_upper}%",),
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def add_error_code(
    equipment_type: str,
    error_code: str,
    error_name: str,
    cause: str,
    action: str,
    severity: str = "warning",
    equipment_model: str = "",
    prevention: str = "",
    reference_page: str = "",
    language: str = "ko",
    db_path: Path = ERROR_DB_PATH,
) -> int:
    """에러코드 1건 등록. Returns: ID"""
    init_error_db(db_path)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        """INSERT INTO error_codes
           (equipment_type, equipment_model, error_code, error_name,
            severity, cause, action, prevention, reference_page, language)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (equipment_type, equipment_model, error_code.upper(), error_name,
         severity, cause, action, prevention, reference_page, language),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def bulk_import_from_json(
    json_path: str,
    db_path: Path = ERROR_DB_PATH,
) -> int:
    """JSON 파일에서 에러코드를 일괄 임포트합니다."""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    count = 0

    for item in data:
        try:
            add_error_code(
                equipment_type=item.get("equipment_type", ""),
                error_code=item.get("error_code", ""),
                error_name=item.get("error_name", ""),
                cause=item.get("cause", ""),
                action=item.get("action", ""),
                severity=item.get("severity", "warning"),
                equipment_model=item.get("equipment_model", ""),
                prevention=item.get("prevention", ""),
                reference_page=item.get("reference_page", ""),
                language=item.get("language", "ko"),
                db_path=db_path,
            )
            count += 1
        except Exception as e:
            logger.warning(f"에러코드 임포트 실패: {e}")

    return count


def get_equipment_types(db_path: Path = ERROR_DB_PATH) -> list[str]:
    """등록된 설비 유형 목록"""
    init_error_db(db_path)
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT DISTINCT equipment_type FROM error_codes ORDER BY equipment_type"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def search_errors(
    keyword: str,
    equipment_type: str = None,
    limit: int = 20,
    db_path: Path = ERROR_DB_PATH,
) -> list[dict]:
    """키워드로 에러코드/원인/조치 검색"""
    init_error_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    like_val = f"%{keyword}%"

    if equipment_type:
        rows = conn.execute(
            """SELECT * FROM error_codes
               WHERE equipment_type = ?
                 AND (error_code LIKE ? OR error_name LIKE ?
                      OR cause LIKE ? OR action LIKE ?)
               LIMIT ?""",
            (equipment_type, like_val, like_val, like_val, like_val, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM error_codes
               WHERE error_code LIKE ? OR error_name LIKE ?
                     OR cause LIKE ? OR action LIKE ?
               LIMIT ?""",
            (like_val, like_val, like_val, like_val, limit),
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def get_error_stats(db_path: Path = ERROR_DB_PATH) -> dict:
    """에러코드 DB 통계"""
    init_error_db(db_path)
    conn = sqlite3.connect(str(db_path))
    total = conn.execute("SELECT COUNT(*) FROM error_codes").fetchone()[0]
    by_type = conn.execute(
        "SELECT equipment_type, COUNT(*) FROM error_codes GROUP BY equipment_type"
    ).fetchall()
    by_severity = conn.execute(
        "SELECT severity, COUNT(*) FROM error_codes GROUP BY severity"
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "by_type": {r[0]: r[1] for r in by_type},
        "by_severity": {r[0]: r[1] for r in by_severity},
    }
