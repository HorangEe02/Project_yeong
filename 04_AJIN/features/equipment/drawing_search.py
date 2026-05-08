"""도면/BOM 검색 DB — 도면번호, 부품번호, 자연어 키워드 검색

아진산업 주력 제품(EWP, CCH, OBC, BMS 등)의 도면 메타데이터를
SQLite에 저장하고 다양한 방식으로 검색한다.

검색 모드:
1. 정확 매칭: 도면번호/부품번호로 O(1) 조회
2. 키워드 검색: 부품명/설명에서 LIKE 검색
3. 필터: 장비유형, 공정, 부서별 필터링
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DRAWING_DB_PATH = Path("data/equipment/drawings.db")


def init_drawing_db(db_path: Path = DRAWING_DB_PATH) -> None:
    """도면 DB 초기화 + 샘플 시딩"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS drawings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drawing_number TEXT NOT NULL,
            part_number TEXT NOT NULL DEFAULT '',
            part_name TEXT NOT NULL,
            revision TEXT DEFAULT 'A',
            equipment_type TEXT DEFAULT '',
            material TEXT DEFAULT '',
            process_type TEXT DEFAULT '',
            department TEXT DEFAULT '',
            file_path TEXT DEFAULT '',
            description TEXT DEFAULT '',
            bom_info TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_drawing_number ON drawings(drawing_number);
        CREATE INDEX IF NOT EXISTS idx_part_number ON drawings(part_number);
        CREATE INDEX IF NOT EXISTS idx_equipment_type ON drawings(equipment_type);
    """)

    # 데이터가 없으면 샘플 시딩
    count = conn.execute("SELECT COUNT(*) FROM drawings").fetchone()[0]
    if count == 0:
        _seed_sample_data(conn)

    conn.commit()
    conn.close()


def _seed_sample_data(conn: sqlite3.Connection) -> None:
    """아진산업 주력 제품 도면 샘플 15건"""
    samples = [
        # EWP (전동워터펌프)
        ("DWG-EWP-001", "AJ-EWP-H100", "EWP 하우징 상부", "C", "프레스", "AL6061-T6", "다이캐스팅", "부품개발팀",
         "drawings/ewp/housing_upper.pdf", "전동워터펌프 상부 하우징 — 냉각수 유입/배출 포트 포함",
         '{"parent": "AJ-EWP-ASS-001", "quantity": 1}'),
        ("DWG-EWP-002", "AJ-EWP-H200", "EWP 하우징 하부", "B", "프레스", "AL6061-T6", "다이캐스팅", "부품개발팀",
         "drawings/ewp/housing_lower.pdf", "전동워터펌프 하부 하우징 — 모터 마운팅 면 포함",
         '{"parent": "AJ-EWP-ASS-001", "quantity": 1}'),
        ("DWG-EWP-003", "AJ-EWP-IMP-01", "EWP 임펠러", "D", "프레스", "PPS-GF40", "사출성형", "부품개발팀",
         "drawings/ewp/impeller.pdf", "워터펌프 임펠러 — 7엽 날개",
         '{"parent": "AJ-EWP-ASS-001", "quantity": 1}'),
        # CCH (냉각채널)
        ("DWG-CCH-001", "AJ-CCH-P100", "CCH 냉각 플레이트", "B", "프레스", "AL3003", "프레스", "생산기술팀",
         "drawings/cch/cooling_plate.pdf", "배터리 모듈 하부 냉각 플레이트",
         '{"parent": "AJ-CCH-ASS-001", "quantity": 2}'),
        ("DWG-CCH-002", "AJ-CCH-M100", "CCH 매니폴드", "A", "프레스", "AL6063", "압출+가공", "생산기술팀",
         "drawings/cch/manifold.pdf", "냉각수 분배 매니폴드 — 4포트",
         '{"parent": "AJ-CCH-ASS-001", "quantity": 1}'),
        # OBC (온보드 차저)
        ("DWG-OBC-001", "AJ-OBC-C100", "OBC 케이스 상부", "B", "프레스", "SPCC", "프레스", "생산기술팀",
         "drawings/obc/case_upper.pdf", "온보드 차저 상부 케이스 — EMI 차폐",
         '{"parent": "AJ-OBC-ASS-001", "quantity": 1}'),
        ("DWG-OBC-002", "AJ-OBC-C200", "OBC 케이스 하부", "B", "프레스", "SPCC", "프레스", "생산기술팀",
         "drawings/obc/case_lower.pdf", "온보드 차저 하부 케이스 — 방열핀 일체형",
         '{"parent": "AJ-OBC-ASS-001", "quantity": 1}'),
        # BMS (배터리관리시스템)
        ("DWG-BMS-001", "AJ-BMS-BR100", "BMS 브라켓", "A", "프레스", "SPHC", "프레스", "부품개발팀",
         "drawings/bms/bracket.pdf", "BMS 모듈 장착 브라켓",
         '{"parent": "AJ-BMS-ASS-001", "quantity": 4}'),
        # 범퍼/외장
        ("DWG-BMP-001", "AJ-BMP-F100", "프론트 범퍼 빔", "C", "프레스", "SAPH440", "프레스+용접", "생산기술팀",
         "drawings/bumper/front_beam.pdf", "프론트 범퍼 빔 — 충돌 흡수 구조",
         '{"parent": "AJ-BMP-ASS-001", "quantity": 1}'),
        ("DWG-BMP-002", "AJ-BMP-R100", "리어 범퍼 빔", "B", "프레스", "SAPH440", "프레스+용접", "생산기술팀",
         "drawings/bumper/rear_beam.pdf", "리어 범퍼 빔 — 견인 후크 마운팅",
         '{"parent": "AJ-BMP-ASS-001", "quantity": 1}'),
        # 서브프레임
        ("DWG-SUB-001", "AJ-SUB-F100", "프론트 서브프레임", "D", "용접기", "SPFH590", "프레스+MAG용접", "생산기술팀",
         "drawings/subframe/front.pdf", "프론트 서브프레임 — 조향장치 마운팅",
         '{"parent": "AJ-SUB-ASS-001", "quantity": 1}'),
        # 시트 부품
        ("DWG-SIT-001", "AJ-SIT-R100", "시트 레일", "A", "프레스", "SAPH440", "프레스", "생산기술팀",
         "drawings/seat/rail.pdf", "시트 슬라이드 레일 — 좌측",
         '{"parent": "AJ-SIT-ASS-001", "quantity": 2}'),
        # 연료탱크
        ("DWG-FTK-001", "AJ-FTK-B100", "연료탱크 밴드", "B", "프레스", "SPHC", "프레스+벤딩", "생산기술팀",
         "drawings/fuel/band.pdf", "연료탱크 고정 밴드",
         '{"parent": "AJ-FTK-ASS-001", "quantity": 2}'),
        # 도어 힌지
        ("DWG-DHG-001", "AJ-DHG-U100", "도어 힌지 상부", "A", "프레스", "SAPH440", "프레스", "생산관리팀",
         "drawings/door/hinge_upper.pdf", "프론트 도어 상부 힌지",
         '{"parent": "AJ-DHG-ASS-001", "quantity": 2}'),
        # 브레이크
        ("DWG-BRK-001", "AJ-BRK-B100", "브레이크 브라켓", "C", "프레스", "SPFH590", "프레스+가공", "부품개발팀",
         "drawings/brake/bracket.pdf", "디스크 브레이크 캘리퍼 브라켓",
         '{"parent": "AJ-BRK-ASS-001", "quantity": 2}'),
    ]

    conn.executemany(
        """INSERT INTO drawings
           (drawing_number, part_number, part_name, revision, equipment_type,
            material, process_type, department, file_path, description, bom_info)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        samples,
    )


