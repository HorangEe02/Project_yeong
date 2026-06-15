"""Postgres-backed live event and alarm service.

Firebase RTDB를 대체하는 표준 알람 경로다. 운영에서는 Alembic이 만든
Postgres `live_alarms` 테이블을 사용하고, 로컬/테스트 기본값에서는
`core.db`의 SQLite URL에 같은 테이블을 멱등 생성해 동작한다.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

from core.data_lineage import lineage_values
from core.db import create_sqlalchemy_engine

_METADATA = sa.MetaData()

_LIVE_ALARMS = sa.Table(
    "live_alarms",
    _METADATA,
    sa.Column("id", sa.String(80), primary_key=True),
    sa.Column("domain", sa.String(80), nullable=False, server_default="equipment"),
    sa.Column("severity", sa.String(40), nullable=False, server_default="info"),
    sa.Column("message", sa.Text, nullable=False),
    sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("data_class", sa.String(32), nullable=False, server_default="unknown"),
    sa.Column("source_system", sa.String(80), nullable=False, server_default="unknown"),
    sa.Column("source_label", sa.String(255), nullable=False, server_default=""),
    sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
)


def _engine():
    """Create the current application DB engine."""
    return create_sqlalchemy_engine()


def _ensure_sqlite_table(engine) -> None:
    """Create fallback SQLite tables for local development and tests only.

    Args:
        engine: SQLAlchemy engine returned by `core.db`.
    """
    if engine.dialect.name == "sqlite":
        _METADATA.create_all(engine, tables=[_LIVE_ALARMS])


def _payload_message(payload: dict[str, Any]) -> str:
    """Derive a compact alarm message from arbitrary event payload."""
    return (
        str(payload.get("message") or "")
        or str(payload.get("description") or "")
        or str(payload.get("type") or "live alarm")
    )


def normalize_alarm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy RTDB-shaped payloads for the new live_alarms table.

    Args:
        payload: Legacy or new alarm payload.

    Returns:
        dict[str, Any]: Payload with stable `id`, `severity`, `message`, and timestamp fields.
    """
    now = datetime.now(timezone.utc)
    alarm_id = str(payload.get("id") or f"alarm-{uuid.uuid4().hex[:12]}")
    raw_severity = str(payload.get("severity") or "info")
    severity = raw_severity.upper() if raw_severity.isupper() else raw_severity.lower()
    normalized = dict(payload)
    normalized.setdefault("id", alarm_id)
    normalized.setdefault("message", _payload_message(payload))
    normalized.setdefault("detected_at", now.isoformat())
    normalized["severity"] = severity
    return normalized


def insert_alarm(
    payload: dict[str, Any],
    *,
    domain: str = "equipment",
    data_class: str = "real",
    source_system: str = "live_events",
    source_label: str = "live_events",
) -> str:
    """Insert or update a live alarm.

    Args:
        payload: Alarm payload. Existing RTDB alarm payloads are accepted.
        domain: Alarm domain, for example `equipment` or `compliance`.
        data_class: Lineage data class.
        source_system: Lineage source system.
        source_label: Human-readable lineage label.

    Returns:
        str: Alarm id.
    """
    alarm = normalize_alarm_payload(payload)
    alarm_id = str(alarm["id"])
    now = datetime.now(timezone.utc)
    lineage = lineage_values(data_class, source_system, source_label)
    source_updated_at = lineage.get("source_updated_at") or now.isoformat()
    try:
        source_updated_dt = datetime.fromisoformat(source_updated_at)
    except ValueError:
        source_updated_dt = now

    engine = _engine()
    _ensure_sqlite_table(engine)
    row = {
        "id": alarm_id,
        "domain": domain,
        "severity": str(alarm.get("severity") or "info"),
        "message": _payload_message(alarm),
        "payload": alarm,
        "created_at": now,
        "data_class": lineage["data_class"],
        "source_system": lineage["source_system"],
        "source_label": lineage["source_label"],
        "source_updated_at": source_updated_dt,
    }
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(_LIVE_ALARMS).values(**row)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "severity": stmt.excluded.severity,
                    "message": stmt.excluded.message,
                    "payload": stmt.excluded.payload,
                    "domain": stmt.excluded.domain,
                    "source_updated_at": stmt.excluded.source_updated_at,
                },
            )
            conn.execute(stmt)
        else:
            conn.execute(sa.text("DELETE FROM live_alarms WHERE id = :id"), {"id": alarm_id})
            conn.execute(_LIVE_ALARMS.insert().values(**row))
    return alarm_id


def list_recent_alarms(domain: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """List recent live alarms.

    Args:
        domain: Optional domain filter.
        limit: Maximum row count.

    Returns:
        list[dict[str, Any]]: Recent alarms ordered newest first.
    """
    engine = _engine()
    _ensure_sqlite_table(engine)
    conditions = []
    if domain:
        conditions.append(_LIVE_ALARMS.c.domain == domain)
    stmt = (
        sa.select(_LIVE_ALARMS)
        .where(*conditions)
        .order_by(_LIVE_ALARMS.c.created_at.desc())
        .limit(max(1, min(int(limit), 200)))
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()

    out: list[dict[str, Any]] = []
    for row in rows:
        payload = row.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        created_at = row.get("created_at")
        acknowledged_at = row.get("acknowledged_at")
        out.append(
            {
                "id": row["id"],
                "domain": row["domain"],
                "severity": row["severity"],
                "message": row["message"],
                "payload": payload,
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at or ""),
                "acknowledged_at": acknowledged_at.isoformat()
                if hasattr(acknowledged_at, "isoformat")
                else acknowledged_at,
            }
        )
    return out


def acknowledge_alarm(alarm_id: str) -> bool:
    """Mark a live alarm as acknowledged.

    Args:
        alarm_id: Alarm id.

    Returns:
        bool: True when a row was updated.
    """
    engine = _engine()
    _ensure_sqlite_table(engine)
    with engine.begin() as conn:
        res = conn.execute(
            _LIVE_ALARMS.update()
            .where(_LIVE_ALARMS.c.id == alarm_id)
            .values(acknowledged_at=datetime.now(timezone.utc))
        )
        return bool(res.rowcount)
