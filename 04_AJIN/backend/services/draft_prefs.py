"""P3-1 — Module B 사용자 prefs 서버 sync (compliance.db).

저장: `draft_user_prefs(user_id PK, favorited_doc_types TEXT, updated_at)`
용도: 다중 기기 (노트북/휴대폰/태블릿) ★ 즐겨찾기 동기화. 페르소나: 시니어.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

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
            CREATE TABLE IF NOT EXISTS draft_user_prefs (
                user_id TEXT PRIMARY KEY,
                favorited_doc_types TEXT DEFAULT '[]',
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_prefs(user_id: str) -> dict:
    """사용자 prefs 조회. 없으면 빈 즐겨찾기 반환."""
    if not user_id:
        return {"favorited_doc_types": []}
    ensure_table()
    conn = _connect()
    try:
        r = conn.execute(
            "SELECT favorited_doc_types FROM draft_user_prefs WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not r:
            return {"favorited_doc_types": []}
        try:
            favs = json.loads(r["favorited_doc_types"] or "[]")
        except Exception:
            favs = []
        return {"favorited_doc_types": favs if isinstance(favs, list) else []}
    finally:
        conn.close()


def upsert_prefs(user_id: str, favorited_doc_types: list[str]) -> dict:
    """사용자 prefs 저장 — last-write-wins (단순 overwrite)."""
    if not user_id:
        return {"favorited_doc_types": favorited_doc_types, "updated_at": ""}
    ensure_table()
    clean = [str(x) for x in (favorited_doc_types or []) if isinstance(x, (str, int))]
    payload = json.dumps(clean, ensure_ascii=False)
    now = datetime.now().isoformat(timespec="seconds")
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO draft_user_prefs(user_id, favorited_doc_types, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "favorited_doc_types=excluded.favorited_doc_types, "
            "updated_at=excluded.updated_at",
            (user_id, payload, now),
        )
        conn.commit()
        return {"favorited_doc_types": clean, "updated_at": now}
    finally:
        conn.close()


# 부록 6 P4-4 — multi-device 충돌 해결 (3-way merge)
def merge_prefs(
    user_id: str,
    client_list: list[str],
    base_version: str = "",
    removed_ids: list[str] | None = None,
) -> dict:
    """3-way merge — base_version 이 현재 server 보다 stale 일 때 set union.

    Args:
        client_list: 기기가 전송한 최신 즐겨찾기 (현재 기기 상태)
        base_version: 기기가 마지막 GET 했을 때 받은 server updated_at
        removed_ids: 기기가 명시적으로 제거한 항목 (있으면 merge 결과에서 제외)

    Returns:
        {favorited_doc_types, updated_at, merged: bool, conflict_detected: bool}
    """
    if not user_id:
        return upsert_prefs(user_id, client_list)

    ensure_table()
    removed_set = set(removed_ids or [])
    client_set = set(str(x) for x in (client_list or []))

    conn = _connect()
    try:
        r = conn.execute(
            "SELECT favorited_doc_types, updated_at FROM draft_user_prefs WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        server_list: list[str] = []
        server_version = ""
        if r:
            try:
                server_list = json.loads(r["favorited_doc_types"] or "[]")
            except Exception:
                server_list = []
            server_version = r["updated_at"] or ""

        # base_version 이 현재 server_version 과 일치하면 conflict 없음 — 일반 overwrite
        # 다르면 (= 다른 기기가 그 사이 변경함) 3-way merge
        conflict = bool(base_version) and bool(server_version) and base_version != server_version

        if conflict:
            # 양쪽 set union, removed_set 제외 (사용자 명시 제거 의도 보존)
            merged_set = (set(server_list) | client_set) - removed_set
            merged_list = sorted(merged_set)
        else:
            merged_list = sorted(client_set - removed_set)

        # 정렬은 deterministic 위해 alphabetical. 사용자 보기 순서는 frontend 가 결정.
        out = upsert_prefs(user_id, merged_list)
        out["merged"] = True if conflict else False
        out["conflict_detected"] = conflict
        return out
    finally:
        conn.close()
