"""Postgres audit repository.

Firestore audit shadow를 대체하는 Postgres 기반 로그인 이벤트 저장/조회
계층이다. `APP_DB_BACKEND=postgres`일 때만 활성화되고, 로컬 SQLite fallback
테스트에서는 같은 테이블을 멱등 생성한다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa

from core.data_lineage import lineage_values
from core.db import create_sqlalchemy_engine, is_postgres_enabled

_METADATA = sa.MetaData()

_LOGIN_HISTORY = sa.Table(
    "login_history",
    _METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.Integer, nullable=True),
    sa.Column("employee_id", sa.String(80), nullable=False),
    sa.Column("action", sa.String(80), nullable=False, server_default="login"),
    sa.Column("success", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("ip_address", sa.String(120), nullable=False, server_default=""),
    sa.Column("user_agent", sa.Text, nullable=False, server_default=""),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("data_class", sa.String(32), nullable=False, server_default="real"),
    sa.Column("source_system", sa.String(80), nullable=False, server_default="backend_api"),
    sa.Column("source_label", sa.String(255), nullable=False, server_default="auth_login"),
    sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
)


def is_available() -> bool:
    """Return whether Postgres audit should be used."""
    return is_postgres_enabled()


def _engine():
    """Create the configured SQLAlchemy engine."""
    return create_sqlalchemy_engine()


def _ensure_sqlite_table(engine) -> None:
    """Create SQLite fallback table for tests."""
    if engine.dialect.name == "sqlite":
        _METADATA.create_all(engine, tables=[_LOGIN_HISTORY])


def _resolve_remote_user_id(conn, employee_id: str) -> int | None:
    """Resolve the Postgres-side user id for an employee id.

    Args:
        conn: Active SQLAlchemy connection.
        employee_id: Stable employee id from the login request.

    Returns:
        int | None: Matching ``public.users.user_id`` when available, otherwise
        ``None`` so nullable audit rows can still be written.
    """

    if not employee_id:
        return None

    # The auth router still authenticates against a local SQLite mirror. Its
    # autoincrement user_id can drift from Supabase/Postgres, so audit rows must
    # key by employee_id and resolve the remote FK at insert time.
    if conn.engine.dialect.name == "postgresql":
        statement = sa.text(
            "select user_id from public.users where employee_id = :employee_id limit 1"
        )
    else:
        statement = sa.text(
            "select user_id from users where employee_id = :employee_id limit 1"
        )

    try:
        row = conn.execute(statement, {"employee_id": employee_id}).mappings().first()
    except Exception:
        return None
    if not row or row.get("user_id") is None:
        return None
    return int(row["user_id"])


def write_login_event(
    user_id: int | str,
    employee_id: str,
    success: bool,
    ip_address: str = "",
    user_agent: str = "",
    department: str = "",
    role_level: int = 0,
) -> str | None:
    """Write a login event to Postgres login_history.

    Args:
        user_id: Application user id.
        employee_id: Employee id.
        success: Login success flag.
        ip_address: Request IP address.
        user_agent: Request user agent.
        department: Reserved for future analytics dimensions.
        role_level: Reserved for future analytics dimensions.

    Returns:
        str | None: Created event id, or None when Postgres audit is disabled.
    """
    del user_id
    del department, role_level
    if not is_available():
        return None
    now = datetime.now(timezone.utc)
    lineage = lineage_values("real", "backend_api", "auth_login")
    row = {
        "user_id": None,
        "employee_id": employee_id,
        "action": "login",
        "success": bool(success),
        "ip_address": ip_address or "",
        "user_agent": user_agent or "",
        "created_at": now,
        "data_class": lineage["data_class"],
        "source_system": lineage["source_system"],
        "source_label": lineage["source_label"],
        "source_updated_at": now,
    }
    engine = _engine()
    _ensure_sqlite_table(engine)
    with engine.begin() as conn:
        row["user_id"] = _resolve_remote_user_id(conn, employee_id)
        result = conn.execute(_LOGIN_HISTORY.insert().values(**row))
    inserted = result.inserted_primary_key
    return str(inserted[0]) if inserted else "postgres-login-event"


def _rows_since(days: int) -> list[dict[str, Any]]:
    """Read login rows newer than the given day window."""
    engine = _engine()
    _ensure_sqlite_table(engine)
    cutoff = datetime.combine(date.today() - timedelta(days=days), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    stmt = (
        sa.select(_LOGIN_HISTORY)
        .where(_LOGIN_HISTORY.c.created_at >= cutoff)
        .where(_LOGIN_HISTORY.c.data_class == "real")
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(stmt).mappings().all()]


def read_login_stats(days: int = 30) -> dict[str, Any]:
    """Read aggregate login stats from Postgres."""
    if not is_available():
        raise RuntimeError("postgres audit disabled")
    rows = _rows_since(days)
    total = len(rows)
    success = sum(1 for row in rows if int(row.get("success") or 0) == 1)
    unique_users = {row.get("employee_id") for row in rows if row.get("employee_id")}
    return {
        "total": total,
        "success": success,
        "failed": total - success,
        "success_rate": success / total if total else 0.0,
        "unique_users": len(unique_users),
    }


def read_hour_distribution(days: int = 30) -> dict[int, int]:
    """Read successful-login distribution by hour."""
    if not is_available():
        raise RuntimeError("postgres audit disabled")
    buckets: dict[int, int] = {hour: 0 for hour in range(24)}
    for row in _rows_since(days):
        if int(row.get("success") or 0) != 1:
            continue
        ts = row.get("created_at")
        if hasattr(ts, "hour"):
            buckets[int(ts.hour)] += 1
    return buckets


def read_recent_logins(limit: int = 50) -> list[dict[str, Any]]:
    """Read recent login events from Postgres."""
    if not is_available():
        raise RuntimeError("postgres audit disabled")
    engine = _engine()
    _ensure_sqlite_table(engine)
    stmt = (
        sa.select(_LOGIN_HISTORY)
        .where(_LOGIN_HISTORY.c.action == "login")
        .where(_LOGIN_HISTORY.c.data_class == "real")
        .order_by(_LOGIN_HISTORY.c.created_at.desc())
        .limit(max(1, min(int(limit), 200)))
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    out: list[dict[str, Any]] = []
    for row in rows:
        ts = row.get("created_at")
        out.append(
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "employee_id": row["employee_id"],
                "action": row["action"],
                "success": int(row["success"]),
                "ip_address": row["ip_address"],
                "user_agent": row["user_agent"],
                "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts or ""),
            }
        )
    return out
