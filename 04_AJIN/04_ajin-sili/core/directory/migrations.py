"""Idempotent migration runner for the canonical directory.

Targets 3 SQLite DBs. Each ALTER ADD COLUMN is wrapped in try/except
sqlite3.OperationalError so re-running is a no-op (SQLite has no
ADD COLUMN IF NOT EXISTS).

Usage:
    from core.directory.migrations import apply_all
    apply_all()

Called from:
    - features/search/employee/database.py:_init_tables() on import
    - backend/auth_middleware.py:init_audit_db() (audit subset)
    - CLI: python -m core.directory.migrations
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from core.data_lineage import ensure_lineage_columns, lineage_values, table_columns, table_exists

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"

EMPLOYEES_DB = DATA_DIR / "employees.db"
AUTH_DB = DATA_DIR / "auth.db"
AUDIT_DB = DATA_DIR / "audit.db"


def _exec_idempotent(conn: sqlite3.Connection, sql: str) -> bool:
    """Run a single statement; swallow OperationalError (duplicate column etc).

    Returns True if executed, False if already-applied.
    """
    try:
        conn.execute(sql)
        return True
    except sqlite3.OperationalError as exc:
        # "duplicate column name" / "already exists" — already migrated.
        logger.debug("migration step skipped (%s): %s", exc, sql.strip().splitlines()[0])
        return False


# ─────────────────────────────────────────────────────────
# employees.db
# ─────────────────────────────────────────────────────────

EMPLOYEES_MIGRATIONS = [
    "ALTER TABLE employees ADD COLUMN is_synthetic INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE employees ADD COLUMN source_system TEXT NOT NULL DEFAULT 'seed'",
    "ALTER TABLE employees ADD COLUMN canonical_employee_id TEXT",
    "ALTER TABLE employees ADD COLUMN data_class TEXT NOT NULL DEFAULT 'unknown'",
    "ALTER TABLE employees ADD COLUMN source_label TEXT DEFAULT ''",
    "ALTER TABLE employees ADD COLUMN source_updated_at TEXT DEFAULT ''",
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_emp_canonical
       ON employees(canonical_employee_id) WHERE canonical_employee_id IS NOT NULL""",
    "CREATE INDEX IF NOT EXISTS idx_emp_synthetic ON employees(is_synthetic)",
    "CREATE INDEX IF NOT EXISTS idx_emp_data_class ON employees(data_class)",
    """CREATE TABLE IF NOT EXISTS headcount_snapshot (
         snapshot_date TEXT PRIMARY KEY,
         total_active INTEGER NOT NULL,
         synthetic_count INTEGER NOT NULL,
         real_count INTEGER NOT NULL,
         computed_at TEXT NOT NULL DEFAULT (datetime('now'))
       )""",
    """CREATE TABLE IF NOT EXISTS search_history (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         user_id TEXT NOT NULL,
         query TEXT NOT NULL,
         intent TEXT,
         clicked_rank INTEGER,
         action_invoked TEXT,
         latency_ms INTEGER,
         result_count INTEGER,
         ts TEXT NOT NULL DEFAULT (datetime('now'))
       )""",
    "CREATE INDEX IF NOT EXISTS idx_sh_user_ts ON search_history(user_id, ts DESC)",
    "CREATE INDEX IF NOT EXISTS idx_sh_intent_ts ON search_history(intent, ts DESC)",
]


# ─────────────────────────────────────────────────────────
# auth.db (users.employee_id already exists as NOT NULL UNIQUE)
# ─────────────────────────────────────────────────────────

AUTH_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN data_class TEXT NOT NULL DEFAULT 'unknown'",
    "ALTER TABLE users ADD COLUMN source_system TEXT NOT NULL DEFAULT 'unknown'",
    "ALTER TABLE users ADD COLUMN source_label TEXT DEFAULT ''",
    "ALTER TABLE users ADD COLUMN source_updated_at TEXT DEFAULT ''",
    "ALTER TABLE login_history ADD COLUMN data_class TEXT NOT NULL DEFAULT 'unknown'",
    "ALTER TABLE login_history ADD COLUMN source_system TEXT NOT NULL DEFAULT 'unknown'",
    "ALTER TABLE login_history ADD COLUMN source_label TEXT DEFAULT ''",
    "ALTER TABLE login_history ADD COLUMN source_updated_at TEXT DEFAULT ''",
    "CREATE INDEX IF NOT EXISTS idx_users_emp ON users(employee_id)",
    "CREATE INDEX IF NOT EXISTS idx_users_data_class ON users(data_class)",
    "CREATE INDEX IF NOT EXISTS idx_login_history_data_class ON login_history(data_class)",
]

