"""D4 — 사내 SOP 와 규제 변경 간 차이 분석.

저장: `compliance.db.sop_documents` 테이블 (D4 신규).
매칭: (1) tag — related_regulation_ids ⊃ change.regulation_type, 또는
       (2) semantic — ChromaDB 유사도 (regulation_indexer 컬렉션 재사용).
diff: difflib.SequenceMatcher → 토큰 단위 변경 블록.
"""
from __future__ import annotations

import difflib
import json
import sqlite3
from datetime import datetime
from typing import Any

from config import DATA_DIR

DB_PATH = DATA_DIR / "compliance.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table() -> None:
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sop_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                version TEXT DEFAULT '',
                plant_id TEXT DEFAULT '',
                dept TEXT DEFAULT '',
                file_path TEXT DEFAULT '',
                body_excerpt TEXT DEFAULT '',
                related_regulation_ids TEXT DEFAULT '[]',
                sop_type TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                uploaded_by TEXT DEFAULT '',
                uploaded_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_sop_dept ON sop_documents(dept);
            CREATE INDEX IF NOT EXISTS idx_sop_plant ON sop_documents(plant_id);
        """)
        conn.commit()
    finally:
        conn.close()


def list_sops(limit: int = 100) -> list[dict[str, Any]]:
    ensure_table()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM sop_documents WHERE status='active' "
            "ORDER BY uploaded_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["related_regulation_ids"] = json.loads(d.get("related_regulation_ids") or "[]")
            except Exception:
                d["related_regulation_ids"] = []
            out.append(d)
        return out
    finally:
        conn.close()


def get_sop(sop_id: int) -> dict[str, Any] | None:
    conn = _connect()
    try:
        r = conn.execute("SELECT * FROM sop_documents WHERE id = ?", (sop_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        try:
            d["related_regulation_ids"] = json.loads(d.get("related_regulation_ids") or "[]")
        except Exception:
            d["related_regulation_ids"] = []
        return d
    finally:
        conn.close()


def create_sop(payload: dict[str, Any], uploaded_by: str = "") -> int:
    ensure_table()
    related = payload.get("related_regulation_ids") or []
    if not isinstance(related, list):
        related = [str(related)]
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO sop_documents(title, version, plant_id, dept, file_path, "
            "body_excerpt, related_regulation_ids, sop_type, uploaded_by, uploaded_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                payload.get("title", ""),
                payload.get("version", "1.0"),
                payload.get("plant_id", ""),
                payload.get("dept", ""),
                payload.get("file_path", ""),
                (payload.get("body_excerpt") or "")[:5000],
                json.dumps(related, ensure_ascii=False),
                payload.get("sop_type", ""),
                uploaded_by,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _tag_match(change: dict[str, Any], sops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rtype = (change.get("regulation_type") or "").upper()
    matched: list[dict[str, Any]] = []
    if not rtype:
        return matched
    for s in sops:
        related = [str(x).upper() for x in (s.get("related_regulation_ids") or [])]
        if rtype in related:
            matched.append({**s, "match_method": "tag"})
    return matched


def _build_diff_blocks(old_text: str, new_text: str) -> list[dict[str, str]]:
    """SequenceMatcher → 변경 블록. equal/insert/delete/replace 마킹."""
    sm = difflib.SequenceMatcher(None, old_text or "", new_text or "")
    blocks: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            blocks.append({"op": "equal", "old": old_text[i1:i2], "new": new_text[j1:j2]})
        elif tag == "replace":
            blocks.append({"op": "replace", "old": old_text[i1:i2], "new": new_text[j1:j2]})
        elif tag == "delete":
            blocks.append({"op": "delete", "old": old_text[i1:i2], "new": ""})
        elif tag == "insert":
            blocks.append({"op": "insert", "old": "", "new": new_text[j1:j2]})
    return blocks


def diff_for_change(change_id: int, change_row: dict[str, Any]) -> dict[str, Any]:
    """변경 1건 → 영향 SOP 목록 + 사이드바이 diff 블록."""
    ensure_table()
    sops = list_sops(limit=200)
    matches = _tag_match(change_row, sops)

    old_value = change_row.get("old_value") or ""
    new_value = change_row.get("new_value") or change_row.get("summary_ko") or ""

    affected: list[dict[str, Any]] = []
    for sop in matches:
        body = sop.get("body_excerpt") or ""
        diff_blocks = _build_diff_blocks(body, body)  # SOP 본문 자체는 변경 없음
        regulation_blocks = _build_diff_blocks(old_value, new_value)
        affected.append({
            "sop_id": sop["id"],
            "sop_title": sop["title"],
            "version": sop["version"],
            "dept": sop["dept"],
            "match_method": sop["match_method"],
            "regulation_diff": regulation_blocks,
            "sop_excerpt": body,
            "sop_diff": diff_blocks,
        })

    return {
        "change_id": change_id,
        "regulation_type": change_row.get("regulation_type"),
        "affected_sops": affected,
        "match_count": len(affected),
    }