def _get_conn(db_path: Path = DRAWING_DB_PATH) -> sqlite3.Connection:
    init_drawing_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def search_by_number(
    query: str,
    db_path: Path = DRAWING_DB_PATH,
) -> list[dict]:
    """도면번호 또는 부품번호로 정확/부분 매칭 검색"""
    conn = _get_conn(db_path)
    try:
        q = query.strip().upper()
        rows = conn.execute(
            """SELECT * FROM drawings
               WHERE UPPER(drawing_number) LIKE ? OR UPPER(part_number) LIKE ?
               ORDER BY drawing_number
               LIMIT 20""",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def search_by_keyword(
    query: str,
    equipment_type: str = "",
    department: str = "",
    db_path: Path = DRAWING_DB_PATH,
) -> list[dict]:
    """부품명, 설명, 재질 등 키워드 검색"""
    conn = _get_conn(db_path)
    try:
        conditions = [
            "(part_name LIKE ? OR description LIKE ? OR material LIKE ? OR process_type LIKE ?)"
        ]
        params = [f"%{query}%"] * 4

        if equipment_type:
            conditions.append("equipment_type = ?")
            params.append(equipment_type)
        if department:
            conditions.append("department = ?")
            params.append(department)

        where = " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT * FROM drawings WHERE {where} ORDER BY part_name LIMIT 20",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_drawing(drawing_id: int, db_path: Path = DRAWING_DB_PATH) -> Optional[dict]:
    """도면 상세 조회"""
    conn = _get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM drawings WHERE id = ?", (drawing_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        try:
            result["bom"] = json.loads(result.get("bom_info", "{}"))
        except (json.JSONDecodeError, TypeError):
            result["bom"] = {}
        return result
    finally:
        conn.close()


def get_equipment_types(db_path: Path = DRAWING_DB_PATH) -> list[str]:
    """등록된 장비유형 목록"""
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT equipment_type FROM drawings WHERE equipment_type != '' ORDER BY equipment_type"
        ).fetchall()
        return [r["equipment_type"] for r in rows]
    finally:
        conn.close()


def get_drawing_stats(db_path: Path = DRAWING_DB_PATH) -> dict:
    """도면 DB 통계"""
    conn = _get_conn(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM drawings").fetchone()[0]
        by_type = {}
        for row in conn.execute(
            "SELECT equipment_type, COUNT(*) as cnt FROM drawings GROUP BY equipment_type"
        ):
            by_type[row["equipment_type"] or "기타"] = row["cnt"]
        return {"total": total, "by_type": by_type}
    finally:
        conn.close()
