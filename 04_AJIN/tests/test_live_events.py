"""Postgres replacement live event service tests."""

from __future__ import annotations

import os

from backend.services.feedback_events import record_feedback_event
from backend.services.live_events import acknowledge_alarm, insert_alarm, list_recent_alarms


def _use_tmp_db(monkeypatch, tmp_path) -> None:
    """Point SQLAlchemy app DB helpers at a temporary SQLite file."""
    monkeypatch.setenv("APP_DB_BACKEND", "sqlite")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'events.db'}")


def test_live_events_insert_list_and_ack(monkeypatch, tmp_path) -> None:
    """live_alarms row can be inserted, listed, and acknowledged."""
    _use_tmp_db(monkeypatch, tmp_path)

    alarm_id = insert_alarm(
        {
            "id": "alarm-1",
            "severity": "CRITICAL",
            "description": "SPC violation",
            "process": "cch",
        },
        domain="equipment",
        source_system="plc_ingest",
        source_label="plc_ingest",
    )

    assert alarm_id == "alarm-1"
    rows = list_recent_alarms(domain="equipment", limit=10)
    assert len(rows) == 1
    assert rows[0]["id"] == "alarm-1"
    assert rows[0]["message"] == "SPC violation"
    assert rows[0]["payload"]["process"] == "cch"
    assert rows[0]["acknowledged_at"] is None

    assert acknowledge_alarm("alarm-1") is True
    assert acknowledge_alarm("missing") is False
    acked = list_recent_alarms(domain="equipment", limit=10)
    assert acked[0]["acknowledged_at"]


def test_feedback_event_records_without_firebase(monkeypatch, tmp_path) -> None:
    """Feedback API storage path persists through the app DB instead of RTDB."""
    _use_tmp_db(monkeypatch, tmp_path)
    monkeypatch.setenv("FIREBASE_WRITE_ENABLED", "false")

    event_id = record_feedback_event(
        message_id="msg-1",
        rating="thumbs_up",
        employee_id="E001",
    )

    assert event_id.startswith("feedback-")
    assert os.environ["FIREBASE_WRITE_ENABLED"] == "false"