SEED_TEST_EMPLOYEE_IDS = (
    "HR-0001", "QA-0100", "PR-0200", "IT-0001", "QM-0001",
    "QA-0101", "PT-0301", "SL-0401", "ES-0001", "PU-0001", "RE-0001",
    "QA-0102", "QA-0001", "GS-0001", "SF-0001", "SF-0501", "RB-0001",
    "RD-0801", "MF-0901", "PM-0001", "SL-0001", "EX-0001", "IT-0701",
    "PU-0601", "AT-0001", "ED-0001", "HR-0000", "MD-0001", "PD-0001",
    "PT-0001", "VR-0001", "HR-0002", "HR-9999",
)


# ─────────────────────────────────────────────────────────
# audit.db
# ─────────────────────────────────────────────────────────

AUDIT_MIGRATIONS = [
    "ALTER TABLE api_audit_log ADD COLUMN latency_ms INTEGER",
    "ALTER TABLE api_audit_log ADD COLUMN intent TEXT",
    "ALTER TABLE api_audit_log ADD COLUMN result_count INTEGER",
    "CREATE INDEX IF NOT EXISTS idx_audit_latency ON api_audit_log(timestamp, latency_ms)",
    # Feature B Sprint 1 P0 — mail send audit (plan §14.2)
    """CREATE TABLE IF NOT EXISTS mail_audit_log (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         ts TEXT NOT NULL DEFAULT (datetime('now')),
         user_id INTEGER,
         sender_email TEXT,
         version_id INTEGER,
         version_status TEXT,
         adapter TEXT,
         ok INTEGER,
         message_id TEXT,
         to_count INTEGER DEFAULT 0,
         cc_count INTEGER DEFAULT 0,
         bcc_count INTEGER DEFAULT 0,
         external_domains TEXT,
         guard_decision TEXT,
         watermark_id TEXT,
         detail TEXT
       )""",
    "CREATE INDEX IF NOT EXISTS idx_mail_audit_ts ON mail_audit_log(ts DESC)",
    "CREATE INDEX IF NOT EXISTS idx_mail_audit_user ON mail_audit_log(user_id, ts DESC)",
    "CREATE INDEX IF NOT EXISTS idx_mail_audit_decision ON mail_audit_log(guard_decision, ts DESC)",
]


def _apply(db_path: Path, statements: list[str], label: str) -> int:
    if not db_path.exists():
        logger.info("%s migration skipped: %s does not exist yet", label, db_path)
        return 0
    conn = sqlite3.connect(str(db_path))
    try:
        applied = sum(1 for stmt in statements if _exec_idempotent(conn, stmt))
        conn.commit()
        if applied:
            logger.info("%s migration: %d/%d statements applied", label, applied, len(statements))
        return applied
    finally:
        conn.close()


def _backfill_employees(db_path: Path) -> int:
    """Backfill employees lineage without deleting existing seed/demo rows."""
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_lineage_columns(conn, "employees")
        real = lineage_values("real", "erp_csv", "ERP CSV sync")
        synthetic = lineage_values("synthetic", "seed", "Seed/demo employees")
        conn.execute(
            """UPDATE employees
                  SET source_system = 'erp_csv'
                WHERE is_synthetic = 0 AND source_system = 'erp'"""
        )
        conn.execute(
            """UPDATE employees
                  SET data_class = ?,
                      source_system = CASE
                          WHEN source_system IN ('', 'unknown', 'seed', 'erp') THEN ?
                          ELSE source_system
                      END,
                      source_label = CASE
                          WHEN source_label IS NULL OR source_label = '' THEN ?
                          ELSE source_label
                      END,
                      source_updated_at = CASE
                          WHEN source_updated_at IS NULL OR source_updated_at = '' THEN ?
                          ELSE source_updated_at
                      END
                WHERE is_synthetic = 0""",
            (
                real["data_class"],
                real["source_system"],
                real["source_label"],
                real["source_updated_at"],
            ),
        )
        conn.execute(
            """UPDATE employees
                  SET data_class = ?,
                      source_system = CASE
                          WHEN source_system IS NULL OR source_system = '' OR source_system = 'unknown'
                          THEN ?
                          ELSE source_system
                      END,
                      source_label = CASE
                          WHEN source_label IS NULL OR source_label = '' THEN ?
                          ELSE source_label
                      END,
                      source_updated_at = CASE
                          WHEN source_updated_at IS NULL OR source_updated_at = '' THEN ?
                          ELSE source_updated_at
                      END
                WHERE is_synthetic = 1
                   OR data_class IS NULL OR data_class = '' OR data_class = 'unknown'""",
            (
                synthetic["data_class"],
                synthetic["source_system"],
                synthetic["source_label"],
                synthetic["source_updated_at"],
            ),
        )
        conn.execute(
            """UPDATE employees
                  SET canonical_employee_id = employee_id
                WHERE data_class = 'real'
                  AND (canonical_employee_id IS NULL OR canonical_employee_id = '')"""
        )
        conn.commit()
        return int(conn.total_changes)
    finally:
        conn.close()


