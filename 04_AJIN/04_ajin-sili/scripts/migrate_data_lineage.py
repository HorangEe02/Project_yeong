#!/usr/bin/env python3
"""Non-destructive migration for A/E/F data source labeling.

The migration adds shared lineage columns and backfills existing seed/demo
rows. It never deletes rows and never changes CSV headers; generated CSV files
receive ``.source.json`` sidecar manifests when ``--apply`` is used.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.data_lineage import (  # noqa: E402
    ensure_lineage_columns,
    lineage_values,
    table_columns,
    table_exists,
    write_source_manifest,
)
from core.directory.migrations import SEED_TEST_EMPLOYEE_IDS  # noqa: E402


def _count_by_class(conn: sqlite3.Connection, table_name: str) -> dict[str, int]:
    """Count rows grouped by ``data_class`` after lineage columns are present.

    Args:
        conn: Open SQLite connection.
        table_name: Table name to count.

    Returns:
        Mapping of data class to row count.
    """
    if not table_exists(conn, table_name):
        return {}
    rows = conn.execute(
        f"SELECT data_class, COUNT(*) FROM {table_name} GROUP BY data_class ORDER BY data_class"
    ).fetchall()
    return {str(k or "unknown"): int(v or 0) for k, v in rows}


def _update(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    """Execute an UPDATE statement and return rowcount.

    Args:
        conn: Open SQLite connection.
        sql: Application-owned SQL statement.
        params: Bound parameters.

    Returns:
        Number of rows affected according to sqlite3.
    """
    cur = conn.execute(sql, params)
    return int(cur.rowcount or 0)


def _migrate_employees(conn: sqlite3.Connection) -> dict[str, int | dict[str, int]]:
    """Apply Feature A lineage to employees.db.

    Args:
        conn: employees.db connection.

    Returns:
        Summary with added columns, updated rows, and class counts.
    """
    added = ensure_lineage_columns(conn, "employees")
    real = lineage_values("real", "erp_csv", "ERP CSV sync")
    synthetic = lineage_values("synthetic", "seed", "Seed/demo employees")
    updated = 0
    updated += _update(conn, "UPDATE employees SET source_system='erp_csv' WHERE is_synthetic=0 AND source_system='erp'")
    updated += _update(
        conn,
        """UPDATE employees
              SET data_class=?,
                  source_system=CASE
                      WHEN source_system IN ('', 'unknown', 'seed', 'erp') THEN ?
                      ELSE source_system
                  END,
                  source_label=CASE WHEN source_label IS NULL OR source_label='' THEN ? ELSE source_label END,
                  source_updated_at=CASE
                      WHEN source_updated_at IS NULL OR source_updated_at='' THEN ?
                      ELSE source_updated_at
                  END
            WHERE is_synthetic=0""",
        (real["data_class"], real["source_system"], real["source_label"], real["source_updated_at"]),
    )
    updated += _update(
        conn,
        """UPDATE employees
              SET data_class=?,
                  source_system=CASE
                      WHEN source_system IS NULL OR source_system='' OR source_system='unknown' THEN ?
                      ELSE source_system
                  END,
                  source_label=CASE WHEN source_label IS NULL OR source_label='' THEN ? ELSE source_label END,
                  source_updated_at=CASE
                      WHEN source_updated_at IS NULL OR source_updated_at='' THEN ?
                      ELSE source_updated_at
                  END
            WHERE is_synthetic=1
               OR data_class IS NULL OR data_class='' OR data_class='unknown'""",
        (
            synthetic["data_class"],
            synthetic["source_system"],
            synthetic["source_label"],
            synthetic["source_updated_at"],
        ),
    )
    updated += _update(
        conn,
        """UPDATE employees
              SET canonical_employee_id = employee_id
            WHERE data_class='real'
              AND (canonical_employee_id IS NULL OR canonical_employee_id='')""",
    )
    return {"added_columns": added, "updated_rows": updated, "counts": _count_by_class(conn, "employees")}


def _migrate_auth(conn: sqlite3.Connection) -> dict[str, int | dict[str, dict[str, int]]]:
    """Apply Feature E lineage to auth users and login history.

    Args:
        conn: auth.db connection.

    Returns:
        Summary with added columns, updated rows, and class counts.
    """
    added = ensure_lineage_columns(conn, "users") + ensure_lineage_columns(conn, "login_history")
    updated = 0
    system = lineage_values("system", "bootstrap_admin", "Initial bootstrap admin")
    updated += _update(
        conn,
        """UPDATE users
              SET data_class=?, source_system=?, source_label=?, source_updated_at=?
            WHERE employee_id='admin'""",
        (system["data_class"], system["source_system"], system["source_label"], system["source_updated_at"]),
    )
    synthetic = lineage_values("synthetic", "seed_test_users", "Seed test users")
    placeholders = ",".join("?" for _ in SEED_TEST_EMPLOYEE_IDS)
    updated += _update(
        conn,
        f"""UPDATE users
               SET data_class=?, source_system=?, source_label=?, source_updated_at=?
             WHERE employee_id IN ({placeholders})""",
        (
            synthetic["data_class"],
            synthetic["source_system"],
            synthetic["source_label"],
            synthetic["source_updated_at"],
            *SEED_TEST_EMPLOYEE_IDS,
        ),
    )
    if "password_hash" in table_columns(conn, "users"):
        for marker, source_system in (("!LDAP!", "idp_ldap"), ("!OIDC!", "idp_oidc"), ("!SAML!", "idp_saml")):
            real = lineage_values("real", source_system, source_system)
            updated += _update(
                conn,
                """UPDATE users
                      SET data_class=?, source_system=?, source_label=?, source_updated_at=?
                    WHERE password_hash=?""",
                (real["data_class"], real["source_system"], real["source_label"], real["source_updated_at"], marker),
            )
    updated += _update(
        conn,
        """UPDATE login_history
              SET data_class=COALESCE((SELECT u.data_class FROM users u WHERE u.employee_id=login_history.employee_id), data_class),
                  source_system=COALESCE((SELECT u.source_system FROM users u WHERE u.employee_id=login_history.employee_id), source_system),
                  source_label=CASE WHEN source_label IS NULL OR source_label='' THEN 'auth_login_history' ELSE source_label END,
                  source_updated_at=CASE WHEN source_updated_at IS NULL OR source_updated_at='' THEN datetime('now') ELSE source_updated_at END
            WHERE data_class IS NULL OR data_class='' OR data_class='unknown'""",
    )
    return {
        "added_columns": added,
        "updated_rows": updated,
        "counts": {
            "users": _count_by_class(conn, "users"),
            "login_history": _count_by_class(conn, "login_history"),
        },
    }


def _seed_table(conn: sqlite3.Connection, table_name: str, *, source_system: str = "seed_equipment") -> int:
    """Mark existing rows in one equipment table as synthetic seed data.

    Args:
        conn: Open SQLite connection.
        table_name: Table to backfill.
        source_system: Source-system label.

    Returns:
        Number of rows updated.
    """
    ensure_lineage_columns(conn, table_name)
    lineage = lineage_values("synthetic", source_system, source_system)
    return _update(
        conn,
        f"""UPDATE {table_name}
              SET data_class=?, source_system=?, source_label=?, source_updated_at=?
            WHERE data_class IS NULL OR data_class='' OR data_class='unknown'""",
        (lineage["data_class"], lineage["source_system"], lineage["source_label"], lineage["source_updated_at"]),
    )


def _migrate_equipment_seed_tables(conn: sqlite3.Connection, table_names: tuple[str, ...]) -> dict:
    """Apply synthetic seed labels to Feature F SQLite tables.

    Args:
        conn: Open equipment database connection.
        table_names: Existing table names to process.

    Returns:
        Summary with added/updated information.
    """
    updated = 0
    counts: dict[str, dict[str, int]] = {}
    for table in table_names:
        if not table_exists(conn, table):
            continue
        updated += _seed_table(conn, table)
        counts[table] = _count_by_class(conn, table)
    return {"updated_rows": updated, "counts": counts}


def _migrate_inspection(conn: sqlite3.Connection) -> dict:
    """Apply source labels to inspection logs and ingest logs.

    Args:
        conn: inspection.db connection.

    Returns:
        Summary dict.
    """
    updated = 0
    for table in ("checklist_templates", "inspection_logs", "inspection_ingest_log"):
        if table_exists(conn, table):
            ensure_lineage_columns(conn, table)
    if table_exists(conn, "checklist_templates"):
        updated += _seed_table(conn, "checklist_templates")
    if table_exists(conn, "inspection_logs"):
        try:
            conn.execute("ALTER TABLE inspection_logs ADD COLUMN source TEXT DEFAULT 'unknown'")
        except sqlite3.OperationalError:
            pass
        seed = lineage_values("synthetic", "seed_equipment", "seed_equipment")
        real_csv = lineage_values("real", "csv_upload", "csv_upload")
        real_pwa = lineage_values("real", "tablet_pwa", "tablet_pwa")
        updated += _update(
            conn,
            """UPDATE inspection_logs
                  SET data_class=?, source_system=?, source_label=?, source_updated_at=?
                WHERE source IN ('', 'unknown', 'synthetic', 'seed_equipment', 'test')
                  AND (data_class IS NULL OR data_class='' OR data_class='unknown')""",
            (seed["data_class"], seed["source_system"], seed["source_label"], seed["source_updated_at"]),
        )
        updated += _update(
            conn,
            """UPDATE inspection_logs
                  SET data_class=?, source_system=?, source_label=?, source_updated_at=?
                WHERE source='csv_upload'""",
            (real_csv["data_class"], real_csv["source_system"], real_csv["source_label"], real_csv["source_updated_at"]),
        )
        updated += _update(
            conn,
            """UPDATE inspection_logs
                  SET data_class=?, source_system=?, source_label=?, source_updated_at=?
                WHERE source='tablet_pwa'""",
            (real_pwa["data_class"], real_pwa["source_system"], real_pwa["source_label"], real_pwa["source_updated_at"]),
        )
    if table_exists(conn, "inspection_ingest_log"):
        seed = lineage_values("synthetic", "seed_equipment", "seed_equipment")
        real_csv = lineage_values("real", "csv_upload", "csv_upload")
        updated += _update(
            conn,
            """UPDATE inspection_ingest_log
                  SET data_class=?, source_system=?, source_updated_at=?
                WHERE source_label IN ('test', 'synthetic', 'seed_equipment')
                  AND (data_class IS NULL OR data_class='' OR data_class='unknown')""",
            (seed["data_class"], seed["source_system"], seed["source_updated_at"]),
        )
        updated += _update(
            conn,
            """UPDATE inspection_ingest_log
                  SET data_class=?, source_system=?, source_updated_at=?
                WHERE source_label NOT IN ('test', 'synthetic', 'seed_equipment')
                  AND (data_class IS NULL OR data_class='' OR data_class='unknown')""",
            (real_csv["data_class"], real_csv["source_system"], real_csv["source_updated_at"]),
        )
    return {
        "updated_rows": updated,
        "counts": {
            table: _count_by_class(conn, table)
            for table in ("checklist_templates", "inspection_logs", "inspection_ingest_log")
            if table_exists(conn, table)
        },
    }


def _migrate_spc_violations(conn: sqlite3.Connection) -> dict:
    """Mark persisted SPC violations as real PLC-ingest events.

    Args:
        conn: spc_violations.db connection.

    Returns:
        Summary dict.
    """
    if not table_exists(conn, "spc_violations"):
        return {"skipped": "missing_table"}
    ensure_lineage_columns(conn, "spc_violations")
    lineage = lineage_values("real", "plc_ingest", "plc_ingest")
    updated = _update(
        conn,
        """UPDATE spc_violations
              SET data_class=?, source_system=?, source_label=?, source_updated_at=?
            WHERE data_class IS NULL OR data_class='' OR data_class='unknown'""",
        (lineage["data_class"], lineage["source_system"], lineage["source_label"], lineage["source_updated_at"]),
    )
    return {"updated_rows": updated, "counts": {"spc_violations": _count_by_class(conn, "spc_violations")}}


def _with_db(
    path: Path,
    apply: bool,
    migration: Callable[[sqlite3.Connection], dict],
) -> dict:
    """Run one DB migration with rollback in dry-run mode.

    Args:
        path: SQLite database path.
        apply: Whether to commit changes.
        migration: Migration callback.

    Returns:
        Summary dictionary.
    """
    if not path.exists():
        return {"skipped": "missing"}
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("BEGIN")
        summary = migration(conn)
        if apply:
            conn.commit()
        else:
            conn.rollback()
        return summary
    finally:
        conn.close()


def _write_file_manifests(apply: bool) -> dict[str, int]:
    """Write sidecar manifests for generated equipment CSV files.

    Args:
        apply: Whether to write files or only report candidates.

    Returns:
        Count by source directory.
    """
    patterns = {
        "spc_samples": REPO_ROOT / "data" / "spc_samples",
        "spc_ml": REPO_ROOT / "data" / "spc_ml",
        "mold_ml": REPO_ROOT / "data" / "mold_ml",
    }
    counts: dict[str, int] = {}
    for label, directory in patterns.items():
        files = sorted(p for p in directory.glob("*.csv") if p.is_file()) if directory.exists() else []
        counts[label] = len(files)
        if apply:
            for path in files:
                write_source_manifest(
                    path,
                    data_class="synthetic",
                    source_system="seed_equipment",
                    source_label=f"{label}:existing_file",
                )
    return counts


def run(apply: bool = False) -> dict[str, dict]:
    """Run all A/E/F lineage migrations.

    Args:
        apply: If false, all SQLite changes are rolled back and manifests are not written.

    Returns:
        Nested migration summary.
    """
    data = REPO_ROOT / "data"
    equipment = data / "equipment"
    return {
        "employees": _with_db(data / "employees.db", apply, _migrate_employees),
        "auth": _with_db(data / "auth.db", apply, _migrate_auth),
        "equipment_error_codes": _with_db(
            equipment / "error_codes.db",
            apply,
            lambda conn: _migrate_equipment_seed_tables(conn, ("error_codes",)),
        ),
        "equipment_mold_lifecycle": _with_db(
            equipment / "mold_lifecycle.db",
            apply,
            lambda conn: _migrate_equipment_seed_tables(
                conn,
                ("molds", "mold_shot_logs", "mold_maintenance_logs"),
            ),
        ),
        "equipment_molds": _with_db(
            equipment / "molds.db",
            apply,
            lambda conn: _migrate_equipment_seed_tables(conn, ("molds",)),
        ),
        "equipment_drawings": _with_db(
            equipment / "drawings.db",
            apply,
            lambda conn: _migrate_equipment_seed_tables(conn, ("drawings",)),
        ),
        "equipment_error_history": _with_db(
            equipment / "error_history.db",
            apply,
            lambda conn: _migrate_equipment_seed_tables(conn, ("error_history",)),
        ),
        "equipment_spc_violations": _with_db(
            data / "spc_violations.db",
            apply,
            _migrate_spc_violations,
        ),
        "equipment_inspection": _with_db(equipment / "inspection.db", apply, _migrate_inspection),
        "file_manifests": _write_file_manifests(apply),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    Args:
        argv: Optional argument list.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description="Apply A/E/F data lineage labels")
    parser.add_argument("--apply", action="store_true", help="commit SQLite changes and write CSV sidecars")
    args = parser.parse_args(argv)
    summary = run(apply=args.apply)
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] A/E/F data lineage migration")
    for key, value in summary.items():
        print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
