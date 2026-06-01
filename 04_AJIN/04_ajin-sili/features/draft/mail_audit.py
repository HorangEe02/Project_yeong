"""Mail send audit log — Feature B Sprint 1 P0.

audit.db.mail_audit_log 테이블에 발송 이벤트 영속화.
스키마는 core/directory/migrations.py AUDIT_MIGRATIONS 에 정의 (단일 출처).

호출 위치: backend/routers/draft.py:send_mail 라우터 — guard 통과 후 호출.
가드 차단 시에도 호출 (guard_decision != 'allow') 하여 차단 통계 측정 가능.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from core.directory.migrations import AUDIT_DB

logger = logging.getLogger(__name__)


def _extract_domains(emails: list[str]) -> list[str]:
    domains: set[str] = set()
    for e in emails or []:
        if not e or "@" not in e:
            continue
        domains.add(e.rsplit("@", 1)[-1].lower().strip())
    return sorted(domains)


def append(
    *,
    user_id: Optional[int] = None,
    sender_email: str = "",
    version_id: Optional[int] = None,
    version_status: Optional[str] = None,
    adapter: str = "",
    ok: bool = False,
    message_id: str = "",
    to_recipients: Optional[list[str]] = None,
    cc_recipients: Optional[list[str]] = None,
    bcc_recipients: Optional[list[str]] = None,
    external_domains: Optional[list[str]] = None,
    guard_decision: str = "",
    watermark_id: str = "",
    detail: str = "",
    db_path: Path = AUDIT_DB,
) -> Optional[int]:
    """Insert 1 row into mail_audit_log. Returns row id or None on failure.

    `external_domains` 가 None 이면 to/cc/bcc 합산해서 자동 계산.
    """
    to_list = to_recipients or []
    cc_list = cc_recipients or []
    bcc_list = bcc_recipients or []

    if external_domains is None:
        external_domains = _extract_domains(to_list + cc_list + bcc_list)

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute(
            """INSERT INTO mail_audit_log
               (user_id, sender_email, version_id, version_status,
                adapter, ok, message_id,
                to_count, cc_count, bcc_count,
                external_domains, guard_decision, watermark_id, detail)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                sender_email,
                version_id,
                version_status,
                adapter,
                1 if ok else 0,
                message_id,
                len(to_list),
                len(cc_list),
                len(bcc_list),
                json.dumps(external_domains, ensure_ascii=False),
                guard_decision,
                watermark_id,
                detail,
            ),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return int(row_id) if row_id else None
    except sqlite3.OperationalError as e:
        logger.warning("mail_audit append 실패: %s", e)
        return None


def get_recent(limit: int = 50, db_path: Path = AUDIT_DB) -> list[dict]:
    """최근 발송/차단 이벤트 조회 — admin UI / Sprint 1 DoD 검증용."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM mail_audit_log ORDER BY id DESC LIMIT ?",
            (max(1, min(limit, 500)),),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        logger.warning("mail_audit get_recent 실패: %s", e)
        return []
