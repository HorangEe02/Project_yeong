"""Tests for the Supabase SYS_ADMIN bootstrap command."""

from __future__ import annotations

import json
import stat

import pytest
import sqlalchemy as sa

from core.auth.password import verify_password
from scripts.bootstrap_supabase_sys_admin import (
    DEFAULT_ROLES,
    DEFAULT_SYS_ADMIN,
    bootstrap_sys_admin,
)


@pytest.fixture()
def engine() -> sa.Engine:
    """Create an in-memory schema compatible with the bootstrap SQL.

    Returns:
        sa.Engine: SQLite engine with attached public schema alias.
    """

    engine = sa.create_engine("sqlite://", future=True)
    with engine.begin() as connection:
        connection.execute(sa.text("attach database ':memory:' as public"))
        connection.execute(
            sa.text(
                """
                create table public.roles (
                    role_id integer primary key autoincrement,
                    role_name text not null unique,
                    role_level integer not null default 1,
                    description text not null default '',
                    created_at text default current_timestamp
                )
                """
            )
        )
        connection.execute(
            sa.text(
                """
                create table public.users (
                    user_id integer primary key autoincrement,
                    employee_id text not null unique,
                    username text not null,
                    email text not null default '',
                    phone text not null default '',
                    department text not null default '',
                    position text not null default '',
                    password_hash text not null default '',
                    role_id integer not null references roles(role_id),
                    is_active boolean not null default true,
                    must_change_pw boolean not null default true,
                    data_class text not null default 'unknown',
                    source_system text not null default 'unknown',
                    source_label text not null default '',
                    source_updated_at text
                )
                """
            )
        )
    return engine


def test_dry_run_reports_missing_roles_without_mutation(
    engine: sa.Engine,
    tmp_path,
) -> None:
    """Dry-run reports planned work but does not write roles, users, or password."""

    password_file = tmp_path / "initial-password.txt"
    result = bootstrap_sys_admin(engine, apply=False, password_file=password_file)

    assert result["mode"] == "dry_run"
    assert result["sys_admin_action"] == "would_create"
    assert result["roles_missing"] == sorted(role.role_name for role in DEFAULT_ROLES)
    assert not password_file.exists()
    with engine.connect() as connection:
        role_count = connection.execute(sa.text("select count(*) from public.roles")).scalar_one()
        user_count = connection.execute(sa.text("select count(*) from public.users")).scalar_one()
    assert role_count == 0
    assert user_count == 0


def test_apply_creates_roles_and_named_admin_without_default_admin(
    engine: sa.Engine,
    tmp_path,
) -> None:
    """Apply seeds six roles and creates only the named SYS_ADMIN account."""

    password_file = tmp_path / "initial-password.txt"
    result = bootstrap_sys_admin(engine, apply=True, password_file=password_file)

    assert result["sys_admin_action"] == "created"
    assert result["password_file_written"] is True
    assert stat.S_IMODE(password_file.stat().st_mode) == 0o600

    with engine.connect() as connection:
        roles = connection.execute(
            sa.text("select role_name from public.roles order by role_name")
        ).scalars().all()
        users = connection.execute(
            sa.text(
                """
                select u.employee_id,
                       u.username,
                       u.department,
                       u.position,
                       u.password_hash,
                       u.must_change_pw,
                       u.data_class,
                       u.source_system,
                       r.role_name
                  from public.users u
                  join public.roles r on r.role_id = u.role_id
                 order by u.employee_id
                """
            )
        ).mappings().all()

    assert roles == sorted(role.role_name for role in DEFAULT_ROLES)
    assert len(users) == 1
    row = dict(users[0])
    assert row["employee_id"] == DEFAULT_SYS_ADMIN.employee_id
    assert row["username"] == DEFAULT_SYS_ADMIN.username
    assert row["department"] == DEFAULT_SYS_ADMIN.department
    assert row["position"] == DEFAULT_SYS_ADMIN.position
    assert row["role_name"] == "SYS_ADMIN"
    assert bool(row["must_change_pw"]) is True
    assert row["data_class"] == "system"
    assert row["source_system"] == "supabase_cutover"
    assert verify_password(password_file.read_text(encoding="utf-8").strip(), row["password_hash"])


def test_apply_is_noop_when_named_sys_admin_already_exists(
    engine: sa.Engine,
    tmp_path,
) -> None:
    """Existing active named SYS_ADMIN accounts prevent duplicate creation."""

    password_file = tmp_path / "initial-password.txt"
    bootstrap_sys_admin(engine, apply=True, password_file=password_file)
    existing_password = password_file.read_text(encoding="utf-8")
    result = bootstrap_sys_admin(engine, apply=True, password_file=password_file)

    assert result["sys_admin_action"] == "already_satisfied"
    assert result["password_file_written"] is False
    assert password_file.read_text(encoding="utf-8") == existing_password
    with engine.connect() as connection:
        user_count = connection.execute(sa.text("select count(*) from public.users")).scalar_one()
    assert user_count == 1


def test_active_default_admin_blocks_bootstrap(
    engine: sa.Engine,
    tmp_path,
) -> None:
    """The bootstrap refuses to hide a legacy active admin blocker."""

    with engine.begin() as connection:
        for role in DEFAULT_ROLES:
            connection.execute(
                sa.text(
                    """
                    insert into public.roles (role_name, role_level, description)
                    values (:role_name, :role_level, :description)
                    """
                ),
                {
                    "role_name": role.role_name,
                    "role_level": role.role_level,
                    "description": role.description,
                },
            )
        connection.execute(
            sa.text(
                """
                insert into public.users (
                    employee_id,
                    username,
                    password_hash,
                    role_id,
                    is_active
                ) values ('admin', '시스템관리자', 'hash', :role_id, true)
                """
            ),
            {
                "role_id": connection.execute(
                    sa.text("select role_id from public.roles where role_name='SYS_ADMIN'")
                ).scalar_one()
            },
        )

    with pytest.raises(RuntimeError, match="active default admin"):
        bootstrap_sys_admin(engine, apply=True, password_file=tmp_path / "pw.txt")


def test_bootstrap_summary_does_not_contain_initial_password(
    engine: sa.Engine,
    tmp_path,
) -> None:
    """The generated password stays out of JSON-safe bootstrap summaries."""

    password_file = tmp_path / "initial-password.txt"
    result = bootstrap_sys_admin(engine, apply=True, password_file=password_file)
    password = password_file.read_text(encoding="utf-8").strip()
    rendered = json.dumps(result, default=str, ensure_ascii=False)

    assert password
    assert password not in rendered
