"""설비 점검 이력 DB — 일상/정기/특별 점검 체크리스트 + 이력 타임라인

점검 유형:
- daily: 일상 점검 (작업 시작 전)
- weekly: 주간 점검
- monthly: 월간 정기 점검
- special: 특별 점검 (사고/고장 후)

점검 결과:
- PASS: 전 항목 정상
- PARTIAL: 일부 항목 이상
- FAIL: 주요 항목 이상 (설비 가동 중단 필요)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

INSPECTION_DB_PATH = Path("data/equipment/inspection.db")


def init_inspection_db(db_path: Path = INSPECTION_DB_PATH) -> None:
    """점검 DB 초기화 + 템플릿 시딩"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS checklist_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            equipment_type TEXT NOT NULL,
            checklist_type TEXT NOT NULL DEFAULT 'daily',
            items_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS inspection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id TEXT NOT NULL,
            equipment_name TEXT NOT NULL DEFAULT '',
            template_id INTEGER,
            inspector TEXT DEFAULT '',
            inspection_date TEXT DEFAULT (date('now', 'localtime')),
            results_json TEXT DEFAULT '[]',
            overall_status TEXT DEFAULT 'PASS',
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (template_id) REFERENCES checklist_templates(id)
        );

        CREATE INDEX IF NOT EXISTS idx_inspection_equip
        ON inspection_logs(equipment_id, inspection_date DESC);

        CREATE INDEX IF NOT EXISTS idx_inspection_date
        ON inspection_logs(inspection_date DESC);
    """)

    # 템플릿이 없으면 시딩
    count = conn.execute("SELECT COUNT(*) FROM checklist_templates").fetchone()[0]
    if count == 0:
        _seed_templates(conn)

    conn.commit()
    conn.close()


def _seed_templates(conn: sqlite3.Connection) -> None:
    """장비별 점검 템플릿 시딩"""
    templates = [
        # 프레스 일상점검
        ("프레스 일상점검", "프레스", "daily", json.dumps([
            {"item": "유압 오일 레벨", "standard": "게이지 중앙 이상", "unit": ""},
            {"item": "유압 오일 온도", "standard": "40~60°C", "unit": "°C"},
            {"item": "냉각수 순환", "standard": "정상 순환", "unit": ""},
            {"item": "에어 압력", "standard": "5.0~6.0 kgf/cm²", "unit": "kgf/cm²"},
            {"item": "비상정지 버튼", "standard": "정상 작동", "unit": ""},
            {"item": "광커튼 센서", "standard": "정상 감지", "unit": ""},
            {"item": "금형 체결 상태", "standard": "볼트 토크 확인", "unit": ""},
            {"item": "슬라이드 가이드 윤활", "standard": "윤활유 도포", "unit": ""},
            {"item": "이물질/누유", "standard": "없음", "unit": ""},
            {"item": "소음/진동", "standard": "이상 없음", "unit": ""},
        ], ensure_ascii=False)),

        # 프레스 월간점검
        ("프레스 월간 정기점검", "프레스", "monthly", json.dumps([
            {"item": "유압 오일 교체/필터 점검", "standard": "교체주기 확인", "unit": ""},
            {"item": "실린더 씰 상태", "standard": "누유 없음", "unit": ""},
            {"item": "전기 배선 절연 저항", "standard": "1MΩ 이상", "unit": "MΩ"},
            {"item": "볼스터/슬라이드 평행도", "standard": "±0.05mm 이내", "unit": "mm"},
            {"item": "브레이크/클러치 마모", "standard": "마모한도 이내", "unit": "mm"},
            {"item": "카운터밸런스 압력", "standard": "설정값 ±5%", "unit": "kgf/cm²"},
        ], ensure_ascii=False)),

        # 용접기 일상점검
        ("용접기 일상점검", "용접기", "daily", json.dumps([
            {"item": "용접 전극 마모", "standard": "팁 직경 확인", "unit": "mm"},
            {"item": "냉각수 온도", "standard": "25~40°C", "unit": "°C"},
            {"item": "냉각수 유량", "standard": "정상 흐름", "unit": ""},
            {"item": "에어 압력", "standard": "5.0~6.0 kgf/cm²", "unit": "kgf/cm²"},
            {"item": "가압력", "standard": "설정값 ±10%", "unit": "kN"},
            {"item": "용접 전류/시간 설정", "standard": "WPS 기준값", "unit": ""},
            {"item": "케이블/호스 상태", "standard": "손상 없음", "unit": ""},
            {"item": "안전 커버/가드", "standard": "정상 장착", "unit": ""},
        ], ensure_ascii=False)),

        # 용접기 주간점검
        ("용접기 주간점검", "용접기", "weekly", json.dumps([
            {"item": "전극팁 드레싱", "standard": "팁 정형 실시", "unit": ""},
            {"item": "너겟 테스트", "standard": "규격 이내", "unit": "mm"},
            {"item": "가압 실린더 동작", "standard": "정상", "unit": ""},
            {"item": "트랜스포머 절연", "standard": "이상 없음", "unit": ""},
        ], ensure_ascii=False)),

        # 로봇 일상점검
        ("로봇 일상점검", "로봇", "daily", json.dumps([
            {"item": "원점 복귀 정상", "standard": "정상 동작", "unit": ""},
            {"item": "그리퍼 동작", "standard": "파지력 정상", "unit": ""},
            {"item": "케이블 드레스 상태", "standard": "간섭 없음", "unit": ""},
            {"item": "비상정지 기능", "standard": "정상 작동", "unit": ""},
            {"item": "에어 압력", "standard": "설정 범위", "unit": "kgf/cm²"},
            {"item": "이상 소음/진동", "standard": "없음", "unit": ""},
            {"item": "티칭 위치 확인", "standard": "편차 ±1mm 이내", "unit": "mm"},
        ], ensure_ascii=False)),

        # 로봇 월간점검
        ("로봇 월간 정기점검", "로봇", "monthly", json.dumps([
            {"item": "감속기 오일", "standard": "오일 레벨/변색 확인", "unit": ""},
            {"item": "각 축 백래시", "standard": "규격 이내", "unit": ""},
            {"item": "서보 모터 전류", "standard": "정격 범위", "unit": "A"},
            {"item": "엔코더 배터리", "standard": "전압 3.0V 이상", "unit": "V"},
            {"item": "제어기 팬/필터", "standard": "청소/교체", "unit": ""},
        ], ensure_ascii=False)),
    ]

    conn.executemany(
        """INSERT INTO checklist_templates
           (template_name, equipment_type, checklist_type, items_json)
           VALUES (?, ?, ?, ?)""",
        templates,
    )


def _get_conn(db_path: Path = INSPECTION_DB_PATH) -> sqlite3.Connection:
    init_inspection_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── 템플릿 조회 ──

def get_templates(
    equipment_type: str = "",
    checklist_type: str = "",
    db_path: Path = INSPECTION_DB_PATH,
) -> list[dict]:
    """점검 템플릿 조회"""
    conn = _get_conn(db_path)
    try:
        conditions = []
        params = []
        if equipment_type:
            conditions.append("equipment_type = ?")
            params.append(equipment_type)
        if checklist_type:
            conditions.append("checklist_type = ?")
            params.append(checklist_type)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM checklist_templates{where} ORDER BY equipment_type, checklist_type",
            params,
        ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            try:
                d["items"] = json.loads(d.get("items_json", "[]"))
            except (json.JSONDecodeError, TypeError):
                d["items"] = []
            result.append(d)
        return result
    finally:
        conn.close()


def get_template(template_id: int, db_path: Path = INSPECTION_DB_PATH) -> Optional[dict]:
    """특정 템플릿 상세"""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM checklist_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["items"] = json.loads(d.get("items_json", "[]"))
        return d
    finally:
        conn.close()


# ── 점검 기록 ──

def save_inspection(
    equipment_id: str,
    equipment_name: str,
    template_id: int,
    inspector: str,
    results: list[dict],
    overall_status: str = "PASS",
    note: str = "",
    inspection_date: str = "",
    db_path: Path = INSPECTION_DB_PATH,
) -> int:
    """점검 결과 저장

    Args:
        results: [{"item": str, "result": "OK"|"NG"|"NA", "measured_value": str, "note": str}, ...]
        overall_status: "PASS" | "PARTIAL" | "FAIL"

    Returns:
        inspection log id
    """
    conn = _get_conn(db_path)
    try:
        results_json = json.dumps(results, ensure_ascii=False)
        if not inspection_date:
            inspection_date = datetime.now().strftime("%Y-%m-%d")

        cur = conn.execute(
            """INSERT INTO inspection_logs
               (equipment_id, equipment_name, template_id, inspector,
                inspection_date, results_json, overall_status, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (equipment_id, equipment_name, template_id, inspector,
             inspection_date, results_json, overall_status, note),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_inspection_history(
    equipment_id: str = "",
    limit: int = 20,
    db_path: Path = INSPECTION_DB_PATH,
) -> list[dict]:
    """점검 이력 조회"""
    conn = _get_conn(db_path)
    try:
        if equipment_id:
            rows = conn.execute(
                """SELECT l.*, t.template_name, t.equipment_type, t.checklist_type
                   FROM inspection_logs l
                   LEFT JOIN checklist_templates t ON l.template_id = t.id
                   WHERE l.equipment_id = ?
                   ORDER BY l.inspection_date DESC, l.created_at DESC
                   LIMIT ?""",
                (equipment_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT l.*, t.template_name, t.equipment_type, t.checklist_type
                   FROM inspection_logs l
                   LEFT JOIN checklist_templates t ON l.template_id = t.id
                   ORDER BY l.inspection_date DESC, l.created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            try:
                d["results"] = json.loads(d.get("results_json", "[]"))
            except (json.JSONDecodeError, TypeError):
                d["results"] = []
            result.append(d)
        return result
    finally:
        conn.close()


def get_inspection_stats(db_path: Path = INSPECTION_DB_PATH) -> dict:
    """점검 통계"""
    conn = _get_conn(db_path)
    try:
        total_templates = conn.execute("SELECT COUNT(*) FROM checklist_templates").fetchone()[0]
        total_logs = conn.execute("SELECT COUNT(*) FROM inspection_logs").fetchone()[0]

        by_status = {}
        for row in conn.execute(
            "SELECT overall_status, COUNT(*) as cnt FROM inspection_logs GROUP BY overall_status"
        ):
            by_status[row["overall_status"]] = row["cnt"]

        by_type = {}
        for row in conn.execute(
            "SELECT equipment_type, COUNT(*) as cnt FROM checklist_templates GROUP BY equipment_type"
        ):
            by_type[row["equipment_type"]] = row["cnt"]

        return {
            "templates": total_templates,
            "inspections": total_logs,
            "by_status": by_status,
            "by_type": by_type,
        }
    finally:
        conn.close()
