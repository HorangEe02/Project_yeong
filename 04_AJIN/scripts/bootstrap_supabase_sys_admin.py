#!/usr/bin/env python3
"""Bootstrap the required named SYS_ADMIN user on the Supabase Postgres DB.

The script is intentionally conservative: dry-run is the default, secrets are
never printed, and the one-time initial password is written only to a local
gitignored file with owner-only permissions.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.auth.password import (  # noqa: E402
    generate_initial_password,
    hash_password,
    validate_password_strength,
)
from core.db import create_sqlalchemy_engine  # noqa: E402
from scripts.supabase_cutover import (  # noqa: E402
    DEFAULT_ENV_FILES,
    EnvIssue,
    load_env_files,
    unique_paths,
    validate_environment,
)
from scripts.verify_supabase_remote import DEFAULT_PROJECT_REF  # noqa: E402

DEFAULT_PASSWORD_FILE = ROOT / "secrets" / "supabase-sys-admin-initial-password.txt"


@dataclass(frozen=True)
class RoleSeed:
    """Application role seed row.

    Args:
        role_name: Stable role name used by AJIN RBAC.
        role_level: Numeric privilege level used by existing auth logic.
        description: Human-readable role purpose.
    """

    role_name: str
    role_level: int
    description: str


@dataclass(frozen=True)
class SysAdminSpec:
    """Named system administrator bootstrap account.

    Args:
        employee_id: Stable employee id for the bootstrap administrator.
        username: Display name for operators.
        department: Owning department.
        position: Position title.
        role_name: RBAC role to assign.
        data_class: Data lineage class.
        source_system: Data lineage source system.
        source_label: Data lineage source label.
    """

    employee_id: str = "SYS-0001"
    username: str = "AJIN 운영관리자"
    department: str = "IT전략팀"
    position: str = "시스템 관리자"
    role_name: str = "SYS_ADMIN"
    data_class: str = "system"
    source_system: str = "supabase_cutover"
    source_label: str = "Named SYS_ADMIN bootstrap"


@dataclass(frozen=True)
class AdminPosture:
    """Sanitized admin posture snapshot.

    Args:
        active_sys_admin_count: Number of active users with SYS_ADMIN role.
        named_sys_admin_count: Active SYS_ADMIN users not using employee_id admin.
        active_default_admin_count: Active users using the legacy admin employee id.
        target_exists: Whether the target employee id already exists.
        target_is_active_sys_admin: Whether the target is already a valid admin.
    """

    active_sys_admin_count: int
    named_sys_admin_count: int
    active_default_admin_count: int
    target_exists: bool
    target_is_active_sys_admin: bool


DEFAULT_ROLES: tuple[RoleSeed, ...] = (
    RoleSeed("INACTIVE", 0, "Inactive or disabled account"),
    RoleSeed("EMPLOYEE", 1, "Standard employee access"),
    RoleSeed("MANAGER", 2, "Department manager access"),
    RoleSeed("TEAM_LEAD", 3, "Team lead access"),
    RoleSeed("HR_ADMIN", 4, "HR administrator access"),
    RoleSeed("SYS_ADMIN", 5, "System administrator access"),
)
DEFAULT_SYS_ADMIN = SysAdminSpec()


def _json_safe(value: Any) -> Any:
    """Convert dataclasses and paths into JSON-serializable values.

    Args:
        value: Arbitrary value returned by the bootstrap workflow.

    Returns:
        Any: JSON-compatible value.
    """

    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def validate_bootstrap_environment(project_ref: str) -> list[EnvIssue]:
    """Validate environment values before connecting to Supabase.

    Args:
        project_ref: Expected Supabase project reference.

    Returns:
        list[EnvIssue]: Validation issues without secret values.
    """

    issues = validate_environment(project_ref)
    issue_names = {issue.name for issue in issues}
    if os.getenv("APP_DB_BACKEND", "").strip().lower() != "postgres":
        if "APP_DB_BACKEND" not in issue_names:
            issues.append(EnvIssue("APP_DB_BACKEND", "APP_DB_BACKEND must be postgres"))
    if not os.getenv("DATABASE_URL", "").strip():
        if "DATABASE_URL" not in issue_names:
            issues.append(EnvIssue("DATABASE_URL", "DATABASE_URL is required"))
    return issues


def _named_in_clause(prefix: str, values: Iterable[str]) -> tuple[str, dict[str, str]]:
    """Build a named-parameter SQL IN clause.

    Args:
        prefix: Parameter name prefix.
        values: Values to bind.

    Returns:
        tuple[str, dict[str, str]]: SQL fragment and parameter mapping.
    """

    params = {f"{prefix}_{index}": value for index, value in enumerate(values)}
    return ", ".join(f":{key}" for key in params), params


def fetch_admin_posture(connection: Connection, spec: SysAdminSpec) -> AdminPosture:
    """Fetch the current admin posture from roles/users.

    Args:
        connection: Active SQLAlchemy connection.
        spec: Target SYS_ADMIN account spec.

    Returns:
        AdminPosture: Sanitized posture counters.
    """

    rows = (
        connection.execute(
            sa.text(
                """
                select u.employee_id,
                       u.is_active,
                       r.role_name
                  from public.users u
                  join public.roles r on r.role_id = u.role_id
                 where r.role_name = 'SYS_ADMIN'
                    or lower(u.employee_id) = 'admin'
                    or u.employee_id = :target_employee_id
                 order by u.employee_id
                """
            ),
            {"target_employee_id": spec.employee_id},
        )
        .mappings()
        .all()
    )
    active_sys_admins = [
        row
        for row in rows
        if row.get("role_name") == "SYS_ADMIN" and bool(row.get("is_active"))
    ]
    named_sys_admins = [
        row
        for row in active_sys_admins
        if str(row.get("employee_id") or "").lower() != "admin"
    ]
    active_default_admins = [
        row
        for row in rows
        if str(row.get("employee_id") or "").lower() == "admin"
        and bool(row.get("is_active"))
    ]
    target_rows = [row for row in rows if row.get("employee_id") == spec.employee_id]
    target_is_active_sys_admin = any(
        row.get("role_name") == "SYS_ADMIN" and bool(row.get("is_active"))
        for row in target_rows
    )
    return AdminPosture(
        active_sys_admin_count=len(active_sys_admins),
        named_sys_admin_count=len(named_sys_admins),
        active_default_admin_count=len(active_default_admins),
        target_exists=bool(target_rows),
        target_is_active_sys_admin=target_is_active_sys_admin,
    )


def fetch_existing_roles(connection: Connection, roles: Iterable[RoleSeed]) -> set[str]:
    """Return the role names already present in the database.

    Args:
        connection: Active SQLAlchemy connection.
        roles: Expected role seed rows.

    Returns:
        set[str]: Existing role names.
    """

    role_names = [role.role_name for role in roles]
    clause, params = _named_in_clause("role", role_names)
    rows = (
        connection.execute(
            sa.text(f"select role_name from public.roles where role_name in ({clause})"),
            params,
        )
        .mappings()
        .all()
    )
    return {str(row["role_name"]) for row in rows}


def upsert_roles(connection: Connection, roles: Iterable[RoleSeed]) -> None:
    """Idempotently seed the AJIN RBAC roles.

    Args:
        connection: Active SQLAlchemy connection.
        roles: Role seed rows to create or update.
    """

    for role in roles:
        connection.execute(
            sa.text(
                """
                insert into public.roles (role_name, role_level, description)
                values (:role_name, :role_level, :description)
                on conflict (role_name) do update
                    set role_level = excluded.role_level,
                        description = excluded.description
                """
            ),
            asdict(role),
        )


def assert_password_file_ready(path: Path, *, overwrite: bool) -> None:
    """Ensure the one-time password file can be safely written.

    Args:
        path: Password output path.
        overwrite: Whether an existing file may be replaced.

    Raises:
        FileExistsError: If the file already exists and overwrite is false.
        OSError: If the parent directory cannot be created.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"{path} already exists; move it or pass --overwrite-password-file"
        )


