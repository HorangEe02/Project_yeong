#!/usr/bin/env python3
"""Migrate supported SQLite tables into the application Postgres database.

기본값은 destructive 하지 않은 dry-run/count/report이다. `--apply`는
DATABASE_URL이 설정된 Postgres 대상에 대해 지원 테이블만 복사한다.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.db import create_sqlalchemy_engine, is_postgres_enabled  # noqa: E402

SUPPORTED_TABLES = {
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
}

DEFAULT_SQLITE_DBS = [
    ROOT / "data" / "ajin_app.db",
    ROOT / "data" / "auth.db",
    ROOT / "data" / "employees.db",
    ROOT / "data" / "compliance.db",
    ROOT / "data" / "notifications.db",
    ROOT / "data" / "spc_violations.db",
]


def _sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    """Return user table names from a SQLite connection."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Return SQLite table column names."""
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def scan_sqlite_db(path: Path) -> dict[str, Any]:
    """Scan one SQLite database without mutating it.

    Args:
        path: SQLite database path.

    Returns:
        dict[str, Any]: Table counts and supported-migration flags.
    """
    if not path.exists():
        return {"path": str(path), "exists": False, "tables": []}
    conn = sqlite3.connect(str(path))
    try:
        tables = []
        for table in _sqlite_tables(conn):
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            tables.append(
                {
                    "name": table,
                    "rows": int(count),
                    "columns": _columns(conn, table),
                    "supported": table in SUPPORTED_TABLES or table == "spc_violations",
                }
            )
        return {"path": str(path), "exists": True, "tables": tables}
    finally:
        conn.close()


def _postgres_columns(engine, table: str) -> set[str]:
    """Return target Postgres table columns."""
    inspector = sa.inspect(engine)
    if not inspector.has_table(table):
        return set()
    return {str(col["name"]) for col in inspector.get_columns(table)}


def _copy_table(
    *,
    source_conn: sqlite3.Connection,
    engine,
    source_table: str,
    target_table: str,
    limit: int | None,
) -> int:
    """Copy rows from one supported SQLite table into Postgres.

    Args:
        source_conn: SQLite connection.
        engine: SQLAlchemy target engine.
        source_table: Source table name.
        target_table: Target table name.
        limit: Optional row limit.

    Returns:
        int: Inserted or upserted row count.
    """
    if source_table == "spc_violations" and target_table == "plc_violations":
        query = "SELECT * FROM spc_violations"
        if limit:
            query += f" LIMIT {int(limit)}"
        source_conn.row_factory = sqlite3.Row
        source_rows = [dict(row) for row in source_conn.execute(query).fetchall()]
        rows = [
            {
                "id": row["id"],
                "process_id": row.get("process", ""),
                "rule_number": int(row.get("rule_number") or 0),
                "severity": row.get("severity", "info"),
                "message": row.get("rule_name") or row.get("recommended_action") or "SPC violation",
                "payload": row,
                "created_at": row.get("detected_at"),
                "data_class": row.get("data_class", "real"),
                "source_system": row.get("source_system", "plc_ingest"),
                "source_label": row.get("source_label", "plc_ingest"),
                "source_updated_at": row.get("source_updated_at") or row.get("detected_at"),
            }
            for row in source_rows
        ]
        if not rows:
            return 0
        metadata = sa.MetaData()
        target = sa.Table(target_table, metadata, autoload_with=engine)
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = pg_insert(target).values(rows)
                stmt = stmt.on_conflict_do_nothing()
                conn.execute(stmt)
            else:
                conn.execute(target.insert(), rows)
        return len(rows)

    target_cols = _postgres_columns(engine, target_table)
    if not target_cols:
        return 0
    source_cols = _columns(source_conn, source_table)
    common = [col for col in source_cols if col in target_cols]
    if not common:
        return 0
    query = f"SELECT {', '.join(common)} FROM {source_table}"
    if limit:
        query += f" LIMIT {int(limit)}"
    source_conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in source_conn.execute(query).fetchall()]
    if not rows:
        return 0

    metadata = sa.MetaData()
    target = sa.Table(target_table, metadata, autoload_with=engine)
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(target).values(rows)
            stmt = stmt.on_conflict_do_nothing()
            conn.execute(stmt)
        else:
            conn.execute(target.insert(), rows)
    return len(rows)


def apply_migration(paths: list[Path], limit: int | None) -> dict[str, Any]:
    """Apply supported SQLite table copies into Postgres."""
    if not is_postgres_enabled():
        raise RuntimeError("APP_DB_BACKEND=postgres is required for --apply")
    engine = create_sqlalchemy_engine()
    applied: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        conn = sqlite3.connect(str(path))
        try:
            for table in _sqlite_tables(conn):
                target = "plc_violations" if table == "spc_violations" else table
                if table not in SUPPORTED_TABLES and table != "spc_violations":
                    continue
                copied = _copy_table(
                    source_conn=conn,
                    engine=engine,
                    source_table=table,
                    target_table=target,
                    limit=limit,
                )
                applied.append({"source_db": str(path), "source_table": table, "target_table": target, "rows": copied})
        finally:
            conn.close()
    return {"applied": applied}


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Only inspect source SQLite DBs")
    mode.add_argument("--apply", action="store_true", help="Copy supported rows into Postgres")
    parser.add_argument("--sqlite-db", action="append", default=[], help="SQLite DB path; repeatable")
    parser.add_argument("--limit", type=int, default=None, help="Optional per-table row limit")
    parser.add_argument("--report-json", type=Path, default=None, help="Write JSON report to this path")
    return parser.parse_args()


def main() -> int:
    """Run the SQLite to Postgres migration command."""
    args = parse_args()
    paths = [Path(p).expanduser().resolve() for p in args.sqlite_db] or DEFAULT_SQLITE_DBS
    report = {
        "mode": "apply" if args.apply else "dry-run",
        "sources": [scan_sqlite_db(path) for path in paths],
    }
    if args.apply:
        report.update(apply_migration(paths, args.limit))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
