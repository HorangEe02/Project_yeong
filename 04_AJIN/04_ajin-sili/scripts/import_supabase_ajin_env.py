#!/usr/bin/env python3
"""Create the local Supabase cutover dotenv from the AJIN handoff note.

The source note can contain raw database credentials. This command writes only
to the gitignored `.env.supabase.local` file, preserves already-entered manual
tokens, and reports only set/missing state.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT.parent / "Brand-New-update" / "supabase-ajin.md"
DEFAULT_OUTPUT = ROOT / ".env.supabase.local"
DEFAULT_PROJECT_REF = "ycjuzwltwbeudanjykag"
ATTACHMENTS_BUCKET = "ajin-attachments"
DRAFT_EXPORTS_BUCKET = "ajin-draft-exports"

SUPABASE_URL_RE = re.compile(r"https://(?P<ref>[a-z0-9]{20})\.supabase\.co")
PUBLISHABLE_KEY_RE = re.compile(r"\bsb_publishable_[A-Za-z0-9_-]+\b")
DATABASE_URL_RE = re.compile(r"\bpostgresql://[^\s`]+")
PASSWORD_RE = re.compile(r"(?im)\bsupabase\s+pw\s*:\s*(?P<value>.+?)\s*$")


@dataclass(frozen=True)
class SupabaseAjinConfig:
    """Parsed Supabase connection values from the handoff note.

    Args:
        project_ref: Supabase project reference.
        supabase_url: Hosted Supabase project URL.
        publishable_key: Browser-safe Supabase publishable key.
        database_url: Postgres connection string for the remote project.
        db_password: Database password extracted from the note or URL.
    """

    project_ref: str
    supabase_url: str
    publishable_key: str
    database_url: str
    db_password: str


def _field_after_label(text: str, label: str) -> str:
    """Return the first non-empty line after a simple markdown label.

    Args:
        text: Raw note contents.
        label: Lowercase field label such as `host` or `database`.

    Returns:
        str: Field value, or an empty string when the label is absent.
    """

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower().rstrip(":") != label:
            continue
        for candidate in lines[index + 1 :]:
            value = candidate.strip()
            if value:
                return value
    return ""


def _password_from_url(database_url: str) -> str:
    """Extract the password component from a database URL.

    Args:
        database_url: Raw Postgres connection string.

    Returns:
        str: Password value, or an empty string when it cannot be parsed.
    """

    try:
        return urlsplit(database_url).password or ""
    except ValueError:
        return ""


def _build_database_url(text: str, db_password: str) -> str:
    """Build a Postgres URL from labeled fields when no URL is present.

    Args:
        text: Raw note contents.
        db_password: Database password to percent-encode in the URL.

    Returns:
        str: Constructed Postgres URL, or an empty string if fields are missing.
    """

    host = _field_after_label(text, "host")
    port = _field_after_label(text, "port") or "5432"
    database = _field_after_label(text, "database") or "postgres"
    user = _field_after_label(text, "user")
    if not host or not user or not db_password:
        return ""
    safe_user = quote(user, safe="")
    safe_password = quote(db_password, safe="")
    return f"postgresql://{safe_user}:{safe_password}@{host}:{port}/{database}"


def parse_supabase_ajin(text: str) -> SupabaseAjinConfig:
    """Parse the AJIN Supabase handoff note.

    Args:
        text: Raw markdown note contents.

    Returns:
        SupabaseAjinConfig: Parsed, validated connection values.

    Raises:
        ValueError: If required values are missing or the project ref is wrong.
    """

    url_match = SUPABASE_URL_RE.search(text)
    publishable_match = PUBLISHABLE_KEY_RE.search(text)
    database_match = DATABASE_URL_RE.search(text)
    password_match = PASSWORD_RE.search(text)

    if not url_match:
        raise ValueError("SUPABASE_URL was not found in the handoff note")
    project_ref = url_match.group("ref")
    if project_ref != DEFAULT_PROJECT_REF:
        raise ValueError("Supabase project ref does not match AJIN target")
    if not publishable_match:
        raise ValueError("SUPABASE_PUBLISHABLE_KEY was not found")

    raw_database_url = database_match.group(0) if database_match else ""
    db_password = _password_from_url(raw_database_url)
    if not db_password and password_match:
        db_password = password_match.group("value").strip()
    database_url = raw_database_url or _build_database_url(text, db_password)
    if not database_url:
        raise ValueError("DATABASE_URL could not be derived")
    if not db_password:
        raise ValueError("SUPABASE_DB_PASSWORD could not be derived")

    return SupabaseAjinConfig(
        project_ref=project_ref,
        supabase_url=f"https://{project_ref}.supabase.co",
        publishable_key=publishable_match.group(0),
        database_url=database_url,
        db_password=db_password,
    )


def load_dotenv(path: Path) -> dict[str, str]:
    """Load a dotenv file without expanding or printing values.

    Args:
        path: Dotenv path.

    Returns:
        dict[str, str]: Parsed key/value pairs.
    """

    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_env_values(
    config: SupabaseAjinConfig,
    *,
    existing: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the cutover dotenv values.

    Args:
        config: Parsed Supabase handoff config.
        existing: Existing dotenv values to preserve for manual secrets.

    Returns:
        dict[str, str]: Complete cutover dotenv values.
    """

    existing = existing or {}
    return {
        "SUPABASE_PROJECT_REF": config.project_ref,
        "SUPABASE_URL": config.supabase_url,
        "SUPABASE_ACCESS_TOKEN": existing.get("SUPABASE_ACCESS_TOKEN", ""),
        "SUPABASE_DB_PASSWORD": config.db_password,
        "DATABASE_URL": config.database_url,
        "SUPABASE_SECRET_KEY": existing.get("SUPABASE_SECRET_KEY", ""),
        "SUPABASE_PUBLISHABLE_KEY": config.publishable_key,
        "APP_DB_BACKEND": "postgres",
        "FIREBASE_WRITE_ENABLED": "false",
        "FIREBASE_READ_FALLBACK_ENABLED": "false",
        "SUPABASE_STORAGE_BUCKET_ATTACHMENTS": ATTACHMENTS_BUCKET,
        "SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS": DRAFT_EXPORTS_BUCKET,
        "ENABLE_SUPABASE_REALTIME": "false",
    }


