"""Shared data lineage helpers for real/synthetic source labeling.

The application keeps demo data for local development, but production-facing
queries need a consistent way to distinguish real operational rows from seed
or bootstrap rows. This module centralizes that small contract for SQLite
tables and file sidecar manifests.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_DATA_CLASSES = {"real", "synthetic", "demo", "system", "unknown"}

LINEAGE_COLUMN_DEFS: dict[str, str] = {
    "data_class": "TEXT NOT NULL DEFAULT 'unknown'",
    "source_system": "TEXT NOT NULL DEFAULT 'unknown'",
    "source_label": "TEXT DEFAULT ''",
    "source_updated_at": "TEXT DEFAULT ''",
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def utcnow_iso() -> str:
    """Return a UTC ISO-8601 timestamp with second precision.

    Returns:
        A string timestamp such as ``2026-05-18T12:34:56Z``.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_data_class(value: str | None) -> str:
    """Normalize a data-class value to the allowed vocabulary.

    Args:
        value: Candidate data class from code, DB, or manifest.

    Returns:
        One of ``real``, ``synthetic``, ``demo``, ``system``, or ``unknown``.
    """
    normalized = (value or "").strip().lower()
    return normalized if normalized in VALID_DATA_CLASSES else "unknown"


def lineage_values(
    data_class: str,
    source_system: str,
    source_label: str = "",
    *,
    updated_at: str | None = None,
) -> dict[str, str]:
    """Build the canonical lineage value dict used by INSERT/UPDATE statements.

    Args:
        data_class: Canonical class, usually ``real``, ``synthetic``, or ``system``.
        source_system: Machine-readable origin such as ``erp_csv`` or ``idp_oidc``.
        source_label: Human-readable provenance label for diagnostics.
        updated_at: Optional timestamp override.

    Returns:
        Dict containing ``data_class``, ``source_system``, ``source_label``, and
        ``source_updated_at``.
    """
    return {
        "data_class": normalize_data_class(data_class),
        "source_system": (source_system or "unknown").strip() or "unknown",
        "source_label": (source_label or "").strip(),
        "source_updated_at": updated_at or utcnow_iso(),
    }


def should_include_non_real_data() -> bool:
    """Return whether default reads should include synthetic/demo/system rows.

    Production mode is enabled by ``AJIN_DATA_CLASS_MODE=production|prod|real``
    or ``AJIN_EXCLUDE_SYNTHETIC=1|true|yes|on``. Local development keeps demo
    data visible by default so existing seed-based flows continue to work.

    Returns:
        ``False`` in production real-data mode, otherwise ``True``.
    """
    mode = (os.environ.get("AJIN_DATA_CLASS_MODE") or "").strip().lower()
    exclude = (os.environ.get("AJIN_EXCLUDE_SYNTHETIC") or "").strip().lower()
    if mode in {"production", "prod", "real", "real_only"}:
        return False
    return exclude not in {"1", "true", "yes", "on"}


