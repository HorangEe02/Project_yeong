"""D1 — SQLite FTS5 인덱스 (regulations 테이블 1,784 row 대상).

`compliance.db.regulations` 의 name, name_ko + content_json 의 핵심 텍스트 필드를
하나의 `body` 컬럼으로 평탄화하여 FTS5 가상테이블에 적재한다.

토크나이저: `unicode61 remove_diacritics 2` — 라틴/영문 정규화.
한국어는 trigram 파생 형태로도 매칭되므로 단어 단위 매칭이 가능.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from config import DATA_DIR

DB_PATH = DATA_DIR / "compliance.db"

FTS_TABLE = "regulations_fts"

_BODY_FIELDS = (
    "title", "title_ko", "scope", "ajin_relevance",
    "description", "key_activities", "changes_summary",
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _flatten_body(content_json: str | None, name: str, name_ko: str) -> str:
    parts: list[str] = [name or "", name_ko or ""]
    if content_json:
        try:
            doc = json.loads(content_json)
        except Exception:
            return " ".join(p for p in parts if p)
        if isinstance(doc, dict):
            for f in _BODY_FIELDS:
                v = doc.get(f)
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, list):
                    parts.extend(str(x) for x in v if isinstance(x, (str, int, float)))
    return " ".join(p for p in parts if p)


def ensure_table() -> None:
    """FTS5 가상테이블 + 메타 테이블 생성 (idempotent)."""
    conn = _connect()
    try:
        conn.executescript(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(
                reg_id UNINDEXED,
                name,
                name_ko,
                body,
                doc_type UNINDEXED,
                authority UNINDEXED,
                tokenize='unicode61 remove_diacritics 2'
            );
            CREATE TABLE IF NOT EXISTS regulations_fts_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.commit()
    finally:
        conn.close()


def index_count() -> int:
    conn = _connect()
    try:
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {FTS_TABLE}").fetchone()[0]
        except sqlite3.OperationalError:
            return 0
    finally:
        conn.close()


def rebuild() -> int:
    """전체 인덱스 재구축. regulations 1,784 row → FTS5."""
    ensure_table()
    conn = _connect()
    try:
        conn.execute(f"DELETE FROM {FTS_TABLE}")
        rows = conn.execute(
            "SELECT reg_id, name, name_ko, doc_type, authority, content_json "
            "FROM regulations"
        ).fetchall()
        inserted = 0
        for r in rows:
            body = _flatten_body(r["content_json"], r["name"] or "", r["name_ko"] or "")
            conn.execute(
                f"INSERT INTO {FTS_TABLE}(reg_id, name, name_ko, body, doc_type, authority) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    r["reg_id"] or "",
                    r["name"] or "",
                    r["name_ko"] or "",
                    body,
                    r["doc_type"] or "",
                    r["authority"] or "",
                ),
            )
            inserted += 1
        conn.execute(
            "INSERT OR REPLACE INTO regulations_fts_meta(key, value) VALUES('last_rebuild_count', ?)",
            (str(inserted),),
        )
        conn.commit()
        return inserted
    finally:
        conn.close()


def rebuild_if_empty() -> int:
    if index_count() == 0:
        return rebuild()
    return index_count()


def _escape_query(q: str) -> str:
    """FTS5 안전 쿼리. 토큰을 OR 으로 묶어 부분 매칭에 관대하게."""
    tokens = [t for t in (q or "").split() if t]
    if not tokens:
        return ""
    safe = []
    for t in tokens:
        cleaned = "".join(ch for ch in t if ch.isalnum() or ch in "가-힣")
        if cleaned:
            safe.append(f'"{t}"')
    return " OR ".join(safe) if safe else ""


def query(q: str, limit: int = 20, offset: int = 0,
          doc_type: str | None = None) -> list[dict[str, Any]]:
    """FTS5 BM25 검색. (rank, reg_id, name, name_ko, doc_type, authority, snippet)"""
    ensure_table()
    fts_q = _escape_query(q)
    if not fts_q:
        return []
    sql = (
        f"SELECT reg_id, name, name_ko, doc_type, authority, "
        f"snippet({FTS_TABLE}, 3, '<mark>', '</mark>', '…', 12) AS snippet, "
        f"bm25({FTS_TABLE}) AS rank "
        f"FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH ? "
    )
    params: list[Any] = [fts_q]
    if doc_type:
        sql += "AND doc_type = ? "
        params.append(doc_type)
    sql += "ORDER BY rank LIMIT ? OFFSET ?"
    params += [limit, offset]

    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [
            {
                "reg_id": r["reg_id"],
                "name": r["name"],
                "name_ko": r["name_ko"],
                "doc_type": r["doc_type"],
                "authority": r["authority"],
                "snippet": r["snippet"],
                "rank": float(r["rank"]),
            }
            for r in rows
        ]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def fetch_regulation(reg_id: str) -> dict[str, Any] | None:
    """단일 규제 상세 조회 (regulations 테이블 + content_json)."""
    conn = _connect()
    try:
        r = conn.execute(
            "SELECT reg_id, name, name_ko, doc_type, category, authority, "
            "compliance_status, effective_date, last_amended, content_json "
            "FROM regulations WHERE reg_id = ?",
            (reg_id,),
        ).fetchone()
        if not r:
            return None
        out: dict[str, Any] = dict(r)
        cj = out.pop("content_json", None)
        if cj:
            try:
                doc = json.loads(cj)
                if isinstance(doc, dict):
                    out["body"] = doc.get("scope") or doc.get("description") or ""
                    out["raw"] = doc
            except Exception:
                pass
        return out
    finally:
        conn.close()
