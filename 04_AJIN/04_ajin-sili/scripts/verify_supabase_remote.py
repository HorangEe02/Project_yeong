#!/usr/bin/env python3
"""Verify that the AJIN backend can operate against the Supabase remote project.

The verifier is intentionally read-only. It checks environment contracts,
Postgres schema state, public-role grants, and Storage bucket visibility without
printing secret values.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

DEFAULT_PROJECT_REF = "ycjuzwltwbeudanjykag"
EXPECTED_ALEMBIC_HEAD = "20260518_0002"
DEFAULT_ATTACHMENT_BUCKET = "ajin-attachments"
DEFAULT_DRAFT_EXPORT_BUCKET = "ajin-draft-exports"
REQUIRED_TABLES = (
    "users",
    "attachments",
    "live_alarms",
    "feedback_events",
    "audit_logs",
)
SENSITIVE_TABLES = (
    "users",
    "attachments",
    "audit_logs",
    "login_history",
    "employees",
    "draft_versions",
    "chat_messages",
    "live_alarms",
    "feedback_events",
)
DENY_POLICY_TABLES = (
    "roles",
    "users",
    "login_history",
    "audit_logs",
    "employees",
    "employee_search_history",
    "regulation_changes",
    "crawl_history",
    "notification_outbox",
    "notification_logs",
    "live_alarms",
    "feedback_events",
    "draft_versions",
    "chat_messages",
    "attachments",
    "plc_violations",
)
TRUTHY_VALUES = {"1", "true", "yes", "on"}
FALSEY_VALUES = {"", "0", "false", "no", "off"}


@dataclass(frozen=True)
class CheckResult:
    """Single verification result.

    Args:
        name: Stable machine-readable check name.
        status: One of pass, warn, fail, or skip.
        summary: Human-readable result summary without secrets.
        details: Optional sanitized metadata for operators.
    """

    name: str
    status: str
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation.

        Returns:
            dict[str, Any]: Check fields suitable for console, JSON, or Markdown output.
        """

        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class VerificationConfig:
    """Verifier runtime configuration.

    Args:
        project_ref: Supabase project ref expected by this environment.
        strict: Whether release-grade checks should fail on transition blockers.
        expected_alembic_head: Alembic revision expected on the target DB.
        db_connect_timeout_seconds: Postgres connection timeout for read-only probes.
        required_tables: Public schema tables required by the AJIN backend.
        sensitive_tables: Tables that must not be granted to the anon role.
        deny_policy_tables: Tables expected to have explicit anon/authenticated deny policies.
        attachment_bucket: Supabase Storage bucket for uploaded attachments.
        draft_export_bucket: Supabase Storage bucket for draft exports.
    """

    project_ref: str = DEFAULT_PROJECT_REF
    strict: bool = False
    expected_alembic_head: str = EXPECTED_ALEMBIC_HEAD
    db_connect_timeout_seconds: int = 5
    required_tables: tuple[str, ...] = REQUIRED_TABLES
    sensitive_tables: tuple[str, ...] = SENSITIVE_TABLES
    deny_policy_tables: tuple[str, ...] = DENY_POLICY_TABLES
    attachment_bucket: str = DEFAULT_ATTACHMENT_BUCKET
    draft_export_bucket: str = DEFAULT_DRAFT_EXPORT_BUCKET

    @property
    def expected_url(self) -> str:
        """Return the hosted Supabase API URL for the configured project.

        Returns:
            str: Expected Supabase project URL.
        """

        return f"https://{self.project_ref}.supabase.co"


