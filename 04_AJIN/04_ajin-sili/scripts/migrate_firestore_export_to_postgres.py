#!/usr/bin/env python3
"""Inspect or migrate Firestore JSON exports into Postgres.

이 스크립트는 Firebase Admin SDK에 직접 접속하지 않는다. 비용 차단 목적상
Firestore export 파일을 입력으로 받아 dry-run/count/checksum 리포트를 만들고,
지원되는 collection만 명시적으로 Postgres에 적재한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.db import create_sqlalchemy_engine, is_postgres_enabled  # noqa: E402

COLLECTION_TO_TABLE = {
    "users": "users",
    "audit_logs": "audit_logs",
    "employees": "employees",
    "draft_versions": "draft_versions",
    "chat_messages": "chat_messages",
    "attachments": "attachments",
}


def _read_json(path: Path) -> Any:
    """Read one JSON export file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten_export(raw: Any) -> dict[str, list[dict[str, Any]]]:
    """Normalize common Firestore JSON export shapes.

    Args:
        raw: Parsed JSON export.

    Returns:
        dict[str, list[dict[str, Any]]]: Collection name to document list.
    """
    if isinstance(raw, dict) and all(isinstance(v, list) for v in raw.values()):
        return {str(k): [dict(item) for item in v] for k, v in raw.items()}
    if isinstance(raw, list):
        collections: dict[str, list[dict[str, Any]]] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            collection = str(item.get("collection") or item.get("__collection__") or "unknown")
            payload = item.get("data") if isinstance(item.get("data"), dict) else item
            collections.setdefault(collection, []).append(dict(payload))
        return collections
    return {}


def inspect_export(path: Path) -> dict[str, Any]:
    """Build a dry-run report for one Firestore JSON export."""
    raw_bytes = path.read_bytes()
    collections = _flatten_export(json.loads(raw_bytes.decode("utf-8")))
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "collections": [
            {
                "name": name,
                "rows": len(rows),
                "target_table": COLLECTION_TO_TABLE.get(name),
                "supported": name in COLLECTION_TO_TABLE,
            }
            for name, rows in sorted(collections.items())
        ],
    }


def _target_columns(engine, table: str) -> set[str]:
    """Return target table column names."""
    inspector = sa.inspect(engine)
    if not inspector.has_table(table):
        return set()
    return {str(col["name"]) for col in inspector.get_columns(table)}


def apply_export(path: Path, limit: int | None) -> list[dict[str, Any]]:
    """Apply supported Firestore collections to Postgres."""
    if not is_postgres_enabled():
        raise RuntimeError("APP_DB_BACKEND=postgres is required for --apply")
    engine = create_sqlalchemy_engine()
    collections = _flatten_export(_read_json(path))
    applied: list[dict[str, Any]] = []
    for collection, rows in collections.items():
        table = COLLECTION_TO_TABLE.get(collection)
        if not table:
            continue
        target_cols = _target_columns(engine, table)
        if not target_cols:
            continue
        selected_rows = rows if limit is None else rows[:limit]
        normalized = [{k: v for k, v in row.items() if k in target_cols} for row in selected_rows]
        normalized = [row for row in normalized if row]
        if not normalized:
            continue
        metadata = sa.MetaData()
        target = sa.Table(table, metadata, autoload_with=engine)
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                conn.execute(pg_insert(target).values(normalized).on_conflict_do_nothing())
            else:
                conn.execute(target.insert(), normalized)
        applied.append({"collection": collection, "target_table": table, "rows": len(normalized)})
    return applied


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("export_json", type=Path)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report-json", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    """Run the Firestore export migration command."""
    args = parse_args()
    report = {"mode": "apply" if args.apply else "dry-run", "export": inspect_export(args.export_json)}
    if args.apply:
        report["applied"] = apply_export(args.export_json, args.limit)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
