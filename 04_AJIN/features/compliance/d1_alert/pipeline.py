"""D1 Alert dispatch pipeline — alarm_aggregator → firebase_rtdb.push_alarm 호출 체인.

배경:
- `features.compliance.alerts.alarm_aggregator.collect_recent_alarms()` 가 5종 source
  (law_change / dday_imminent / impact_score / unresolved_action / trend_spike) 에서
  `ComplianceAlarm` 리스트를 read-time 집계한다.
- 그러나 read-time 집계만으로는 frontend 가 알람 발생 즉시 받기 어렵다 (polling lag).
- 본 모듈은 집계된 알람을 `firebase_rtdb.push_alarm()` 으로 `/live_alarms` path 에
  push 하여 F SPC 알람과 동일 통로로 실시간 노출되도록 한다.
- 같은 path `/live_alarms` 를 공유하되 `module="D"` 필드로 구분 → frontend 가 필터링.

Celery wiring:
- `backend.celery_app.t_compliance_alarm_dispatch` 가 매 5분 본 함수를 호출한다.

Dedup:
- 동일 `ComplianceAlarm.id` 의 중복 push 방지 → `_pushed_state.db` SQLite 테이블에
  `alarm_id, rtdb_key, pushed_at` 영속.
- alarm_aggregator 의 5종 source 자체 dedup 과 직교 (저 위는 한 collect 내 dedup,
  여기는 dispatch 간 dedup).

dry-run 모드 (FIREBASE_WRITE_ENABLED=false 또는 미설정):
- `firebase_rtdb.push_alarm` 이 자동으로 `data/captures/rtdb_dryrun/` 에 파일 캡쳐.
- pipeline 은 그대로 동작 (key 는 'dryrun-*' 또는 'disabled-*' 형태).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from backend.schemas.compliance_alarm import ComplianceAlarm
from backend.services.firebase_rtdb import push_alarm
from features.compliance.alerts.alarm_aggregator import collect_recent_alarms

logger = logging.getLogger(__name__)

_PUSHED_STATE_DB = Path("data") / "_d1_alert_rtdb_pushed.db"
_RTDB_PATH = "/live_alarms"


def _ensure_state_table(conn: sqlite3.Connection) -> None:
    """idempotent — dedup 상태 테이블 생성."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS d1_alert_rtdb_pushed (
            alarm_id TEXT PRIMARY KEY,
            rtdb_key TEXT NOT NULL,
            pushed_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def _load_pushed_ids(conn: sqlite3.Connection) -> set[str]:
    cur = conn.execute("SELECT alarm_id FROM d1_alert_rtdb_pushed")
    return {row[0] for row in cur.fetchall()}


def _mark_pushed(conn: sqlite3.Connection, alarm_id: str, rtdb_key: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO d1_alert_rtdb_pushed(alarm_id, rtdb_key) VALUES(?, ?)",
        (alarm_id, rtdb_key),
    )
    conn.commit()


def _to_rtdb_payload(alarm: ComplianceAlarm) -> dict[str, Any]:
    """ComplianceAlarm → RTDB `/live_alarms` 항목 형식.

    F SPC 알람과 같은 schema 를 유지하되, `module="D"` 로 구분.
    frontend `useComplianceRTDB` 가 module 필드로 필터링.
    """
    return {
        "module": alarm.module,  # = "D"
        "source": alarm.source,
        "severity": alarm.severity,
        "title": alarm.title,
        "detail": alarm.detail,
        "regulation_id": alarm.regulation_id or "",
        "effective_date": alarm.effective_date or "",
        "timestamp": alarm.timestamp,
        "alarm_id": alarm.id,
    }


def dispatch_compliance_alarms_to_rtdb(
    limit: int = 100,
    dedup: bool = True,
) -> dict[str, Any]:
    """알람 수집 → 신규만 RTDB push.

    Args:
        limit: alarm_aggregator 에서 가져올 최대 알람 수.
        dedup: True (기본) — 이미 push 된 alarm_id 는 skip. False — 모두 재 push (debug).

    Returns:
        {"collected": int, "pushed": int, "skipped": int, "details": list[dict]}
    """
    alarms = collect_recent_alarms(limit=limit)
    if not alarms:
        return {"collected": 0, "pushed": 0, "skipped": 0, "details": []}

    _PUSHED_STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    pushed_count = 0
    skipped_count = 0
    details: list[dict[str, Any]] = []

    with sqlite3.connect(_PUSHED_STATE_DB) as conn:
        _ensure_state_table(conn)
        already_pushed = _load_pushed_ids(conn) if dedup else set()

        for alarm in alarms:
            if alarm.id in already_pushed:
                skipped_count += 1
                continue

            payload = _to_rtdb_payload(alarm)
            try:
                rtdb_key = push_alarm(payload, path=_RTDB_PATH)
            except Exception as e:
                logger.exception("[d1_alert] RTDB push 실패 alarm_id=%s: %s", alarm.id, e)
                continue

            _mark_pushed(conn, alarm.id, rtdb_key)
            pushed_count += 1
            details.append({
                "alarm_id": alarm.id,
                "module": alarm.module,
                "severity": alarm.severity,
                "rtdb_key": rtdb_key,
            })

    logger.info(
        "[d1_alert] dispatch 완료 collected=%d pushed=%d skipped=%d",
        len(alarms),
        pushed_count,
        skipped_count,
    )
    return {
        "collected": len(alarms),
        "pushed": pushed_count,
        "skipped": skipped_count,
        "details": details,
    }