def write_initial_password(path: Path, password: str, *, overwrite: bool) -> None:
    """Write the one-time initial password with owner-only permissions.

    Args:
        path: Local gitignored output path.
        password: Plain initial password to write once.
        overwrite: Whether an existing file may be replaced.

    Raises:
        FileExistsError: If the file already exists and overwrite is false.
        OSError: If the file cannot be written or chmodded.
    """

    assert_password_file_ready(path, overwrite=overwrite)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if not overwrite:
        flags |= os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(password)
            handle.write("\n")
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def insert_sys_admin(
    connection: Connection,
    *,
    spec: SysAdminSpec,
    password_hash: str,
) -> None:
    """Insert the named SYS_ADMIN user.

    Args:
        connection: Active SQLAlchemy connection.
        spec: Target SYS_ADMIN account spec.
        password_hash: Bcrypt hash of the generated initial password.

    Raises:
        RuntimeError: If the SYS_ADMIN role is missing.
    """

    role_row = (
        connection.execute(
            sa.text("select role_id from public.roles where role_name = :role_name"),
            {"role_name": spec.role_name},
        )
        .mappings()
        .first()
    )
    if not role_row:
        raise RuntimeError("SYS_ADMIN role is missing after role seed")
    connection.execute(
        sa.text(
            """
            insert into public.users (
                employee_id,
                username,
                department,
                position,
                password_hash,
                role_id,
                is_active,
                must_change_pw,
                data_class,
                source_system,
                source_label,
                source_updated_at
            ) values (
                :employee_id,
                :username,
                :department,
                :position,
                :password_hash,
                :role_id,
                true,
                true,
                :data_class,
                :source_system,
                :source_label,
                current_timestamp
            )
            """
        ),
        {
            "employee_id": spec.employee_id,
            "username": spec.username,
            "department": spec.department,
            "position": spec.position,
            "password_hash": password_hash,
            "role_id": role_row["role_id"],
            "data_class": spec.data_class,
            "source_system": spec.source_system,
            "source_label": spec.source_label,
        },
    )


