"""D2 base — Notifier 인터페이스 + 공통 데이터 클래스."""
from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from config import DATA_DIR

NOTIFICATIONS_DB = DATA_DIR / "notifications.db"
CAPTURES_DIR = DATA_DIR / "captures"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class NotificationContext:
    """단일 알림 단위 — outbox 페이로드 + 사용자 채널 정보."""
    user_id: str
    user_email: str
    channel: str  # email | slack | teams
    template: str  # change_alert | digest
    subject: str
    body_text: str
    payload: dict[str, Any] = field(default_factory=dict)
    change_id: int | None = None


@dataclass
class DispatchResult:
    success: bool
    detail: str = ""
    captured_path: str | None = None


class Notifier(ABC):
    """채널별 어댑터 베이스."""
    channel: str = "base"

    @abstractmethod
    def send(self, ctx: NotificationContext) -> DispatchResult: ...


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(NOTIFICATIONS_DB)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables() -> None:
    """notifications.db 3 테이블 생성 (idempotent)."""
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id TEXT PRIMARY KEY,
                email TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                channel_email INTEGER DEFAULT 1,
                channel_slack INTEGER DEFAULT 0,
                channel_teams INTEGER DEFAULT 0,
                severity_threshold TEXT DEFAULT 'MEDIUM',
                digest_enabled INTEGER DEFAULT 1,
                digest_hour_kst INTEGER DEFAULT 8,
                plant_filter_json TEXT DEFAULT '[]',
                department_filter TEXT DEFAULT '',
                slack_webhook_url TEXT DEFAULT '',
                teams_webhook_url TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS notification_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                template TEXT NOT NULL,
                subject TEXT DEFAULT '',
                payload_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                last_error TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                sent_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_outbox_status ON notification_outbox(status);
            CREATE INDEX IF NOT EXISTS idx_outbox_user ON notification_outbox(user_id);
            CREATE TABLE IF NOT EXISTS notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                outbox_id INTEGER,
                user_id TEXT NOT NULL,
                change_id INTEGER,
                template TEXT NOT NULL,
                channel TEXT NOT NULL,
                sent_at TEXT DEFAULT (datetime('now', 'localtime')),
                success INTEGER DEFAULT 1,
                detail TEXT DEFAULT '',
                UNIQUE(user_id, change_id, template, channel)
            );
            CREATE INDEX IF NOT EXISTS idx_log_user ON notification_log(user_id);
            CREATE INDEX IF NOT EXISTS idx_log_change ON notification_log(change_id);
        """)
        conn.commit()
    finally:
        conn.close()


def severity_meets_threshold(sev: str, threshold: str) -> bool:
    """severity (CRITICAL/HIGH/MEDIUM/LOW) 가 threshold 이상이면 True."""
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    return order.get((sev or "LOW").upper(), 0) >= order.get(
        (threshold or "MEDIUM").upper(), 1
    )


def get_prefs(user_id: str) -> dict[str, Any] | None:
    ensure_tables()
    conn = _connect()
    try:
        r = conn.execute(
            "SELECT * FROM notification_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def upsert_prefs(user_id: str, prefs: dict[str, Any], email: str = "") -> dict[str, Any]:
    ensure_tables()
    import json as _json

    plant_filter = prefs.get("plant_filter") or []
    if isinstance(plant_filter, list):
        plant_filter_json = _json.dumps(plant_filter, ensure_ascii=False)
    else:
        plant_filter_json = str(plant_filter)

    fields = {
        "email": email or prefs.get("email", ""),
        "enabled": 1 if prefs.get("enabled", True) else 0,
        "channel_email": 1 if prefs.get("channel_email", True) else 0,
        "channel_slack": 1 if prefs.get("channel_slack", False) else 0,
        "channel_teams": 1 if prefs.get("channel_teams", False) else 0,
        "severity_threshold": (prefs.get("severity_threshold", "MEDIUM") or "MEDIUM").upper(),
        "digest_enabled": 1 if prefs.get("digest_enabled", True) else 0,
        "digest_hour_kst": int(prefs.get("digest_hour_kst", 8)),
        "plant_filter_json": plant_filter_json,
        "department_filter": prefs.get("department_filter") or "",
        "slack_webhook_url": prefs.get("slack_webhook_url", ""),
        "teams_webhook_url": prefs.get("teams_webhook_url", ""),
        "updated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }

    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT user_id FROM notification_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            sql = "UPDATE notification_preferences SET " + ", ".join(
                f"{k} = ?" for k in fields
            ) + " WHERE user_id = ?"
            conn.execute(sql, [*fields.values(), user_id])
        else:
            cols = ["user_id", *fields.keys()]
            placeholders = ", ".join("?" for _ in cols)
            sql = f"INSERT INTO notification_preferences({', '.join(cols)}) VALUES ({placeholders})"
            conn.execute(sql, [user_id, *fields.values()])
        conn.commit()
    finally:
        conn.close()

    out = get_prefs(user_id) or {}
    return out