DatabaseSnapshot = Mapping[str, Any]
DatabaseQueryRunner = Callable[[str, VerificationConfig], DatabaseSnapshot]
StorageBucketLister = Callable[[VerificationConfig], Iterable[Any]]
ProjectListRunner = Callable[[VerificationConfig], tuple[int, str, str]]
_SUPABASE_HEALTH_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_SUPABASE_HEALTH_CACHE_TTL_SECONDS = 30.0


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable using deployment-friendly values.

    Args:
        name: Environment variable name.
        default: Value to return when the variable is absent or unrecognized.

    Returns:
        bool: Parsed boolean value.
    """

    raw = os.getenv(name)
    if raw is None:
        return default
    lowered = raw.strip().lower()
    if lowered in TRUTHY_VALUES:
        return True
    if lowered in FALSEY_VALUES:
        return False
    return default


def sanitize_url(raw_url: str | None) -> str | None:
    """Remove username and password from a URL-like value.

    Args:
        raw_url: Potential URL value.

    Returns:
        str | None: URL without credentials, or the original non-URL string.
    """

    if not raw_url:
        return raw_url
    try:
        parts = urlsplit(raw_url)
    except ValueError:
        return "<invalid-url>"
    if not parts.scheme or not parts.netloc:
        return raw_url

    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    safe_netloc = f"{hostname}{port}"
    return urlunsplit((parts.scheme, safe_netloc, parts.path, parts.query, parts.fragment))


def normalize_database_url(raw_url: str) -> str:
    """Normalize a Postgres URL for SQLAlchemy's psycopg driver.

    Args:
        raw_url: DATABASE_URL value supplied by the runtime environment.

    Returns:
        str: SQLAlchemy-compatible URL.
    """

    if raw_url.startswith("postgresql+"):
        return raw_url
    if raw_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw_url[len("postgresql://") :]
    if raw_url.startswith("postgres://"):
        return "postgresql+psycopg://" + raw_url[len("postgres://") :]
    return raw_url


def key_state(raw_key: str | None) -> str:
    """Classify a Supabase key without exposing the key itself.

    Args:
        raw_key: Key value from the environment.

    Returns:
        str: Safe key classification.
    """

    if not raw_key:
        return "missing"
    if raw_key.startswith("sb_secret_"):
        return "secret"
    if raw_key.startswith("sb_publishable_"):
        return "publishable"
    if raw_key.count(".") == 2:
        return "legacy_jwt"
    return "present_unknown_prefix"


def _secret_fragments() -> list[str]:
    """Collect local secret fragments that must not appear in generated reports.

    Returns:
        list[str]: Secret-like values from the current process environment.
    """

    names = (
        "SUPABASE_ACCESS_TOKEN",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_DB_PASSWORD",
        "DATABASE_URL",
    )
    fragments = [os.getenv(name, "") for name in names]
    db_url = os.getenv("DATABASE_URL", "")
    try:
        password = urlsplit(db_url).password
        if password:
            fragments.append(password)
    except ValueError:
        pass
    token, _source = read_supabase_access_token()
    if token:
        fragments.append(token)
    return [value for value in fragments if len(value) >= 4]


def redact_value(value: Any) -> Any:
    """Recursively redact secret values from a report object.

    Args:
        value: Arbitrary JSON-like value.

    Returns:
        Any: Redacted JSON-like value.
    """

    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if not isinstance(value, str):
        return value

    redacted = sanitize_url(value) if "://" in value and "@" in value else value
    for fragment in _secret_fragments():
        redacted = redacted.replace(fragment, "<redacted>")
    return redacted


def result(name: str, status: str, summary: str, **details: Any) -> CheckResult:
    """Build a sanitized CheckResult.

    Args:
        name: Stable check name.
        status: One of pass, warn, fail, or skip.
        summary: Human-readable summary.
        **details: Additional detail values.

    Returns:
        CheckResult: Sanitized check result.
    """

    return CheckResult(name=name, status=status, summary=summary, details=redact_value(details))


def read_supabase_access_token() -> tuple[str | None, str]:
    """Read the Supabase CLI personal access token without exposing it.

    Returns:
        tuple[str | None, str]: Token value and safe source label.
    """

    env_token = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip()
    if env_token:
        return env_token, "env:SUPABASE_ACCESS_TOKEN"

    token_path = Path.home() / ".supabase" / "access-token"
    try:
        if token_path.exists():
            return token_path.read_text(encoding="utf-8").strip(), "~/.supabase/access-token"
    except OSError:
        return None, "~/.supabase/access-token"
    return None, "missing"


def is_valid_supabase_access_token_shape(token: str | None) -> bool:
    """Check the current Supabase personal access token prefix shape.

    Args:
        token: Token read from env or Supabase CLI credential store.

    Returns:
        bool: True when the token has the expected personal access token prefix.
    """

    return bool(token and re.fullmatch(r"sbp_[A-Za-z0-9]{40,}", token))


def _contains_project_ref(value: Any, project_ref: str) -> bool:
    """Recursively find a project ref in Supabase CLI JSON output.

    Args:
        value: Parsed JSON value.
        project_ref: Target Supabase project ref.

    Returns:
        bool: Whether the project ref appears as a string value.
    """

    if isinstance(value, str):
        return value == project_ref
    if isinstance(value, dict):
        return any(_contains_project_ref(item, project_ref) for item in value.values())
    if isinstance(value, list):
        return any(_contains_project_ref(item, project_ref) for item in value)
    return False


def run_supabase_projects_list(config: VerificationConfig) -> tuple[int, str, str]:
    """Run `supabase projects list -o json`.

    Args:
        config: Verification configuration.

    Returns:
        tuple[int, str, str]: Return code, stdout, and stderr.
    """

    del config
    completed = subprocess.run(
        ["supabase", "projects", "list", "-o", "json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=int(os.getenv("SUPABASE_CLI_TIMEOUT_SECONDS", "30")),
    )
    return completed.returncode, completed.stdout, completed.stderr


def read_linked_project_ref() -> tuple[str | None, str]:
    """Read the local Supabase CLI linked project ref.

    Returns:
        tuple[str | None, str]: Linked project ref and safe source label.
    """

    candidates = (
        Path("supabase/.temp/project-ref"),
        Path("supabase/.temp/project_ref"),
    )
    for path in candidates:
        try:
            if path.exists():
                return path.read_text(encoding="utf-8").strip(), str(path)
        except OSError:
            return None, str(path)
    return None, "supabase/.temp/project-ref"


def check_supabase_cli(
    config: VerificationConfig,
    project_list_runner: ProjectListRunner | None = None,
) -> list[CheckResult]:
    """Validate Supabase CLI authentication and local project link state.

    Args:
        config: Verification configuration.
        project_list_runner: Optional test seam for `supabase projects list`.

    Returns:
        list[CheckResult]: CLI and project-link check results.
    """

    checks: list[CheckResult] = []
    supabase_bin = shutil.which("supabase")
    if not supabase_bin:
        return [
            result("supabase_cli_available", "fail", "Supabase CLI is not installed or not on PATH."),
            result("supabase_access_token_shape", "skip", "Skipped because Supabase CLI is missing."),
            result("supabase_project_list", "skip", "Skipped because Supabase CLI is missing."),
            result("supabase_linked_project_ref", "skip", "Skipped because Supabase CLI is missing."),
        ]

    try:
        version = subprocess.run(
            ["supabase", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("SUPABASE_CLI_TIMEOUT_SECONDS", "30")),
        )
        version_text = (version.stdout or version.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        return [
            result(
                "supabase_cli_available",
                "fail",
                "Supabase CLI exists but cannot be executed.",
                error_type=type(exc).__name__,
            ),
            result("supabase_access_token_shape", "skip", "Skipped because CLI execution failed."),
            result("supabase_project_list", "skip", "Skipped because CLI execution failed."),
            result("supabase_linked_project_ref", "skip", "Skipped because CLI execution failed."),
        ]
    checks.append(
        result(
            "supabase_cli_available",
            "pass" if version.returncode == 0 else "fail",
            "Supabase CLI is executable." if version.returncode == 0 else "Supabase CLI failed.",
            version=version_text,
        )
    )

    token, token_source = read_supabase_access_token()
    token_is_valid = is_valid_supabase_access_token_shape(token)
    checks.append(
        result(
            "supabase_access_token_shape",
            "pass" if token_is_valid else "fail",
            "Supabase access token shape is valid."
            if token_is_valid
            else "Supabase access token is missing or not an sbp_ personal access token.",
            source=token_source,
        )
    )

    if not token_is_valid:
        checks.append(
            result(
                "supabase_project_list",
                "skip",
                "Skipped because Supabase access token shape is invalid.",
            )
        )
    else:
        try:
            returncode, stdout, stderr = (
                project_list_runner(config)
                if project_list_runner is not None
                else run_supabase_projects_list(config)
            )
            if returncode != 0:
                checks.append(
                    result(
                        "supabase_project_list",
                        "fail",
                        "Supabase CLI project list failed.",
                        error=(stderr or stdout).strip(),
                    )
                )
            else:
                try:
                    payload = json.loads(stdout or "[]")
                    found = _contains_project_ref(payload, config.project_ref)
                except json.JSONDecodeError:
                    payload = None
                    found = config.project_ref in stdout
                checks.append(
                    result(
                        "supabase_project_list",
                        "pass" if found else "fail",
                        "Target Supabase project is visible to the CLI token."
                        if found
                        else "Target Supabase project was not found in CLI project list.",
                        project_ref=config.project_ref,
                        output_format="json" if payload is not None else "text",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                result(
                    "supabase_project_list",
                    "fail",
                    "Supabase CLI project list raised an exception.",
                    error_type=type(exc).__name__,
                )
            )

    linked_ref, linked_source = read_linked_project_ref()
    if not linked_ref:
        checks.append(
            result(
                "supabase_linked_project_ref",
                "fail",
                "Supabase project is not linked locally.",
                expected=config.project_ref,
                source=linked_source,
            )
        )
    elif linked_ref == config.project_ref:
        checks.append(
            result(
                "supabase_linked_project_ref",
                "pass",
                "Local Supabase link matches project ref.",
                source=linked_source,
            )
        )
    else:
        checks.append(
            result(
                "supabase_linked_project_ref",
                "fail",
                "Local Supabase link points to a different project.",
                expected=config.project_ref,
                configured=linked_ref,
                source=linked_source,
            )
        )

    return checks


def check_environment(config: VerificationConfig) -> list[CheckResult]:
    """Validate Supabase and fallback environment contracts.

    Args:
        config: Verification configuration.

    Returns:
        list[CheckResult]: Environment check results.
    """

    checks: list[CheckResult] = []
    env_project_ref = os.getenv("SUPABASE_PROJECT_REF", "").strip()
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    app_db_backend = os.getenv("APP_DB_BACKEND", "sqlite").strip().lower()
    database_url = os.getenv("DATABASE_URL", "").strip()
    secret_key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    firebase_write_enabled = env_bool("FIREBASE_WRITE_ENABLED", default=False)
    firebase_read_fallback_enabled = env_bool("FIREBASE_READ_FALLBACK_ENABLED", default=False)

    if not env_project_ref:
        checks.append(
            result(
                "project_ref_configured",
                "fail" if config.strict else "warn",
                "SUPABASE_PROJECT_REF is required in strict mode."
                if config.strict
                else "SUPABASE_PROJECT_REF is not set; verifier project-ref argument is used.",
                expected=config.project_ref,
            )
        )
    elif env_project_ref == config.project_ref:
        checks.append(result("project_ref_configured", "pass", "SUPABASE_PROJECT_REF matches."))
    else:
        checks.append(
            result(
                "project_ref_configured",
                "fail",
                "SUPABASE_PROJECT_REF does not match the verifier project ref.",
                expected=config.project_ref,
                configured=env_project_ref,
            )
        )

    if not supabase_url:
        checks.append(
            result(
                "url_matches_project_ref",
                "fail",
                "SUPABASE_URL is missing.",
                expected=config.expected_url,
            )
        )
    elif supabase_url == config.expected_url:
        checks.append(result("url_matches_project_ref", "pass", "SUPABASE_URL matches project ref."))
    else:
        checks.append(
            result(
                "url_matches_project_ref",
                "fail",
                "SUPABASE_URL does not match the expected project URL.",
                expected=config.expected_url,
                configured=sanitize_url(supabase_url),
            )
        )

    if app_db_backend == "postgres":
        checks.append(result("db_backend", "pass", "APP_DB_BACKEND is postgres."))
    else:
        checks.append(
            result(
                "db_backend",
                "fail",
                "APP_DB_BACKEND must be postgres for Supabase operation.",
                configured=app_db_backend or "<empty>",
            )
        )

    if database_url:
        checks.append(
            result(
                "database_url_configured",
                "pass",
                "DATABASE_URL is configured.",
                database_url=sanitize_url(database_url),
            )
        )
    else:
        checks.append(result("database_url_configured", "fail", "DATABASE_URL is missing."))

    secret_status = key_state(secret_key)
    if secret_status in {"secret", "legacy_jwt"}:
        checks.append(
            result(
                "secret_key_configured",
                "pass",
                "SUPABASE_SECRET_KEY is configured for backend-only access.",
                key_type=secret_status,
            )
        )
    else:
        checks.append(
            result(
                "secret_key_configured",
                "fail",
                "SUPABASE_SECRET_KEY is missing or not an elevated backend key.",
                key_type=secret_status,
            )
        )

    publishable_status = key_state(publishable_key)
    checks.append(
        result(
            "publishable_key_configured",
            "pass" if publishable_status != "missing" else "warn",
            "SUPABASE_PUBLISHABLE_KEY presence checked.",
            key_type=publishable_status,
        )
    )

    if firebase_write_enabled:
        checks.append(
            result(
                "firebase_write_disabled",
                "fail",
                "FIREBASE_WRITE_ENABLED must be false before Supabase production operation.",
            )
        )
    else:
        checks.append(result("firebase_write_disabled", "pass", "Firebase writes are disabled."))

    if firebase_read_fallback_enabled:
        checks.append(
            result(
                "firebase_read_fallback_disabled",
                "fail" if config.strict else "warn",
                "FIREBASE_READ_FALLBACK_ENABLED should be false after verification/canary.",
            )
        )
    else:
        checks.append(
            result("firebase_read_fallback_disabled", "pass", "Firebase read fallback is disabled.")
        )

    return checks


def _named_in_clause(prefix: str, values: Iterable[str]) -> tuple[str, dict[str, str]]:
    """Build a safe SQLAlchemy named-parameter IN clause.

    Args:
        prefix: Parameter name prefix.
        values: Values to bind.

    Returns:
        tuple[str, dict[str, str]]: SQL placeholder clause and bind params.
    """

    params = {f"{prefix}_{index}": value for index, value in enumerate(values)}
    clause = ", ".join(f":{name}" for name in params)
    return clause or "NULL", params


def query_database_snapshot(database_url: str, config: VerificationConfig) -> DatabaseSnapshot:
    """Collect read-only DB metadata from a Postgres DATABASE_URL.

    Args:
        database_url: SQLAlchemy-compatible Postgres URL.
        config: Verification configuration.

    Returns:
        DatabaseSnapshot: Connection, Alembic, table, RLS, and grant metadata.

    Raises:
        Exception: Propagates SQLAlchemy/driver errors so callers can fail closed.
    """

    from sqlalchemy import create_engine, text

    connect_timeout = int(
        os.getenv("SUPABASE_VERIFY_CONNECT_TIMEOUT", str(config.db_connect_timeout_seconds))
    )
    engine = create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": connect_timeout},
    )
    with engine.connect() as connection:
        connection.execute(text("select 1")).scalar_one()

        alembic_versions: list[str] = []
        try:
            alembic_versions = list(
                connection.execute(text("select version_num from alembic_version")).scalars().all()
            )
        except Exception:
            alembic_versions = []

        app_tables = tuple(
            dict.fromkeys(
                (
                    *config.required_tables,
                    *config.sensitive_tables,
                    *config.deny_policy_tables,
                )
            )
        )
        app_clause, app_params = _named_in_clause("app_table", app_tables)
        table_rows = (
            connection.execute(
                text(
                    f"""
                    select c.relname as table_name, c.relrowsecurity as rls_enabled
                    from pg_class c
                    join pg_namespace n on n.oid = c.relnamespace
                    where n.nspname = 'public'
                      and c.relkind in ('r', 'p')
                      and c.relname in ({app_clause})
                    """
                ),
                app_params,
            )
            .mappings()
            .all()
        )
        observed_tables = {str(row["table_name"]) for row in table_rows}

        sensitive_clause, sensitive_params = _named_in_clause(
            "sensitive_table", config.sensitive_tables
        )
        grant_rows = (
            connection.execute(
                text(
                    f"""
                    select grantee, table_name, privilege_type
                    from information_schema.role_table_grants
                    where table_schema = 'public'
                      and grantee in ('anon', 'authenticated', 'service_role')
                      and table_name in ({sensitive_clause})
                    order by grantee, table_name, privilege_type
                    """
                ),
                sensitive_params,
            )
            .mappings()
            .all()
        )

        deny_clause, deny_params = _named_in_clause("deny_table", config.deny_policy_tables)
        policy_rows = (
            connection.execute(
                text(
                    f"""
                    select tablename as table_name,
                           policyname as policy_name,
                           roles,
                           cmd,
                           qual,
                           with_check
                    from pg_policies
                    where schemaname = 'public'
                      and tablename in ({deny_clause})
                    order by tablename, policyname
                    """
                ),
                deny_params,
            )
            .mappings()
            .all()
        )

        admin_rows = []
        if {"users", "roles"}.issubset(observed_tables):
            admin_rows = (
                connection.execute(
                    text(
                        """
                        select u.employee_id,
                               u.password_hash,
                               u.is_active,
                               r.role_name
                        from public.users u
                        join public.roles r on r.role_id = u.role_id
                        where r.role_name = 'SYS_ADMIN'
                           or u.employee_id = 'admin'
                        order by u.employee_id
                        """
                    )
                )
                .mappings()
                .all()
            )

    table_map = {str(row["table_name"]): True for row in table_rows}
    rls_map = {str(row["table_name"]): bool(row["rls_enabled"]) for row in table_rows}
    privileges = [dict(row) for row in grant_rows]
    policies = [dict(row) for row in policy_rows]
    admin_users = [
        {
            "employee_id": row.get("employee_id"),
            "password_hash": row.get("password_hash"),
            "is_active": bool(row.get("is_active")),
            "role_name": row.get("role_name"),
        }
        for row in admin_rows
    ]
    return {
        "connected": True,
        "alembic_versions": alembic_versions,
        "tables": table_map,
        "rls_enabled": rls_map,
        "privileges": privileges,
        "policies": policies,
        "admin_users": admin_users,
    }


def _normalize_policy_roles(raw_roles: Any) -> set[str]:
    """Normalize pg_policies.roles into a string set.

    Args:
        raw_roles: Role list returned by the database driver.

    Returns:
        set[str]: Role names assigned to a policy.
    """

    if raw_roles is None:
        return set()
    if isinstance(raw_roles, str):
        return {role.strip().strip('"') for role in raw_roles.strip("{}").split(",") if role.strip()}
    return {str(role).strip().strip('"') for role in raw_roles if str(role).strip()}


def _is_false_expression(expression: Any) -> bool:
    """Return whether a policy expression is an explicit false predicate.

    Args:
        expression: Raw pg_policies.qual or with_check value.

    Returns:
        bool: True when the expression is equivalent to `false`.
    """

    compact = re.sub(r"\s+", "", str(expression or "")).lower()
    return compact in {"false", "(false)"}


def _has_deny_all_policy(table: str, policies: Iterable[Mapping[str, Any]]) -> bool:
    """Check whether a table has the expected deny-all Data API policy.

    Args:
        table: Public table name.
        policies: Policy rows from pg_policies.

    Returns:
        bool: True when the table has the expected restrictive deny-all policy.
    """

    expected_name = f"deny_all_data_api_{table}"
    for policy in policies:
        if policy.get("table_name") != table or policy.get("policy_name") != expected_name:
            continue
        roles = _normalize_policy_roles(policy.get("roles"))
        if not {"anon", "authenticated"}.issubset(roles):
            continue
        if str(policy.get("cmd", "")).upper() != "ALL":
            continue
        if not _is_false_expression(policy.get("qual")):
            continue
        if not _is_false_expression(policy.get("with_check")):
            continue
        return True
    return False


def _check_default_admin_risk(snapshot: DatabaseSnapshot, config: VerificationConfig) -> CheckResult:
    """Detect legacy default-admin release blockers.

    Args:
        snapshot: Database metadata snapshot.
        config: Verification configuration.

    Returns:
        CheckResult: Pass/fail/skip status for bootstrap admin posture.
    """

    admin_users = [dict(row) for row in snapshot.get("admin_users", ())]
    if not admin_users:
        return result(
            "default_admin_risk",
            "fail" if config.strict else "warn",
            "No active named SYS_ADMIN was observed.",
            active_sys_admin_count=0,
            named_sys_admin_count=0,
            default_admin_active=False,
            default_password_detected=False,
        )

    active_sys_admins = [
        row
        for row in admin_users
        if row.get("role_name") == "SYS_ADMIN" and bool(row.get("is_active"))
    ]
    named_sys_admins = [
        row for row in active_sys_admins if str(row.get("employee_id") or "").lower() != "admin"
    ]
    default_admin_active = any(
        str(row.get("employee_id") or "").lower() == "admin" and bool(row.get("is_active"))
        for row in admin_users
    )

    default_password_detected = False
    try:
        from core.auth.password import verify_password

        for row in admin_users:
            if str(row.get("employee_id") or "").lower() != "admin":
                continue
            password_hash = str(row.get("password_hash") or "")
            if password_hash and verify_password("admin1234", password_hash):
                default_password_detected = True
                break
    except Exception:
        default_password_detected = False

    blockers: list[str] = []
    if not named_sys_admins:
        blockers.append("named_sys_admin_missing")
    if default_admin_active:
        blockers.append("default_admin_active")
    if default_password_detected:
        blockers.append("admin1234_password_detected")

    return result(
        "default_admin_risk",
        "fail" if blockers else "pass",
        "Default admin posture is safe."
        if not blockers
        else "Default admin or missing named SYS_ADMIN risk detected.",
        active_sys_admin_count=len(active_sys_admins),
        named_sys_admin_count=len(named_sys_admins),
        default_admin_active=default_admin_active,
        default_password_detected=default_password_detected,
        blockers=blockers,
    )


def check_database(
    config: VerificationConfig,
    query_runner: DatabaseQueryRunner | None = None,
) -> list[CheckResult]:
    """Check remote Postgres connectivity and schema posture.

    Args:
        config: Verification configuration.
        query_runner: Optional test seam that returns a DatabaseSnapshot.

    Returns:
        list[CheckResult]: Database check results.
    """

    raw_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_url:
        return [
            result("database_connected", "fail", "DATABASE_URL is missing; DB check cannot run."),
            result("alembic_current", "skip", "Skipped because DATABASE_URL is missing."),
            result("required_tables_present", "skip", "Skipped because DATABASE_URL is missing."),
            result("required_tables_rls_enabled", "skip", "Skipped because DATABASE_URL is missing."),
            result("sensitive_role_grants", "skip", "Skipped because DATABASE_URL is missing."),
            result("data_api_deny_policies", "skip", "Skipped because DATABASE_URL is missing."),
            result("default_admin_risk", "skip", "Skipped because DATABASE_URL is missing."),
        ]

    normalized_url = normalize_database_url(raw_url)
    try:
        snapshot = (
            query_runner(normalized_url, config)
            if query_runner is not None
            else query_database_snapshot(normalized_url, config)
        )
    except Exception as exc:  # noqa: BLE001
        return [
            result(
                "database_connected",
                "fail",
                "DATABASE_URL read-only connection failed.",
                error=str(exc),
                database_url=sanitize_url(raw_url),
            ),
            result("alembic_current", "skip", "Skipped because DB connection failed."),
            result("required_tables_present", "skip", "Skipped because DB connection failed."),
            result("required_tables_rls_enabled", "skip", "Skipped because DB connection failed."),
            result("sensitive_role_grants", "skip", "Skipped because DB connection failed."),
            result("data_api_deny_policies", "skip", "Skipped because DB connection failed."),
            result("default_admin_risk", "skip", "Skipped because DB connection failed."),
        ]

    checks = [
        result(
            "database_connected",
            "pass",
            "DATABASE_URL read-only connection succeeded.",
            database_url=sanitize_url(raw_url),
        )
    ]

    versions = tuple(str(value) for value in snapshot.get("alembic_versions", ()))
    if config.expected_alembic_head in versions:
        checks.append(
            result(
                "alembic_current",
                "pass",
                "Alembic revision matches expected head.",
                expected=config.expected_alembic_head,
            )
        )
    elif versions:
        checks.append(
            result(
                "alembic_current",
                "fail",
                "Alembic revision does not match expected head.",
                expected=config.expected_alembic_head,
                observed=list(versions),
            )
        )
    else:
        checks.append(
            result(
                "alembic_current",
                "fail",
                "Alembic revision table is missing or empty.",
                expected=config.expected_alembic_head,
            )
        )

    tables = dict(snapshot.get("tables", {}))
    missing_tables = [table for table in config.required_tables if not tables.get(table)]
    checks.append(
        result(
            "required_tables_present",
            "fail" if missing_tables else "pass",
            "Required public tables are present."
            if not missing_tables
            else "Required public tables are missing.",
            missing=missing_tables,
        )
    )

    rls_enabled = dict(snapshot.get("rls_enabled", {}))
    rls_disabled = [
        table for table in config.required_tables if tables.get(table) and not rls_enabled.get(table)
    ]
    checks.append(
        result(
            "required_tables_rls_enabled",
            "fail" if rls_disabled else "pass",
            "RLS is enabled on required tables."
            if not rls_disabled
            else "RLS is disabled on one or more required tables.",
            disabled=rls_disabled,
        )
    )

    privileges = [dict(row) for row in snapshot.get("privileges", ())]
    role_grants = [
        row
        for row in privileges
        if row.get("grantee") in {"anon", "authenticated", "service_role"}
    ]
    if role_grants:
        checks.append(
            result(
                "sensitive_role_grants",
                "fail",
                "Sensitive public tables grant privileges to Data API roles.",
                grants=role_grants,
            )
        )
    else:
        checks.append(
            result(
                "sensitive_role_grants",
                "pass",
                "No anon/authenticated/service_role grants found on sensitive public tables.",
            )
        )

    policies = [dict(row) for row in snapshot.get("policies", ())]
    existing_deny_tables = [table for table in config.deny_policy_tables if tables.get(table)]
    missing_deny_policies = [
        table for table in existing_deny_tables if not _has_deny_all_policy(table, policies)
    ]
    deny_tables_without_rls = [
        table for table in existing_deny_tables if not rls_enabled.get(table)
    ]
    checks.append(
        result(
            "data_api_deny_policies",
            "fail" if missing_deny_policies or deny_tables_without_rls else "pass",
            "Explicit deny-all Data API policies are present."
            if not missing_deny_policies and not deny_tables_without_rls
            else "Explicit deny-all Data API policies or RLS settings are missing.",
            missing_policy=missing_deny_policies,
            rls_disabled=deny_tables_without_rls,
        )
    )
    checks.append(_check_default_admin_risk(snapshot, config))

    return checks


def _bucket_to_dict(bucket: Any) -> dict[str, Any]:
    """Normalize a Supabase Storage bucket response item.

    Args:
        bucket: Bucket value returned by supabase-py or a test double.

    Returns:
        dict[str, Any]: Normalized bucket fields.
    """

    if isinstance(bucket, dict):
        return dict(bucket)
    if hasattr(bucket, "model_dump"):
        return dict(bucket.model_dump())
    data: dict[str, Any] = {}
    for attr in ("id", "name", "public"):
        if hasattr(bucket, attr):
            data[attr] = getattr(bucket, attr)
    return data


def list_storage_buckets(config: VerificationConfig) -> Iterable[Any]:
    """List Supabase Storage buckets through the backend secret key.

    Args:
        config: Verification configuration.

    Returns:
        Iterable[Any]: Bucket response items from supabase-py.

    Raises:
        Exception: Propagates supabase-py/network/auth errors.
    """

    from supabase import create_client

    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    response = client.storage.list_buckets()
    if isinstance(response, dict) and "data" in response:
        return response["data"] or []
    if hasattr(response, "data"):
        return response.data or []
    return response or []


def check_storage(
    config: VerificationConfig,
    bucket_lister: StorageBucketLister | None = None,
) -> list[CheckResult]:
    """Check Supabase Storage API access and required bucket posture.

    Args:
        config: Verification configuration.
        bucket_lister: Optional test seam that returns bucket-like values.

    Returns:
        list[CheckResult]: Storage check results.
    """

    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        return [
            result(
                "storage_api_access",
                "fail",
                "SUPABASE_URL and SUPABASE_SECRET_KEY are required for Storage verification.",
                url_configured=bool(os.getenv("SUPABASE_URL")),
                secret_key_type=key_state(os.getenv("SUPABASE_SECRET_KEY")),
            ),
            result("storage_buckets_present", "skip", "Skipped because Storage API is not configured."),
            result("storage_buckets_private", "skip", "Skipped because Storage API is not configured."),
        ]

    try:
        raw_buckets = (
            bucket_lister(config) if bucket_lister is not None else list_storage_buckets(config)
        )
        buckets = [_bucket_to_dict(bucket) for bucket in raw_buckets]
    except Exception as exc:  # noqa: BLE001
        return [
            result("storage_api_access", "fail", "Storage API list_buckets call failed.", error=str(exc)),
            result("storage_buckets_present", "skip", "Skipped because Storage API failed."),
            result("storage_buckets_private", "skip", "Skipped because Storage API failed."),
        ]

    checks = [result("storage_api_access", "pass", "Storage API list_buckets call succeeded.")]
    required = (config.attachment_bucket, config.draft_export_bucket)
    by_name = {
        str(bucket.get("name") or bucket.get("id")): bucket
        for bucket in buckets
        if bucket.get("name") or bucket.get("id")
    }
    missing = [name for name in required if name not in by_name]
    checks.append(
        result(
            "storage_buckets_present",
            "fail" if missing else "pass",
            "Required Storage buckets are present."
            if not missing
            else "Required Storage buckets are missing.",
            missing=missing,
            required=list(required),
        )
    )

    public_buckets = [
        name for name in required if name in by_name and bool(by_name[name].get("public", False))
    ]
    checks.append(
        result(
            "storage_buckets_private",
            "fail" if public_buckets else "pass",
            "Required Storage buckets are private."
            if not public_buckets
            else "One or more required Storage buckets are public.",
            public_buckets=public_buckets,
        )
    )
    return checks


def summarize(checks: list[CheckResult]) -> dict[str, Any]:
    """Summarize a collection of check results.

    Args:
        checks: Verification results.

    Returns:
        dict[str, Any]: Aggregate status and counts.
    """

    counts = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    if counts["fail"]:
        status = "fail"
    elif counts["warn"]:
        status = "warn"
    else:
        status = "pass"
    return {"status": status, **counts, "total": len(checks)}


def run_verification(
    config: VerificationConfig,
    include_cli: bool = False,
    include_db: bool = True,
    include_storage: bool = True,
    project_list_runner: ProjectListRunner | None = None,
    db_query_runner: DatabaseQueryRunner | None = None,
    storage_bucket_lister: StorageBucketLister | None = None,
) -> dict[str, Any]:
    """Run all configured verification checks.

    Args:
        config: Verification configuration.
        include_cli: Whether to run Supabase CLI authentication/link checks.
        include_db: Whether to query Postgres metadata.
        include_storage: Whether to query Supabase Storage metadata.
        project_list_runner: Optional test seam for CLI project list checks.
        db_query_runner: Optional test seam for DB checks.
        storage_bucket_lister: Optional test seam for Storage checks.

    Returns:
        dict[str, Any]: Sanitized verification report.
    """

    checks = check_environment(config)
    if include_cli:
        checks.extend(check_supabase_cli(config, project_list_runner=project_list_runner))
    if include_db:
        checks.extend(check_database(config, query_runner=db_query_runner))
    if include_storage:
        checks.extend(check_storage(config, bucket_lister=storage_bucket_lister))

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "project_ref": config.project_ref,
        "expected_url": config.expected_url,
        "strict": config.strict,
        "summary": summarize(checks),
        "checks": [check.to_dict() for check in checks],
    }
    return redact_value(report)


def collect_sanitized_supabase_health(
    project_ref: str | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Collect sanitized Supabase status for the admin health endpoint.

    Args:
        project_ref: Optional expected project ref override.
        use_cache: Whether to return a recent cached probe result.

    Returns:
        dict[str, Any]: Secret-free health fields.
    """

    config = VerificationConfig(
        project_ref=project_ref or os.getenv("SUPABASE_PROJECT_REF", DEFAULT_PROJECT_REF),
        db_connect_timeout_seconds=int(os.getenv("SUPABASE_HEALTH_DB_TIMEOUT_SECONDS", "2")),
    )
    cache_key = config.project_ref
    now = time.monotonic()
    cached = _SUPABASE_HEALTH_CACHE.get(cache_key)
    if use_cache and cached and now - cached[0] <= _SUPABASE_HEALTH_CACHE_TTL_SECONDS:
        return redact_value(dict(cached[1]))

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    db_backend = os.getenv("APP_DB_BACKEND", "sqlite").strip().lower()
    health: dict[str, Any] = {
        "project_ref_configured": bool(project_ref or os.getenv("SUPABASE_PROJECT_REF")),
        "url_matches_project_ref": bool(supabase_url and supabase_url == config.expected_url),
        "db_backend": db_backend,
        "database_connected": False,
        "alembic_current": False,
        "data_api_locked_down": False,
        "default_admin_risk": False,
        "storage_configured": bool(supabase_url and os.getenv("SUPABASE_SECRET_KEY")),
        "storage_buckets_present": False,
    }

    if db_backend == "postgres" and database_url:
        db_checks = check_database(config)
        by_name = {check.name: check for check in db_checks}
        health["database_connected"] = by_name.get(
            "database_connected", CheckResult("", "fail", "")
        ).status == "pass"
        health["alembic_current"] = by_name.get(
            "alembic_current", CheckResult("", "fail", "")
        ).status == "pass"
        health["data_api_locked_down"] = (
            by_name.get("sensitive_role_grants", CheckResult("", "fail", "")).status == "pass"
            and by_name.get("data_api_deny_policies", CheckResult("", "fail", "")).status == "pass"
        )
        health["default_admin_risk"] = (
            by_name.get("default_admin_risk", CheckResult("", "pass", "")).status in {"fail", "warn"}
        )

    if health["storage_configured"]:
        storage_checks = check_storage(config)
        by_name = {check.name: check for check in storage_checks}
        health["storage_buckets_present"] = by_name.get(
            "storage_buckets_present", CheckResult("", "fail", "")
        ).status == "pass"

    if (
        health["url_matches_project_ref"]
        and (db_backend != "postgres" or health["database_connected"])
        and (not health["storage_configured"] or health["storage_buckets_present"])
    ):
        health["status"] = "ok"
    else:
        health["status"] = "warn"
    sanitized = redact_value(health)
    _SUPABASE_HEALTH_CACHE[cache_key] = (now, dict(sanitized))
    return sanitized