def _backfill_auth(db_path: Path) -> int:
    """Backfill auth users/login_history lineage for seed, bootstrap, and IdP rows."""
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_lineage_columns(conn, "users")
        has_login_history = table_exists(conn, "login_history")
        if has_login_history:
            ensure_lineage_columns(conn, "login_history")

        system = lineage_values("system", "bootstrap_admin", "Initial bootstrap admin")
        conn.execute(
            """UPDATE users
                  SET data_class = ?,
                      source_system = ?,
                      source_label = ?,
                      source_updated_at = ?
                WHERE employee_id = 'admin'""",
            (
                system["data_class"],
                system["source_system"],
                system["source_label"],
                system["source_updated_at"],
            ),
        )

        synthetic = lineage_values("synthetic", "seed_test_users", "Seed test users")
        placeholders = ",".join("?" for _ in SEED_TEST_EMPLOYEE_IDS)
        conn.execute(
            f"""UPDATE users
                   SET data_class = ?,
                       source_system = ?,
                       source_label = ?,
                       source_updated_at = ?
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
            for marker, source_system in (
                ("!LDAP!", "idp_ldap"),
                ("!OIDC!", "idp_oidc"),
                ("!SAML!", "idp_saml"),
            ):
                real = lineage_values("real", source_system, source_system)
                conn.execute(
                    """UPDATE users
                          SET data_class = ?,
                              source_system = ?,
                              source_label = ?,
                              source_updated_at = ?
                        WHERE password_hash = ?""",
                    (
                        real["data_class"],
                        real["source_system"],
                        real["source_label"],
                        real["source_updated_at"],
                        marker,
                    ),
                )

        if has_login_history:
            conn.execute(
                """UPDATE login_history
                      SET data_class = COALESCE(
                              (SELECT u.data_class FROM users u WHERE u.employee_id = login_history.employee_id),
                              data_class
                          ),
                          source_system = COALESCE(
                              (SELECT u.source_system FROM users u WHERE u.employee_id = login_history.employee_id),
                              source_system
                          ),
                          source_label = CASE
                              WHEN source_label IS NULL OR source_label = ''
                              THEN 'auth_login_history'
                              ELSE source_label
                          END,
                          source_updated_at = CASE
                              WHEN source_updated_at IS NULL OR source_updated_at = ''
                              THEN datetime('now')
                              ELSE source_updated_at
                          END
                    WHERE data_class IS NULL OR data_class = '' OR data_class = 'unknown'"""
            )
        conn.commit()
        return int(conn.total_changes)
    finally:
        conn.close()


def apply_employees() -> int:
    applied = _apply(EMPLOYEES_DB, EMPLOYEES_MIGRATIONS, "employees.db")
    _backfill_employees(EMPLOYEES_DB)
    return applied


def apply_auth() -> int:
    applied = _apply(AUTH_DB, AUTH_MIGRATIONS, "auth.db")
    _backfill_auth(AUTH_DB)
    return applied


def apply_audit() -> int:
    return _apply(AUDIT_DB, AUDIT_MIGRATIONS, "audit.db")


def apply_all() -> dict[str, int]:
    """Apply 0001 to all 3 DBs. Returns count per DB."""
    return {
        "employees": apply_employees(),
        "auth": apply_auth(),
        "audit": apply_audit(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = apply_all()
    for db, n in result.items():
        print(f"{db}: {n} statements applied")
