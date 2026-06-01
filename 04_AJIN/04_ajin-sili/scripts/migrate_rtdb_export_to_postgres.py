#!/usr/bin/env python3
"""Migrate Firebase RTDB JSON exports to Postgres event tables.

지원 범위는 RTDB `live_alarms`/`feedback` export를 Postgres `live_alarms`와
`feedback_events`로 옮기는 것이다. 기본값은 dry-run이다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.db import create_sqlalchemy_engine, is_postgres_enabled  # noqa: E402


def _now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _load(path: Path) -> Any:
    """Load one RTDB export JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _values(node: Any) -> list[dict[str, Any]]:
    """Return dict child values from a list or mapping."""
    if isinstance(node, list):
        return [item for item in node if isinstance(item, dict)]
    if isinstance(node, dict):
        return [dict(value, id=str(key)) if isinstance(value, dict) else {"id": str(key), "value": value} for key, value in node.items()]
    return []


def extract_live_alarms(raw: Any) -> list[dict[str, Any]]:
    """Extract live alarm rows from an RTDB export object."""
    if isinstance(raw, dict) and "live_alarms" in raw:
        root = raw["live_alarms"]
    elif isinstance(raw, dict) and any(
        isinstance(value, dict) and ("severity" in value or value.get("type") == "spc_violation")
        for value in raw.values()
    ):
        root = raw
    else:
        root = []
    out: list[dict[str, Any]] = []
    for item in _values(root):
        alarm_id = str(item.get("id") or f"alarm-{uuid.uuid4().hex[:12]}")
        created_at = item.get("detected_at") or item.get("created_at") or _now().isoformat()
        out.append(
            {
                "id": alarm_id,
                "domain": str(item.get("domain") or "equipment"),
                "severity": str(item.get("severity") or "info"),
                "message": str(item.get("message") or item.get("description") or "live alarm"),
                "payload": item,
                "created_at": created_at,
                "data_class": "real",
                "source_system": str(item.get("source") or "rtdb_export"),
                "source_label": "rtdb_export",
                "source_updated_at": created_at,
            }
        )
    return out


def extract_feedback(raw: Any) -> list[dict[str, Any]]:
    """Extract feedback rows from an RTDB export object."""
    root = raw.get("feedback", {}) if isinstance(raw, dict) else {}
    rows: list[dict[str, Any]] = []
    if not isinstance(root, dict):
        return rows
    for message_id, events in root.items():
        for event in _values(events):
            rows.append(
                {
                    "id": str(event.get("id") or f"feedback-{uuid.uuid4().hex[:12]}"),
                    "message_id": str(message_id)[:120],
                    "employee_id": str(event.get("user_id") or event.get("employee_id") or "anonymous"),
                    "rating": str(event.get("rating") or ""),
                    "created_at": _now(),
                    "data_class": "real",
                    "source_system": "rtdb_export",
                    "source_label": "rtdb_export",
                    "source_updated_at": _now(),
                }
            )
    return [row for row in rows if row["rating"] in {"thumbs_up", "thumbs_down"}]


def inspect_export(path: Path) -> dict[str, Any]:
    """Build a dry-run report for one RTDB export."""
    raw_bytes = path.read_bytes()
    raw = json.loads(raw_bytes.decode("utf-8"))
    alarms = extract_live_alarms(raw)
    feedback = extract_feedback(raw)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "live_alarms": len(alarms),
        "feedback_events": len(feedback),
    }


def _insert_rows(engine, table_name: str, rows: list[dict[str, Any]]) -> int:
    """Insert rows with conflict-do-nothing semantics."""
    if not rows:
        return 0
    metadata = sa.MetaData()
    table = sa.Table(table_name, metadata, autoload_with=engine)
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            conn.execute(pg_insert(table).values(rows).on_conflict_do_nothing())
        else:
            conn.execute(table.insert(), rows)
    return len(rows)


def apply_export(path: Path, limit: int | None) -> dict[str, int]:
    """Apply RTDB alarm and feedback rows to Postgres."""
    if not is_postgres_enabled():
        raise RuntimeError("APP_DB_BACKEND=postgres is required for --apply")
    raw = _load(path)
    alarms = extract_live_alarms(raw)
    feedback = extract_feedback(raw)
    if limit is not None:
        alarms = alarms[:limit]
        feedback = feedback[:limit]
    engine = create_sqlalchemy_engine()
    return {
        "live_alarms": _insert_rows(engine, "live_alarms", alarms),
        "feedback_events": _insert_rows(engine, "feedback_events", feedback),
    }


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
    """Run the RTDB export migration command."""
    args = parse_args()
    report = {"mode": "apply" if args.apply else "dry-run", "export": inspect_export(args.export_json)}
    if args.apply:
        report["applied"] = apply_export(args.export_json, args.limit)
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
