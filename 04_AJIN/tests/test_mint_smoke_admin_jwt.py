"""Tests for the Cloud Run smoke SYS_ADMIN JWT minting command."""

from __future__ import annotations

import json
import stat
from datetime import datetime, timezone

import jwt
import pytest
import sqlalchemy as sa

from scripts.bootstrap_supabase_sys_admin import DEFAULT_ROLES, DEFAULT_SYS_ADMIN
from scripts.mint_smoke_admin_jwt import (
    SmokeTokenSpec,
    mint_smoke_admin_jwt,
    mint_smoke_admin_token,
    resolve_jwt_secret,
    validate_smoke_environment,
)


@pytest.fixture()
def engine() -> sa.Engine:
    """Create an in-memory schema compatible with admin posture checks.

    Returns:
        sa.Engine: SQLite engine with an attached ``public`` schema alias.
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
                    role_id integer not null references roles(role_id),
                    is_active boolean not null default true
                )
                """
            )
        )
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
    return engine


def _insert_user(
    engine: sa.Engine,
    employee_id: str,
    role_name: str,
    *,
    active: bool = True,
) -> None:
    """Insert a user row with a role lookup.

    Args:
        engine: Test database engine.
        employee_id: Employee id to insert.
        role_name: Role name to assign.
        active: Whether the user is active.
    """

    with engine.begin() as connection:
        role_id = connection.execute(
            sa.text("select role_id from public.roles where role_name = :role_name"),
            {"role_name": role_name},
        ).scalar_one()
        connection.execute(
            sa.text(
                """
                insert into public.users (employee_id, username, role_id, is_active)
                values (:employee_id, :username, :role_id, :is_active)
                """
            ),
            {
                "employee_id": employee_id,
                "username": f"user-{employee_id}",
                "role_id": role_id,
                "is_active": active,
            },
        )


def test_mint_writes_owner_only_token_and_redacts_stdout_summary(
    engine: sa.Engine,
    tmp_path,
    monkeypatch,
) -> None:
    """Minting writes a JWT file but excludes the token and secret from summaries."""

    secret = "test-secret-for-smoke-token-32-bytes"
    monkeypatch.setenv("AJIN_JWT_SECRET", secret)
    _insert_user(engine, DEFAULT_SYS_ADMIN.employee_id, "SYS_ADMIN")
    token_file = tmp_path / "smoke-admin.jwt"

    result = mint_smoke_admin_jwt(
        engine,
        token_spec=SmokeTokenSpec(
            employee_id=DEFAULT_SYS_ADMIN.employee_id,
            username=DEFAULT_SYS_ADMIN.username,
            role_name="SYS_ADMIN",
            ttl_minutes=15,
        ),
        output_file=token_file,
    )

    token = token_file.read_text(encoding="utf-8").strip()
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    rendered = json.dumps(result, default=str, ensure_ascii=False)

    assert decoded["sub"] == DEFAULT_SYS_ADMIN.employee_id
    assert decoded["role"] == "SYS_ADMIN"
    assert decoded["role_level"] == 5
    assert decoded["purpose"] == "cloud_run_smoke"
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
    assert "token" not in result
    assert token not in rendered
    assert secret not in rendered


def test_print_flag_is_required_to_return_token(
    engine: sa.Engine,
    tmp_path,
    monkeypatch,
) -> None:
    """The token appears in the result only when explicitly requested."""

    monkeypatch.setenv("AJIN_JWT_SECRET", "print-allowed-secret-32-byte-value")
    _insert_user(engine, DEFAULT_SYS_ADMIN.employee_id, "SYS_ADMIN")

    result = mint_smoke_admin_jwt(
        engine,
        token_spec=SmokeTokenSpec(
            employee_id=DEFAULT_SYS_ADMIN.employee_id,
            username=DEFAULT_SYS_ADMIN.username,
            role_name="SYS_ADMIN",
            ttl_minutes=15,
        ),
        output_file=tmp_path / "smoke-admin.jwt",
        print_token=True,
    )

    assert result["token"]