def bootstrap_sys_admin(
    engine: Engine,
    *,
    spec: SysAdminSpec = DEFAULT_SYS_ADMIN,
    roles: tuple[RoleSeed, ...] = DEFAULT_ROLES,
    apply: bool = False,
    password_file: Path = DEFAULT_PASSWORD_FILE,
    overwrite_password_file: bool = False,
) -> dict[str, Any]:
    """Bootstrap roles and the named SYS_ADMIN user.

    Args:
        engine: SQLAlchemy engine connected to the target database.
        spec: Target SYS_ADMIN account spec.
        roles: Role seed rows.
        apply: Whether to mutate the database.
        password_file: Local output path for the one-time password.
        overwrite_password_file: Whether an existing password file may be replaced.

    Returns:
        dict[str, Any]: Secret-safe workflow summary.

    Raises:
        RuntimeError: If legacy admin posture or target-account conflict blocks release.
        FileExistsError: If creation needs a password file but it already exists.
    """

    role_names = {role.role_name for role in roles}
    if not apply:
        with engine.connect() as connection:
            roles_before = fetch_existing_roles(connection, roles)
            posture_before = fetch_admin_posture(connection, spec)
            missing_roles = sorted(role_names - roles_before)
            if posture_before.active_default_admin_count:
                raise RuntimeError("active default admin account must be disabled first")
            if posture_before.target_exists and not posture_before.target_is_active_sys_admin:
                raise RuntimeError(
                    "target employee_id exists but is not an active SYS_ADMIN"
                )
            return {
                "mode": "dry_run",
                "roles_missing": missing_roles,
                "roles_would_upsert": [role.role_name for role in roles],
                "sys_admin_action": "already_satisfied"
                if posture_before.named_sys_admin_count
                else "would_create",
                "admin_spec": spec,
                "password_file": password_file,
                "password_file_written": False,
                "posture_before": posture_before,
                "posture_after": posture_before,
            }

    with engine.connect() as connection:
        transaction = connection.begin()
        password: str | None = None
        password_file_created = False
        sys_admin_action = "unknown"
        password_file_written = False
        try:
            roles_before = fetch_existing_roles(connection, roles)
            posture_before = fetch_admin_posture(connection, spec)
            missing_roles = sorted(role_names - roles_before)

            if posture_before.active_default_admin_count:
                raise RuntimeError("active default admin account must be disabled first")
            if posture_before.target_exists and not posture_before.target_is_active_sys_admin:
                raise RuntimeError(
                    "target employee_id exists but is not an active SYS_ADMIN"
                )
            if not posture_before.named_sys_admin_count:
                assert_password_file_ready(
                    password_file,
                    overwrite=overwrite_password_file,
                )

            upsert_roles(connection, roles)
            if posture_before.named_sys_admin_count:
                sys_admin_action = "already_satisfied"
            else:
                password = generate_initial_password(spec.employee_id)
                ok, reason = validate_password_strength(
                    password,
                    employee_id=spec.employee_id,
                    username=spec.username,
                    extra_context=("AJIN", "SYS_ADMIN"),
                )
                if not ok:
                    raise RuntimeError(f"generated password failed policy: {reason}")
                insert_sys_admin(
                    connection,
                    spec=spec,
                    password_hash=hash_password(password),
                )
                write_initial_password(
                    password_file,
                    password,
                    overwrite=overwrite_password_file,
                )
                password_file_created = True
                sys_admin_action = "created"
                password_file_written = True
            posture_after = fetch_admin_posture(connection, spec)
            transaction.commit()
        except Exception:
            transaction.rollback()
            if password_file_created:
                password_file.unlink(missing_ok=True)
            raise

    return {
        "mode": "apply",
        "roles_missing": missing_roles,
        "roles_would_upsert": [role.role_name for role in roles],
        "sys_admin_action": sys_admin_action,
        "admin_spec": spec,
        "password_file": password_file,
        "password_file_written": password_file_written,
        "posture_before": posture_before,
        "posture_after": posture_after,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        action="append",
        type=Path,
        default=[],
        help="dotenv file to load before connecting; may be passed multiple times",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="create/update roles and create the named SYS_ADMIN user",
    )
    parser.add_argument(
        "--project-ref",
        default=DEFAULT_PROJECT_REF,
        help="expected Supabase project ref",
    )
    parser.add_argument(
        "--password-file",
        type=Path,
        default=DEFAULT_PASSWORD_FILE,
        help="local path for the one-time initial password",
    )
    parser.add_argument(
        "--overwrite-password-file",
        action="store_true",
        help="replace an existing one-time password file when creating a new admin",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the SYS_ADMIN bootstrap CLI.

    Args:
        argv: Optional command-line arguments.

    Returns:
        int: Process exit status.
    """

    args = build_arg_parser().parse_args(argv)
    env_paths = unique_paths([*DEFAULT_ENV_FILES, *args.env_file])
    loaded_env_files = load_env_files(env_paths, override=False)
    issues = validate_bootstrap_environment(args.project_ref)
    if issues:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "apply" if args.apply else "dry_run",
                    "loaded_env_files": loaded_env_files,
                    "issues": [asdict(issue) for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    try:
        result = bootstrap_sys_admin(
            create_sqlalchemy_engine(),
            apply=args.apply,
            password_file=args.password_file,
            overwrite_password_file=args.overwrite_password_file,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": "apply" if args.apply else "dry_run",
                    "loaded_env_files": loaded_env_files,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    output = {
        "ok": True,
        "loaded_env_files": loaded_env_files,
        **result,
    }
    print(json.dumps(_json_safe(output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