def _quote_identifier(identifier: str) -> str:
    """Validate and quote a SQLite identifier.

    Args:
        identifier: Table or column name controlled by application code.

    Returns:
        A double-quoted identifier.

    Raises:
        ValueError: If the identifier is not a simple SQLite identifier.
    """
    if not _IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Unsafe SQLite identifier: {identifier!r}")
    return f'"{identifier}"'


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check whether a table exists in the current SQLite database.

    Args:
        conn: Open SQLite connection.
        table_name: Table name to check.

    Returns:
        ``True`` if the table exists.
    """
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    """Return the column names for a SQLite table.

    Args:
        conn: Open SQLite connection.
        table_name: Table name to inspect.

    Returns:
        Set of column names. Missing tables return an empty set.
    """
    if not table_exists(conn, table_name):
        return set()
    return {row[1] for row in conn.execute(f"PRAGMA table_info({_quote_identifier(table_name)})")}


def ensure_lineage_columns(
    conn: sqlite3.Connection,
    table_name: str,
    *,
    defaults: dict[str, str] | None = None,
) -> int:
    """Idempotently add common lineage columns to a SQLite table.

    Args:
        conn: Open SQLite connection.
        table_name: Existing table name.
        defaults: Optional per-column SQL definitions. Use this only for
            application-controlled definitions.

    Returns:
        Number of newly added columns.

    Raises:
        ValueError: If ``table_name`` is not a safe identifier.
    """
    if not table_exists(conn, table_name):
        return 0

    existing = table_columns(conn, table_name)
    definitions = {**LINEAGE_COLUMN_DEFS, **(defaults or {})}
    added = 0
    quoted_table = _quote_identifier(table_name)
    for column, definition in definitions.items():
        if column in existing:
            continue
        conn.execute(f"ALTER TABLE {quoted_table} ADD COLUMN {_quote_identifier(column)} {definition}")
        added += 1
    return added


def set_lineage_for_rows(
    conn: sqlite3.Connection,
    table_name: str,
    *,
    data_class: str,
    source_system: str,
    source_label: str = "",
    where_sql: str = "1=1",
    params: tuple[Any, ...] = (),
    only_unknown: bool = False,
) -> int:
    """Backfill lineage values for rows matching a predicate.

    Args:
        conn: Open SQLite connection.
        table_name: Table to update.
        data_class: Target data class.
        source_system: Target source system.
        source_label: Diagnostic source label.
        where_sql: SQL predicate without ``WHERE``. It must be application-owned.
        params: Bind parameters for ``where_sql``.
        only_unknown: If true, only rows without an explicit lineage are updated.

    Returns:
        SQLite cursor rowcount.
    """
    ensure_lineage_columns(conn, table_name)
    predicate = f"({where_sql})"
    if only_unknown:
        predicate += " AND (data_class IS NULL OR data_class = '' OR data_class = 'unknown')"
    values = lineage_values(data_class, source_system, source_label)
    cursor = conn.execute(
        f"""UPDATE {_quote_identifier(table_name)}
               SET data_class = ?,
                   source_system = ?,
                   source_label = ?,
                   source_updated_at = ?
             WHERE {predicate}""",
        (
            values["data_class"],
            values["source_system"],
            values["source_label"],
            values["source_updated_at"],
            *params,
        ),
    )
    return int(cursor.rowcount or 0)


def data_class_predicate(
    *,
    include_non_real: bool | None = None,
    alias: str = "",
    fallback_is_synthetic_column: str | None = None,
) -> str:
    """Build a SQL predicate for default production real-data filtering.

    Args:
        include_non_real: Explicit override. ``None`` reads the environment.
        alias: Optional table alias without trailing dot.
        fallback_is_synthetic_column: Optional legacy boolean column used when
            ``data_class`` is empty.

    Returns:
        ``1=1`` when non-real rows are visible, otherwise a real-row predicate.
    """
    include = should_include_non_real_data() if include_non_real is None else include_non_real
    if include:
        return "1=1"

    prefix = f"{_quote_identifier(alias)}." if alias else ""
    data_expr = f"{prefix}{_quote_identifier('data_class')}"
    if fallback_is_synthetic_column:
        legacy = f"{prefix}{_quote_identifier(fallback_is_synthetic_column)}"
        data_expr = f"COALESCE(NULLIF({data_expr}, ''), CASE WHEN {legacy}=1 THEN 'synthetic' ELSE 'real' END)"
    return f"{data_expr} = 'real'"


def source_manifest_path(data_path: Path) -> Path:
    """Return the sidecar manifest path for a data file.

    Args:
        data_path: CSV or data file path.

    Returns:
        Path ending in ``.source.json`` without changing the original file.
    """
    return data_path.with_suffix(f"{data_path.suffix}.source.json")


def write_source_manifest(
    data_path: Path,
    *,
    data_class: str,
    source_system: str,
    source_label: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write a sidecar source manifest for a CSV or generated data file.

    Args:
        data_path: Data file being labeled.
        data_class: Canonical class for the file contents.
        source_system: Origin system name.
        source_label: Human-readable origin label.
        extra: Optional extra metadata.

    Returns:
        The sidecar manifest path.
    """
    manifest = source_manifest_path(data_path)
    payload: dict[str, Any] = {
        "data_file": data_path.name,
        **lineage_values(data_class, source_system, source_label),
    }
    if extra:
        payload["extra"] = extra
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