def test_mint_refuses_legacy_active_default_admin(
    engine: sa.Engine,
    tmp_path,
    monkeypatch,
) -> None:
    """A legacy active admin account blocks smoke-token minting."""

    monkeypatch.setenv("AJIN_JWT_SECRET", "blocked-secret-32-byte-test-value")
    _insert_user(engine, "admin", "SYS_ADMIN")
    _insert_user(engine, DEFAULT_SYS_ADMIN.employee_id, "SYS_ADMIN")

    with pytest.raises(RuntimeError, match="active default admin"):
        mint_smoke_admin_jwt(
            engine,
            token_spec=SmokeTokenSpec(
                employee_id=DEFAULT_SYS_ADMIN.employee_id,
                username=DEFAULT_SYS_ADMIN.username,
                role_name="SYS_ADMIN",
                ttl_minutes=15,
            ),
            output_file=tmp_path / "smoke-admin.jwt",
        )


def test_mint_requires_target_active_sys_admin(
    engine: sa.Engine,
    tmp_path,
    monkeypatch,
) -> None:
    """A non-SYS_ADMIN target cannot receive a deploy-smoke token."""

    monkeypatch.setenv("AJIN_JWT_SECRET", "target-secret-32-byte-test-value")
    _insert_user(engine, DEFAULT_SYS_ADMIN.employee_id, "EMPLOYEE")

    with pytest.raises(RuntimeError, match="not an active SYS_ADMIN"):
        mint_smoke_admin_jwt(
            engine,
            token_spec=SmokeTokenSpec(
                employee_id=DEFAULT_SYS_ADMIN.employee_id,
                username=DEFAULT_SYS_ADMIN.username,
                role_name="SYS_ADMIN",
                ttl_minutes=15,
            ),
            output_file=tmp_path / "smoke-admin.jwt",
        )


def test_validate_smoke_environment_requires_jwt_secret(monkeypatch) -> None:
    """Environment validation fails closed when AJIN_JWT_SECRET is absent."""

    monkeypatch.setenv("SUPABASE_PROJECT_REF", "ycjuzwltwbeudanjykag")
    monkeypatch.setenv("APP_DB_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:secret@example.supabase.co/postgres")
    monkeypatch.setenv("SUPABASE_URL", "https://ycjuzwltwbeudanjykag.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_DO_NOT_PRINT")
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_" + ("a" * 40))
    monkeypatch.setenv("FIREBASE_WRITE_ENABLED", "false")
    monkeypatch.setenv("FIREBASE_READ_FALLBACK_ENABLED", "false")
    monkeypatch.delenv("AJIN_JWT_SECRET", raising=False)

    issues = validate_smoke_environment("ycjuzwltwbeudanjykag")

    assert {issue.name for issue in issues} == {"AJIN_JWT_SECRET"}


def test_jwt_secret_file_can_replace_env(monkeypatch, tmp_path) -> None:
    """A 0600 local file can supply the Cloud Run-compatible JWT secret."""

    secret_file = tmp_path / "ajin-jwt-secret.txt"
    secret_file.write_text("file-secret-32-byte-test-value\n", encoding="utf-8")
    secret_file.chmod(0o600)
    monkeypatch.delenv("AJIN_JWT_SECRET", raising=False)

    secret, source = resolve_jwt_secret(secret_file)

    assert secret == "file-secret-32-byte-test-value"
    assert source == f"file:{secret_file}"


def test_jwt_secret_file_requires_owner_only_permissions(tmp_path) -> None:
    """Group-readable local secret files are rejected before token minting."""

    secret_file = tmp_path / "ajin-jwt-secret.txt"
    secret_file.write_text("file-secret-32-byte-test-value\n", encoding="utf-8")
    secret_file.chmod(0o640)

    with pytest.raises(PermissionError, match="readable only by the owner"):
        resolve_jwt_secret(secret_file)


def test_token_ttl_must_be_short() -> None:
    """Smoke tokens are intentionally limited to one hour or less."""

    with pytest.raises(ValueError, match="ttl_minutes"):
        mint_smoke_admin_token(
            spec=SmokeTokenSpec(
                employee_id=DEFAULT_SYS_ADMIN.employee_id,
                username=DEFAULT_SYS_ADMIN.username,
                role_name="SYS_ADMIN",
                ttl_minutes=61,
            ),
            jwt_secret="secret",
            now=datetime(2026, 5, 19, tzinfo=timezone.utc),
        )
