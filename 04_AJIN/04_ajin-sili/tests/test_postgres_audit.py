"""Postgres audit repository tests."""

from __future__ import annotations

import sqlalchemy as sa

from core.auth import postgres_audit
from core.db import create_sqlalchemy_engine


def test_write_login_event_resolves_remote_user_id_by_employee(monkeypatch, tmp_path):
    """Audit rows use the remote user id, not the SQLite mirror id."""

    db_url = f"sqlite:///{tmp_path / 'audit.db'}"
    monkeypatch.setenv("APP_DB_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", db_url)

    engine = create_sqlalchemy_engine()
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                create table users (
                    user_id integer primary key,
                    employee_id text not null unique
                )
                """
            )
        )
        conn.execute(
            sa.text("insert into users (user_id, employee_id) values (42, 'SYS-0001')")
        )

    event_id = postgres_audit.write_login_event(
        user_id=999,
        employee_id="SYS-0001",
        success=True,
    )

    with engine.connect() as conn:
        row = (
            conn.execute(
                sa.text("select user_id, employee_id from login_history where id = :id"),
                {"id": event_id},
            )
            .mappings()
            .one()
        )

    assert row["user_id"] == 42
    assert row["employee_id"] == "SYS-0001"


def test_write_login_event_omits_user_id_when_remote_user_missing(monkeypatch, tmp_path):
    """Missing remote users should not make nullable login_history inserts fail."""

    db_url = f"sqlite:///{tmp_path / 'audit.db'}"
    monkeypatch.setenv("APP_DB_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", db_url)

    event_id = postgres_audit.write_login_event(
        user_id=999,
        employee_id="UNKNOWN",
        success=False,
    )

    engine = create_sqlalchemy_engine()
    with engine.connect() as conn:
        row = (
            conn.execute(
                sa.text("select user_id, employee_id from login_history where id = :id"),
                {"id": event_id},
            )
            .mappings()
            .one()
        )

    assert row["user_id"] is None
    assert row["employee_id"] == "UNKNOWN"