def write_markdown_report(report: Mapping[str, Any], output_path: Path) -> None:
    """Write a team-shareable Markdown verification report.

    Args:
        report: Verification report from run_verification.
        output_path: Markdown output path.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    lines = [
        "# Supabase Remote Verification",
        "",
        f"- Checked at: `{report['checked_at']}`",
        f"- Project ref: `{report['project_ref']}`",
        f"- Expected URL: `{report['expected_url']}`",
        f"- Strict mode: `{report['strict']}`",
        f"- Overall status: `{summary['status']}`",
        f"- Counts: pass={summary['pass']}, warn={summary['warn']}, fail={summary['fail']}, skip={summary['skip']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Summary |",
        "|---|---:|---|",
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['name']}` | `{check['status']}` | {check['summary']} |")
    lines.extend(
        [
            "",
            "## Redacted JSON",
            "",
            "```json",
            json.dumps(redact_value(dict(report)), ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def print_console_report(report: Mapping[str, Any]) -> None:
    """Print a compact console verification summary.

    Args:
        report: Verification report from run_verification.
    """

    summary = report["summary"]
    print(f"Supabase remote verification: {summary['status']}")
    print(f"project_ref={report['project_ref']} expected_url={report['expected_url']}")
    print(
        f"checks pass={summary['pass']} warn={summary['warn']} "
        f"fail={summary['fail']} skip={summary['skip']}"
    )
    for check in report["checks"]:
        print(f"- [{check['status']}] {check['name']}: {check['summary']}")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-ref", default=os.getenv("SUPABASE_PROJECT_REF", DEFAULT_PROJECT_REF))
    parser.add_argument("--strict", action="store_true", help="Fail release transition warnings.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--markdown", type=Path, help="Write a Markdown verification report.")
    parser.add_argument("--skip-cli", action="store_true", help="Skip Supabase CLI auth/link checks.")
    parser.add_argument("--skip-db", action="store_true", help="Skip Postgres metadata checks.")
    parser.add_argument("--skip-storage", action="store_true", help="Skip Storage API checks.")
    return parser.parse_args()


def main() -> int:
    """Run the CLI verifier.

    Returns:
        int: Process exit code.
    """

    args = parse_args()
    config = VerificationConfig(
        project_ref=args.project_ref,
        strict=args.strict,
        attachment_bucket=os.getenv(
            "SUPABASE_STORAGE_BUCKET_ATTACHMENTS", DEFAULT_ATTACHMENT_BUCKET
        ),
        draft_export_bucket=os.getenv(
            "SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS", DEFAULT_DRAFT_EXPORT_BUCKET
        ),
    )
    report = run_verification(
        config,
        include_cli=args.strict and not args.skip_cli,
        include_db=not args.skip_db,
        include_storage=not args.skip_storage,
    )
    if args.markdown:
        write_markdown_report(report, args.markdown)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_console_report(report)
    return 1 if report["summary"]["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
