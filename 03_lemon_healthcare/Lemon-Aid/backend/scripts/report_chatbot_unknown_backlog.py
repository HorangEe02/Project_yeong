"""Report privacy-safe chatbot unknown knowledge backlog groups."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
AI_AGENT_SRC = BACKEND_ROOT / "ai_agent_chat" / "src"

sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))
sys.path.insert(0, str(AI_AGENT_SRC))
sys.path.insert(0, str(BACKEND_ROOT))

from src.services.chatbot_unknown_backlog_report import (  # noqa: E402
    list_unknown_knowledge_backlog_groups,
    unknown_backlog_report_payload,
)


def main() -> int:
    args = _parse_args()
    _load_env_file(args.env_file)
    database_url = args.database_url or os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: set DATABASE_URL or TEST_DATABASE_URL, or pass --database-url.", file=sys.stderr
        )
        return 2

    database_url = _normalize_database_url(database_url)
    payload = asyncio.run(_load_report(args=args, database_url=database_url))
    rendered = (
        _markdown_report(payload)
        if args.format == "markdown"
        else json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote chatbot unknown backlog report to {args.output}")
        return 0
    if args.format == "markdown":
        print(rendered)
    else:
        print(rendered)
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=BACKEND_ROOT / ".env",
        help="Path to a dotenv file containing DATABASE_URL. Defaults to backend/.env.",
    )
    parser.add_argument("--status", default="open", choices=("open", "reviewed", "dismissed"))
    parser.add_argument(
        "--row-limit",
        type=int,
        default=None,
        help="Limit raw backlog rows before aggregation. Omit to include all matching rows.",
    )
    parser.add_argument(
        "--group-limit",
        type=int,
        default=None,
        help="Limit aggregated groups. Omit to report every missing knowledge group.",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="Write the rendered report to this file.")
    return parser.parse_args(argv)


async def _load_report(*, args: argparse.Namespace, database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url)
    try:
        async with AsyncSession(engine) as session:
            groups = await list_unknown_knowledge_backlog_groups(
                session,
                status=args.status,
                row_limit=args.row_limit,
                group_limit=args.group_limit,
            )
    finally:
        await engine.dispose()
    return unknown_backlog_report_payload(groups)


def _normalize_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if normalized.startswith("postgresql://"):
        normalized = "postgresql+asyncpg://" + normalized[len("postgresql://") :]
    return normalized.replace("sslmode=require", "ssl=require")


def _load_env_file(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Chatbot Unknown Knowledge Backlog",
        "",
        f"- total_groups: {payload['total_groups']}",
        f"- total_events: {payload['total_events']}",
        "",
        "| count | status | category | missing_topic | needed_evidence_type | retrieval_status |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for group in payload["groups"]:
        lines.append(
            "| {count} | {status} | {category} | {missing_topic} | {needed_evidence_type} | {retrieval_status} |".format(
                count=group["count"],
                status=group["status"],
                category=group["category"],
                missing_topic=group["missing_topic"],
                needed_evidence_type=group["needed_evidence_type"],
                retrieval_status=group["retrieval_status"],
            )
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
