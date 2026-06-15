"""D3 job — 일일 다이제스트.

지난 N시간(default 24) regulation_changes 를 사용자별로 큐잉.
사용자의 digest_hour_kst 가 현재 시각과 일치할 때만 enqueue.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from backend.services.notify.base import _connect, ensure_tables
from backend.services.notify.dispatcher import enqueue_digest_for_user
from config import DATA_DIR

logger = logging.getLogger(__name__)

CHANGES_DB = DATA_DIR / "compliance_changes.db"


def _recent_changes(hours: int = 24) -> list[dict[str, Any]]:
    if not CHANGES_DB.exists():
        return []
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    conn = sqlite3.connect(CHANGES_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM regulation_changes WHERE detected_at >= ? "
            "ORDER BY detected_at DESC LIMIT 200",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def run(force_all_users: bool = False, hours: int = 24) -> dict[str, int]:
    """현재 시각 KST hour 와 일치하는 사용자에게 다이제스트 큐잉.

    Args:
        force_all_users: True 면 시각 매칭 무시하고 전체 사용자 발송 (수동 트리거).
        hours: 최근 몇 시간 변경분을 묶을지.
    """
    ensure_tables()
    changes = _recent_changes(hours=hours)

    now_hour = datetime.now().hour
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM notification_preferences WHERE enabled=1 AND digest_enabled=1"
        ).fetchall()
        prefs_list = [dict(r) for r in rows]
    finally:
        conn.close()

    queued_users = 0
    queued_messages = 0
    for prefs in prefs_list:
        if not force_all_users and int(prefs.get("digest_hour_kst", 8)) != now_hour:
            continue
        n = enqueue_digest_for_user(prefs["user_id"], prefs, changes)
        if n > 0:
            queued_users += 1
            queued_messages += n

    return {
        "queued_users": queued_users,
        "queued_messages": queued_messages,
        "change_count": len(changes),
    }
