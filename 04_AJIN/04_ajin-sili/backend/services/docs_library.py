"""D7 — 법규 문서 라이브러리 동적 CRUD.

`compliance.db.compliance_documents` 테이블 + 시드 4건 (산안법/REACH/USTR/IATF).
"""
from __future__ import annotations

import sqlite3
from typing import Any

from config import DATA_DIR

DB_PATH = DATA_DIR / "compliance.db"


_SEED = [
    {
        "title": "산안법 시행규칙 개정안",
        "summary": "고용노동부 안전보건 시행규칙 일부 개정안 — 안전거리 확대 및 위험기계 점검 주기 단축.",
        "source_authority": "고용노동부",
        "version": "2026.04",
        "doc_type": "kosha_amend",
        "regulation_ref": "산안법 시행규칙 §40",
        "file_url": "",
    },
    {
        "title": "REACH SVHC 등재 후보 리스트 v28",
        "summary": "ECHA Candidate List 28차 갱신 — 신규 등재 5종 (PFAS 계열 2건 포함).",
        "source_authority": "ECHA",
        "version": "2026.04",
        "doc_type": "reach_svhc",
        "regulation_ref": "REACH Annex XIV",
        "file_url": "",
    },
    {
        "title": "美 자동차부품 232조 관세 검토안",
        "summary": "USTR Section 232 자동차부품 관세 부과 검토 의견수렴 공고.",
        "source_authority": "USTR",
        "version": "2026.03",
        "doc_type": "ustr_232",
        "regulation_ref": "Trade Expansion Act §232",
        "file_url": "",
    },
    {
        "title": "IATF 16949 Sanctioned Interpretations",
        "summary": "IATF 16949 공식 해석문 모음 — 2026 1차 갱신.",
        "source_authority": "IATF",
        "version": "2026.01",
        "doc_type": "iatf_si",
        "regulation_ref": "IATF 16949:2016",
        "file_url": "",
    },
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table() -> None:
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS compliance_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT DEFAULT '',
                file_url TEXT DEFAULT '',
                regulation_ref TEXT DEFAULT '',
                doc_type TEXT NOT NULL,
                version TEXT DEFAULT '',
                source_authority TEXT DEFAULT '',
                uploaded_by TEXT DEFAULT '',
                uploaded_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_docs_doc_type ON compliance_documents(doc_type);
            CREATE INDEX IF NOT EXISTS idx_docs_uploaded_at ON compliance_documents(uploaded_at);
        """)
        conn.commit()
    finally:
        conn.close()


def count() -> int:
    conn = _connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM compliance_documents").fetchone()[0]
    finally:
        conn.close()


def seed_if_empty() -> int:
    ensure_table()
    if count() > 0:
        return 0
    conn = _connect()
    try:
        for d in _SEED:
            conn.execute(
                "INSERT INTO compliance_documents(title, summary, file_url, regulation_ref, "
                "doc_type, version, source_authority, uploaded_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (d["title"], d["summary"], d["file_url"], d["regulation_ref"],
                 d["doc_type"], d["version"], d["source_authority"], "system"),
            )
        conn.commit()
        return len(_SEED)
    finally:
        conn.close()


def list_docs(limit: int = 100, offset: int = 0,
              doc_type: str | None = None) -> list[dict[str, Any]]:
    ensure_table()
    sql = "SELECT * FROM compliance_documents"
    params: list[Any] = []
    if doc_type:
        sql += " WHERE doc_type = ?"
        params.append(doc_type)
    sql += " ORDER BY uploaded_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_doc(doc_id: int) -> dict[str, Any] | None:
    conn = _connect()
    try:
        r = conn.execute(
            "SELECT * FROM compliance_documents WHERE id = ?", (doc_id,)
        ).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def create_doc(payload: dict[str, Any], uploaded_by: str = "") -> int:
    ensure_table()
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO compliance_documents(title, summary, file_url, regulation_ref, "
            "doc_type, version, source_authority, uploaded_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                payload.get("title", ""),
                payload.get("summary", ""),
                payload.get("file_url", ""),
                payload.get("regulation_ref", ""),
                payload.get("doc_type", "misc"),
                payload.get("version", ""),
                payload.get("source_authority", ""),
                uploaded_by,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_doc(doc_id: int) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM compliance_documents WHERE id = ?", (doc_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
