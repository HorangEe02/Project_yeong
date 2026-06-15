"""Feedback event persistence.

프론트의 RTDB 직접 write를 대체하는 서버 측 저장 경로다. 운영에서는
Postgres `feedback_events` 테이블을 사용하고, 로컬/테스트에서는 같은
스키마를 SQLite에 멱등 생성한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

from core.data_lineage import lineage_values
from core.db import create_sqlalchemy_engine

_METADATA = sa.MetaData()

_FEEDBACK_EVENTS = sa.Table(
    "feedback_events",
    _METADATA,
    sa.Column("id", sa.String(80), primary_key=True),
    sa.Column("message_id", sa.String(120), nullable=False),
    sa.Column("employee_id", sa.String(80), nullable=False, server_default="anonymous"),
    sa.Column("rating", sa.String(32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("data_class", sa.String(32), nullable=False, server_default="real"),
    sa.Column("source_system", sa.String(80), nullable=False, server_default="backend_api"),
    sa.Column("source_label", sa.String(255), nullable=False, server_default="feedback"),
    sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
)


def _engine():
    """Create the configured application DB engine."""
    return create_sqlalchemy_engine()


def _ensure_sqlite_table(engine) -> None:
    """Create fallback SQLite tables for local development and tests.

    Args:
        engine: SQLAlchemy engine returned by `core.db`.
    """
    if engine.dialect.name == "sqlite":
        _METADATA.create_all(engine, tables=[_FEEDBACK_EVENTS])


def record_feedback_event(
    *,
    message_id: str,
    rating: str,
    employee_id: str = "anonymous",
    metadata: dict[str, Any] | None = None,
) -> str:
    """Persist one feedback event.

    Args:
        message_id: Chat or draft message id that received feedback.
        rating: Feedback rating. Currently `thumbs_up` or `thumbs_down`.
        employee_id: Authenticated employee id, or `anonymous`.
        metadata: Reserved diagnostic metadata. Stored later when the schema
            gains a JSON column.

    Returns:
        str: Created feedback event id.

    Raises:
        ValueError: If required fields are missing or rating is unsupported.
    """
    del metadata
    normalized_rating = rating.strip()
    if not message_id.strip():
        raise ValueError("message_id is required")
    if normalized_rating not in {"thumbs_up", "thumbs_down"}:
        raise ValueError("rating must be thumbs_up or thumbs_down")

    now = datetime.now(timezone.utc)
    lineage = lineage_values("real", "backend_api", "feedback")
    event_id = f"feedback-{uuid.uuid4().hex[:12]}"
    row = {
        "id": event_id,
        "message_id": message_id.strip(),
        "employee_id": employee_id.strip() or "anonymous",
        "rating": normalized_rating,
        "created_at": now,
        "data_class": lineage["data_class"],
        "source_system": lineage["source_system"],
        "source_label": lineage["source_label"],
        "source_updated_at": now,
    }

    engine = _engine()
    _ensure_sqlite_table(engine)
    with engine.begin() as conn:
        conn.execute(_FEEDBACK_EVENTS.insert().values(**row))
    return event_id
