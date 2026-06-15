"""도면 Vision 캡션 인덱스 — Vision LLM 이 추출한 도면 캡션·키워드를 SQLite 에 저장.

본 모듈은 정식 ChromaDB 임베딩 인덱싱 전 단계의 PoC 이다.
- 입력: Vision LLM 응답(텍스트 캡션) + 사용자 메타데이터(부서, 부품명 추정 등)
- 저장: SQLite (FTS 없이 단순 LIKE 검색)
- 한계: 임베딩 검색 미지원 — v2.0 ChromaDB 통합 시 본 테이블에서 마이그레이션

`search_captions` 는 도면 메타(drawings) 검색과 합쳐 결과를 노출한다.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

CAPTION_DB_PATH = Path("data/equipment/drawing_captions.db")


def _init_db(db_path: Path = CAPTION_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS drawing_captions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            caption      TEXT NOT NULL,
            keywords     TEXT DEFAULT '',
            department   TEXT DEFAULT '',
            uploader     TEXT DEFAULT '',
            file_name    TEXT DEFAULT '',
            image_size   INTEGER DEFAULT 0,
            source_model TEXT DEFAULT '',
            created_at   TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_caption ON drawing_captions(caption);
        CREATE INDEX IF NOT EXISTS idx_dept ON drawing_captions(department);
        """
    )
    conn.commit()
    return conn


def add_caption(
    caption: str,
    keywords: str = "",
    department: str = "",
    uploader: str = "",
    file_name: str = "",
    image_size: int = 0,
    source_model: str = "",
    db_path: Path = CAPTION_DB_PATH,
) -> int:
    """Vision 캡션 1건을 인덱스에 저장하고 row id 반환."""
    conn = _init_db(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO drawing_captions
               (caption, keywords, department, uploader, file_name, image_size, source_model)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (caption, keywords, department, uploader, file_name, image_size, source_model),
        )
        conn.commit()
        return cur.lastrowid or 0
    finally:
        conn.close()


def search_captions(
    query: str = "",
    department: str = "",
    limit: int = 20,
    db_path: Path = CAPTION_DB_PATH,
) -> list[dict]:
    """캡션 텍스트/키워드에 대한 LIKE 검색."""
    conn = _init_db(db_path)
    try:
        conditions: list[str] = []
        params: list = []
        q = query.strip()
        if q:
            conditions.append("(caption LIKE ? OR keywords LIKE ? OR file_name LIKE ?)")
            params.extend([f"%{q}%"] * 3)
        if department:
            conditions.append("department = ?")
            params.append(department)
        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM drawing_captions WHERE {where} ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_caption(caption_id: int, db_path: Path = CAPTION_DB_PATH) -> Optional[dict]:
    conn = _init_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM drawing_captions WHERE id = ?", (caption_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_captions(db_path: Path = CAPTION_DB_PATH) -> int:
    conn = _init_db(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM drawing_captions").fetchone()
        return int(row["c"]) if row else 0
    finally:
        conn.close()
