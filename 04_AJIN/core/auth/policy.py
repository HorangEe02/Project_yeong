"""Feature E authentication and account operation policy helpers.

The helpers in this module keep production authentication decisions in one
place so router code can fail closed without duplicating environment parsing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


PRIMARY_PROVIDERS = {"idp", "local", "hybrid"}


def env_truthy(name: str, default: bool = False) -> bool:
    """Return whether an environment variable is enabled.

    Args:
        name: Environment variable name.
        default: Value returned when the variable is unset.

    Returns:
        bool: True for common truthy string values.
    """

    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_production_runtime() -> bool:
    """Detect a production or Cloud Run runtime.

    Returns:
        bool: True when an environment marker indicates production.
    """

    env_values = (
        os.environ.get("APP_ENV", ""),
        os.environ.get("ENVIRONMENT", ""),
        os.environ.get("AJIN_ENVIRONMENT", ""),
    )
    return any(value.strip().lower() == "production" for value in env_values) or bool(
        os.environ.get("K_SERVICE")
    )


def auth_primary_provider() -> str:
    """Resolve the primary authentication provider.

    Returns:
        str: One of ``idp``, ``local``, or ``hybrid``. Production defaults to
        ``idp`` when ``AUTH_PRIMARY_PROVIDER`` is unset; local/test defaults to
        ``hybrid`` for developer ergonomics.

    Raises:
        ValueError: If ``AUTH_PRIMARY_PROVIDER`` has an unsupported value.
    """

    raw = os.environ.get("AUTH_PRIMARY_PROVIDER", "").strip().lower()
    if not raw:
        return "idp" if is_production_runtime() else "hybrid"
    if raw not in PRIMARY_PROVIDERS:
        raise ValueError(f"Unsupported AUTH_PRIMARY_PROVIDER: {raw}")
    return raw


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    """Read a key from sqlite rows, dicts, or simple objects."""

    try:
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        if key in keys:
            return row[key]
    except Exception:
        pass
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def is_break_glass_user(user_row: Any) -> bool:
    """Return whether a row is allowed to use local password login in IdP mode.

    Args:
        user_row: Auth user row joined with role metadata.

    Returns:
        bool: True only for SYS_ADMIN L5 users whose account is bootstrap
        lineage, or for SYS_ADMIN L5 users when the explicit break-glass env
        override is enabled.
    """

    role_name = str(_row_get(user_row, "role_name", _row_get(user_row, "role", "")) or "")
    try:
        role_level = int(_row_get(user_row, "role_level", 0) or 0)
    except (TypeError, ValueError):
        role_level = 0
    source_system = str(_row_get(user_row, "source_system", "") or "").strip().lower()
    explicit_override = env_truthy("AUTH_ALLOW_BREAK_GLASS_LOGIN", default=False)
    return role_name == "SYS_ADMIN" and role_level >= 5 and (
        source_system == "bootstrap_admin" or explicit_override
    )


def local_password_login_block_reason(user_row: Any) -> str | None:
    """Return the local-login block reason for a user row.

    Args:
        user_row: Auth user row joined with role metadata.

    Returns:
        str | None: ``local_login_disabled`` or ``break_glass_2fa_required``
        when local login must be denied; otherwise ``None``.
    """

    if auth_primary_provider() != "idp":
        return None
    if not is_break_glass_user(user_row):
        return "local_login_disabled"
    if not bool(_row_get(user_row, "totp_enabled", 0)):
        return "break_glass_2fa_required"
    return None


def plaintext_initial_password_allowed() -> bool:
    """Return whether admin APIs may echo a generated temporary password.

    Returns:
        bool: False in production. Non-production defaults to true for local
        workflows but can be disabled with ``AUTH_ALLOW_PLAINTEXT_INITIAL_PASSWORD=false``.
    """

    if is_production_runtime():
        return False
    return env_truthy("AUTH_ALLOW_PLAINTEXT_INITIAL_PASSWORD", default=True)


def seed_test_users_allowed() -> bool:
    """Return whether synthetic auth test users may be seeded.

    Returns:
        bool: True only when explicitly enabled and not production.
    """

    return (not is_production_runtime()) and env_truthy("AUTH_SEED_TEST_USERS", default=False)


def hard_delete_allowed() -> bool:
    """Return whether admin hard delete is enabled.

    Returns:
        bool: True only when explicitly enabled. Production should normally keep
        this false and use retire/tombstone flows instead.
    """

    return env_truthy("AUTH_ALLOW_HARD_DELETE", default=False)


@dataclass(frozen=True)
class AuditRetentionPolicy:
    """Default audit retention posture.

    Args:
        hot_days: Days kept in the hot query path.
        archive_years: Years retained in archive storage.
        hard_delete_default: Whether hard delete is enabled by default.
    """

    hot_days: int = 365
    archive_years: int = 3
    hard_delete_default: bool = False


def audit_retention_policy() -> AuditRetentionPolicy:
    """Return the default Feature E audit retention policy."""

    return AuditRetentionPolicy()
