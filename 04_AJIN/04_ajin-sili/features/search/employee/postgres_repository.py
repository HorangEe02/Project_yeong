"""Postgres employee repository.

기존 employees SQLite DB를 즉시 제거하지 않고, admin/ERP sync가 real 직원
데이터를 Postgres에도 upsert할 수 있는 좁은 저장 계층이다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

from core.data_lineage import lineage_values
from core.db import create_sqlalchemy_engine, is_postgres_enabled

_METADATA = sa.MetaData()

_EMPLOYEES = sa.Table(
    "employees",
    _METADATA,
    sa.Column("employee_id", sa.String(80), primary_key=True),
    sa.Column("canonical_employee_id", sa.String(80), nullable=False, server_default=""),
    sa.Column("name", sa.String(160), nullable=False, server_default=""),
    sa.Column("department", sa.String(160), nullable=False, server_default=""),
    sa.Column("position", sa.String(160), nullable=False, server_default=""),
    sa.Column("email", sa.String(255), nullable=False, server_default=""),
    sa.Column("phone", sa.String(80), nullable=False, server_default=""),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("data_class", sa.String(32), nullable=False, server_default="real"),
    sa.Column("source_system", sa.String(80), nullable=False, server_default="admin_ui"),
    sa.Column("source_label", sa.String(255), nullable=False, server_default=""),
    sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
)


def _engine():
    """Create the configured SQLAlchemy engine."""
    return create_sqlalchemy_engine()


def _ensure_sqlite_table(engine) -> None:
    """Create fallback SQLite table for local tests."""
    if engine.dialect.name == "sqlite":
        _METADATA.create_all(engine, tables=[_EMPLOYEES])


def _as_bool(value: Any) -> bool:
    """Normalize mixed SQLite/Python truthy values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() not in {"", "0", "false", "no", "off", "none"}


def upsert_employee(employee: dict[str, Any]) -> str | None:
    """Upsert one real employee into Postgres when enabled.

    Args:
        employee: Employee dict from admin UI or ERP CSV sync.

    Returns:
        str | None: Employee id when Postgres is enabled, otherwise None.

    Raises:
        ValueError: If `employee_id` is missing while Postgres is enabled.
    """
    if not is_postgres_enabled():
        return None
    employee_id = str(employee.get("employee_id") or "").strip()
    if not employee_id:
        raise ValueError("employee_id is required")
    now = datetime.now(timezone.utc)
    source_system = str(employee.get("source_system") or "admin_ui")
    lineage = lineage_values(str(employee.get("data_class") or "real"), source_system, source_system)
    row = {
        "employee_id": employee_id,
        "canonical_employee_id": str(employee.get("canonical_employee_id") or employee_id),
        "name": str(employee.get("name") or ""),
        "department": str(employee.get("department") or ""),
        "position": str(employee.get("position") or ""),
        "email": str(employee.get("email") or ""),
        "phone": str(employee.get("phone") or ""),
        "is_active": _as_bool(employee.get("is_active", 1)),
        "created_at": now,
        "updated_at": now,
        "data_class": lineage["data_class"],
        "source_system": lineage["source_system"],
        "source_label": lineage["source_label"],
        "source_updated_at": now,
    }
    engine = _engine()
    _ensure_sqlite_table(engine)
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(_EMPLOYEES).values(**row)
            stmt = stmt.on_conflict_do_update(
                index_elements=["employee_id"],
                set_={
                    "canonical_employee_id": stmt.excluded.canonical_employee_id,
                    "name": stmt.excluded.name,
                    "department": stmt.excluded.department,
                    "position": stmt.excluded.position,
                    "email": stmt.excluded.email,
                    "phone": stmt.excluded.phone,
                    "is_active": stmt.excluded.is_active,
                    "updated_at": stmt.excluded.updated_at,
                    "data_class": stmt.excluded.data_class,
                    "source_system": stmt.excluded.source_system,
                    "source_label": stmt.excluded.source_label,
                    "source_updated_at": stmt.excluded.source_updated_at,
                },
            )
            conn.execute(stmt)
        else:
            conn.execute(sa.text("DELETE FROM employees WHERE employee_id = :employee_id"), {"employee_id": employee_id})
            conn.execute(_EMPLOYEES.insert().values(**row))
    return employee_id