def render_dotenv(values: dict[str, str]) -> str:
    """Render dotenv content in the AJIN cutover order.

    Args:
        values: Environment values returned by `build_env_values`.

    Returns:
        str: Dotenv file content.
    """

    groups = (
        (
            "# Generated from ../Brand-New-update/supabase-ajin.md.",
            "SUPABASE_PROJECT_REF",
            "SUPABASE_URL",
            "SUPABASE_ACCESS_TOKEN",
        ),
        (
            "# Supabase Postgres connection.",
            "SUPABASE_DB_PASSWORD",
            "DATABASE_URL",
        ),
        (
            "# Backend-only Storage/Data API keys.",
            "SUPABASE_SECRET_KEY",
            "SUPABASE_PUBLISHABLE_KEY",
        ),
        (
            "# AJIN runtime cutover posture.",
            "APP_DB_BACKEND",
            "FIREBASE_WRITE_ENABLED",
            "FIREBASE_READ_FALLBACK_ENABLED",
            "SUPABASE_STORAGE_BUCKET_ATTACHMENTS",
            "SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS",
            "ENABLE_SUPABASE_REALTIME",
        ),
    )
    lines = [
        "# AJIN Firebase -> Supabase remote cutover env.",
        "# Do not commit this file. Rotate credentials if this file is exposed.",
        "",
    ]
    for group in groups:
        lines.append(group[0])
        lines.extend(f"{key}={values.get(key, '')}" for key in group[1:])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_dotenv(path: Path, content: str) -> None:
    """Write a dotenv file with owner-only permissions.

    Args:
        path: Output dotenv path.
        content: Dotenv content.
    """

    path.write_text(content, encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def safe_status(values: dict[str, str]) -> dict[str, str]:
    """Return set/missing status without leaking secret values.

    Args:
        values: Environment values to summarize.

    Returns:
        dict[str, str]: Safe status by key.
    """

    return {key: "set" if value else "missing" for key, value in values.items()}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argv for tests.

    Returns:
        argparse.Namespace: Parsed arguments.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        default=str(DEFAULT_SOURCE),
        help="Path to Brand-New-update/supabase-ajin.md",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output dotenv path",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Parse and report status without writing the dotenv file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argv for tests.

    Returns:
        int: Process exit code.
    """

    args = parse_args(argv)
    source = Path(args.source).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    config = parse_supabase_ajin(source.read_text(encoding="utf-8"))
    existing = load_dotenv(output)
    values = build_env_values(config, existing=existing)
    if not args.check:
        write_dotenv(output, render_dotenv(values))
    print(
        json.dumps(
            {
                "mode": "check" if args.check else "write",
                "source": str(source),
                "output": str(output),
                "status": safe_status(values),
                "manual_values_required": [
                    key
                    for key in ("SUPABASE_ACCESS_TOKEN", "SUPABASE_SECRET_KEY")
                    if not values.get(key)
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
