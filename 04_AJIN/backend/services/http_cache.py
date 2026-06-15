"""F9 — ETag / If-Modified-Since 공통 유틸 (HTTP 304 캐시).

각 real-HTTP 크롤러 (F8) 가 공통으로 사용하는 conditional GET 헬퍼.
SQLite `http_cache` 테이블에 (url) → (etag, last_modified, fetched_at, body_path) 적재.

페르소나 가치:
- 시니어: "왜 또 차단됐어?" 클레임 ↓ — 매너있는 매번 ETag 동봉으로 외부 차단 회피.
- 신입: 무관 (인프라). 단, 대시보드의 "외부 사이트 응답률" 지표 학습 자료로 노출 가능.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

import httpx

from config import DATA_DIR

DB_PATH = DATA_DIR / "compliance.db"

DEFAULT_USER_AGENT = (
    "AJIN-Compliance-Crawler/1.0 (+https://ajin-cb.web.app; "
    "compliance@ajin.example) httpx"
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table() -> None:
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS http_cache (
                url TEXT PRIMARY KEY,
                etag TEXT DEFAULT '',
                last_modified TEXT DEFAULT '',
                fetched_at TEXT DEFAULT '',
                http_status INTEGER DEFAULT 0,
                body_sha256 TEXT DEFAULT '',
                hit_count INTEGER DEFAULT 0
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_cache(url: str) -> dict[str, Any] | None:
    ensure_table()
    conn = _connect()
    try:
        r = conn.execute("SELECT * FROM http_cache WHERE url = ?", (url,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def upsert_cache(
    url: str,
    etag: str,
    last_modified: str,
    http_status: int,
    body_sha256: str = "",
) -> None:
    ensure_table()
    now = datetime.now().isoformat(timespec="seconds")
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT hit_count FROM http_cache WHERE url = ?", (url,)
        ).fetchone()
        hit_count = (existing["hit_count"] if existing else 0) + (
            1 if http_status == 304 else 0
        )
        conn.execute(
            "INSERT INTO http_cache(url, etag, last_modified, fetched_at, http_status, body_sha256, hit_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(url) DO UPDATE SET "
            "etag=excluded.etag, last_modified=excluded.last_modified, "
            "fetched_at=excluded.fetched_at, http_status=excluded.http_status, "
            "body_sha256=excluded.body_sha256, hit_count=?",
            (url, etag, last_modified, now, http_status, body_sha256, hit_count, hit_count),
        )
        conn.commit()
    finally:
        conn.close()


def conditional_get(
    url: str,
    timeout: float = 10.0,
    extra_headers: dict[str, str] | None = None,
) -> tuple[httpx.Response | None, dict[str, Any]]:
    """Conditional GET — ETag/Last-Modified 동봉.

    Returns:
        (response, http_meta) — response 가 None 이면 304 (변화 없음).
        http_meta = {"status", "etag", "last_modified", "from_cache"}
    """
    cached = get_cache(url) or {}
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    if cached.get("etag"):
        headers["If-None-Match"] = cached["etag"]
    if cached.get("last_modified"):
        headers["If-Modified-Since"] = cached["last_modified"]
    if extra_headers:
        headers.update(extra_headers)

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
    except Exception as e:
        meta: dict[str, Any] = {
            "status": None,
            "etag": "",
            "last_modified": "",
            "from_cache": False,
            "error": str(e)[:200],
        }
        return None, meta

    new_etag = resp.headers.get("ETag", "") or cached.get("etag", "")
    new_lm = resp.headers.get("Last-Modified", "") or cached.get("last_modified", "")

    if resp.status_code == 304:
        upsert_cache(url, new_etag, new_lm, 304)
        return None, {"status": 304, "etag": new_etag,
                      "last_modified": new_lm, "from_cache": True}

    if 200 <= resp.status_code < 300:
        body_sha = ""
        try:
            import hashlib
            body_sha = hashlib.sha256(resp.content).hexdigest()
        except Exception:
            pass
        upsert_cache(url, new_etag, new_lm, resp.status_code, body_sha)

    return resp, {
        "status": resp.status_code,
        "etag": new_etag,
        "last_modified": new_lm,
        "from_cache": False,
    }
