"""v2.3 Phase 3: 규제 크롤링 결과 DB 저장 — compliance.db

크롤링된 규제/법규 데이터를 SQLite에 저장하여:
- 이력 추적 (crawl_history)
- 개별 규제 항목 검색/필터 (regulations)
- 문서 내보내기용 데이터 조회
를 지원한다.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent.parent.parent / "data" / "compliance.db"


def get_db() -> sqlite3.Connection:
    """compliance.db 연결을 반환한다. (v3.5: UTF-8 PRAGMA 추가)"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA encoding='UTF-8'")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """compliance.db 스키마를 초기화한다."""
    conn = get_db()
    conn.executescript("""
    -- 크롤링 실행 이력
    CREATE TABLE IF NOT EXISTS crawl_history (
        crawl_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        crawler_name TEXT NOT NULL,          -- 예: "iso_standards", "domestic_laws"
        display_name TEXT DEFAULT '',         -- 예: "ISO 국제규격", "국내법규"
        json_filename TEXT NOT NULL,          -- 예: "iso_standards.json"
        crawled_at  TEXT NOT NULL,            -- 크롤링 시각 ISO 8601
        total_count INTEGER DEFAULT 0,        -- 수집된 항목 수
        status      TEXT DEFAULT 'success',   -- success / partial / failed
        errors      TEXT DEFAULT '',          -- 오류 메시지
        created_at  TEXT DEFAULT (datetime('now'))
    );

    -- 개별 규제 항목
    CREATE TABLE IF NOT EXISTS regulations (
        reg_pk      INTEGER PRIMARY KEY AUTOINCREMENT,
        crawl_id    INTEGER NOT NULL REFERENCES crawl_history(crawl_id),
        reg_id      TEXT NOT NULL,            -- 원본 ID (law_id, standard_id 등)
        name        TEXT NOT NULL,            -- 규제 이름
        name_ko     TEXT DEFAULT '',
        doc_type    TEXT NOT NULL,            -- ISO/APQP/MSDS/DomesticLaw/EU/OEM/ESG/EV/Trade
        category    TEXT DEFAULT '',
        authority   TEXT DEFAULT '',          -- 발행 기관
        compliance_status TEXT DEFAULT '',    -- 충족/부분충족/미충족 등
        effective_date TEXT DEFAULT '',
        last_amended   TEXT DEFAULT '',
        content_json   TEXT DEFAULT '{}',     -- 원본 항목 전체 JSON
        created_at     TEXT DEFAULT (datetime('now'))
    );

    -- 인덱스
    CREATE INDEX IF NOT EXISTS idx_reg_doc_type ON regulations(doc_type);
    CREATE INDEX IF NOT EXISTS idx_reg_crawl_id ON regulations(crawl_id);
    CREATE INDEX IF NOT EXISTS idx_reg_status ON regulations(compliance_status);
    CREATE INDEX IF NOT EXISTS idx_crawl_name ON crawl_history(crawler_name);
    """)
    conn.commit()
    conn.close()


def save_crawl_result(
    crawler_name: str,
    display_name: str,
    json_filename: str,
    items: list[dict],
    doc_type: str,
    crawled_at: str = "",
    id_key: str = "reg_id",
    name_key: str = "name",
    status_key: str | None = None,
    errors: str = "",
) -> int:
    """크롤링 결과를 DB에 저장한다.

    Args:
        crawler_name: 크롤러 내부명 (예: "iso_standards")
        display_name: 화면 표시명 (예: "ISO 국제규격")
        json_filename: JSON 파일명 (예: "iso_standards.json")
        items: 규제 항목 리스트
        doc_type: 문서 유형 (예: "ISO")
        crawled_at: 크롤링 시각 ISO 8601
        id_key: 항목 ID 필드명
        name_key: 항목 이름 필드명
        status_key: 준수 상태 필드명 (None이면 없음)
        errors: 오류 메시지

    Returns:
        crawl_id
    """
    init_db()
    conn = get_db()

    if not crawled_at:
        crawled_at = datetime.now().isoformat()

    status = "failed" if errors and not items else ("partial" if errors else "success")

    cursor = conn.execute(
        """INSERT INTO crawl_history
           (crawler_name, display_name, json_filename, crawled_at, total_count, status, errors)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (crawler_name, display_name, json_filename, crawled_at, len(items), status, errors),
    )
    crawl_id = cursor.lastrowid

    for item in items:
        reg_id = str(item.get(id_key, ""))
        name = str(item.get(name_key, item.get("name", item.get("name_ko", ""))))
        name_ko = str(item.get("name_ko", item.get("title_ko", "")))
        category = str(item.get("category", ""))
        authority = str(item.get("authority", item.get("issuing_org", "")))
        compliance = str(item.get(status_key, "")) if status_key else ""
        effective = str(item.get("effective_date", ""))
        amended = str(item.get("last_amended", ""))

        conn.execute(
            """INSERT INTO regulations
               (crawl_id, reg_id, name, name_ko, doc_type, category, authority,
                compliance_status, effective_date, last_amended, content_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (crawl_id, reg_id, name, name_ko, doc_type, category, authority,
             compliance, effective, amended, json.dumps(item, ensure_ascii=False)),
        )

    conn.commit()
    conn.close()
    return crawl_id


def get_crawl_history(limit: int = 50) -> list[dict]:
    """크롤링 이력을 조회한다."""
    init_db()
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM crawl_history ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_regulations(
    doc_type: str | None = None,
    compliance_status: str | None = None,
    search_query: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """규제 항목을 조회한다."""
    init_db()
    conn = get_db()

    query = "SELECT * FROM regulations WHERE 1=1"
    params: list[Any] = []

    if doc_type:
        query += " AND doc_type = ?"
        params.append(doc_type)
    if compliance_status:
        query += " AND compliance_status = ?"
        params.append(compliance_status)
    if search_query:
        query += " AND (name LIKE ? OR name_ko LIKE ? OR content_json LIKE ?)"
        q = f"%{search_query}%"
        params.extend([q, q, q])

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_regulations_by_type(doc_type: str) -> list[dict]:
    """특정 유형의 최신 크롤링 규제 항목을 조회한다."""
    init_db()
    conn = get_db()

    # 최신 crawl_id 조회
    latest = conn.execute(
        """SELECT crawl_id FROM crawl_history
           WHERE json_filename LIKE ? AND status != 'failed'
           ORDER BY created_at DESC LIMIT 1""",
        (f"%{doc_type}%",),
    ).fetchone()

    if not latest:
        conn.close()
        return []

    rows = conn.execute(
        "SELECT * FROM regulations WHERE crawl_id = ? ORDER BY reg_id",
        (latest["crawl_id"],),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_db_stats() -> dict:
    """DB 통계를 반환한다."""
    init_db()
    conn = get_db()
    total_crawls = conn.execute("SELECT COUNT(*) FROM crawl_history").fetchone()[0]
    total_regs = conn.execute("SELECT COUNT(*) FROM regulations").fetchone()[0]
    latest_crawl = conn.execute(
        "SELECT crawled_at FROM crawl_history ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return {
        "total_crawls": total_crawls,
        "total_regulations": total_regs,
        "latest_crawl": latest_crawl[0] if latest_crawl else "N/A",
    }
