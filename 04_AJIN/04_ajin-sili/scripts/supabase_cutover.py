#!/usr/bin/env python3
"""Run the AJIN Firebase-to-Supabase cutover sequence.

The command is intentionally fail-closed: dry-run is the default, secrets are
never printed, and remote mutations only run with ``--apply`` after all
required environment values are present.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_supabase_remote import DEFAULT_PROJECT_REF  # noqa: E402

REQUIRED_ENV = (
    "SUPABASE_PROJECT_REF",
    "SUPABASE_URL",
    "SUPABASE_ACCESS_TOKEN",
    "DATABASE_URL",
    "SUPABASE_SECRET_KEY",
    "APP_DB_BACKEND",
    "FIREBASE_WRITE_ENABLED",
    "FIREBASE_READ_FALLBACK_ENABLED",
)
OPTIONAL_ENV = (
    "SUPABASE_DB_PASSWORD",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_STORAGE_BUCKET_ATTACHMENTS",
    "SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS",
)
SECRET_ENV = (
    "SUPABASE_ACCESS_TOKEN",
    "SUPABASE_DB_PASSWORD",
    "DATABASE_URL",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
)
DEFAULT_ENV_FILES = (ROOT / ".env.supabase.local", ROOT / ".env")


@dataclass(frozen=True)
class EnvIssue:
    """Environment validation issue.

    Args:
        name: Environment variable or validation rule name.
        message: Human-readable failure message without secret values.
    """

    name: str
    message: str


def _truthy(value: str | None) -> bool:
    """Return whether an env-like value is truthy.

    Args:
        value: Raw environment value.

    Returns:
        bool: True for common deployment truthy values.
    """

    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_env_files(paths: Iterable[Path], *, override: bool = False) -> list[str]:
    """Load dotenv files into the current process.

    Args:
        paths: Candidate dotenv files.
        override: Whether file values should override existing environment.

    Returns:
        list[str]: Paths that existed and were loaded.
    """

    try:
        from dotenv import dotenv_values
    except ImportError as exc:  # pragma: no cover - dependency is in requirements
        raise RuntimeError("python-dotenv is required to load env files") from exc

    loaded: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        values = dotenv_values(path)
        for key, value in values.items():
            if value is None:
                continue
            if override or not os.getenv(key):
                os.environ[key] = str(value)
        loaded.append(str(path))
    return loaded


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    """Return paths in first-seen order without duplicates.

    Args:
        paths: Candidate paths that may repeat after defaults and CLI args merge.

    Returns:
        list[Path]: Resolved unique paths.
    """

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def key_state(raw_key: str | None) -> str:
    """Classify a Supabase key without exposing its value.

    Args:
        raw_key: Raw key value from environment.

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
    if raw_key.startswith("sbp_"):
        return "personal_access_token"
    return "present_unknown_prefix"


def validate_environment(project_ref: str) -> list[EnvIssue]:
    """Validate the cutover environment contract.

    Args:
        project_ref: Expected Supabase project ref.

    Returns:
        list[EnvIssue]: Failures that block remote cutover.
    """

    issues: list[EnvIssue] = []
    for name in REQUIRED_ENV:
        if not os.getenv(name):
            issues.append(EnvIssue(name, f"{name} is required"))

    expected_url = f"https://{project_ref}.supabase.co"
    configured_ref = os.getenv("SUPABASE_PROJECT_REF", "").strip()
    configured_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    if configured_ref and configured_ref != project_ref:
        issues.append(EnvIssue("SUPABASE_PROJECT_REF", "project ref does not match"))
    if configured_url and configured_url != expected_url:
        issues.append(
            EnvIssue("SUPABASE_URL", "SUPABASE_URL must match the project ref")
        )
    app_db_backend = os.getenv("APP_DB_BACKEND", "").strip().lower()
    if app_db_backend and app_db_backend != "postgres":
        issues.append(EnvIssue("APP_DB_BACKEND", "APP_DB_BACKEND must be postgres"))
    firebase_write = os.getenv("FIREBASE_WRITE_ENABLED")
    if firebase_write and _truthy(firebase_write):
        issues.append(
            EnvIssue("FIREBASE_WRITE_ENABLED", "Firebase writes must be disabled")
        )
    firebase_read = os.getenv("FIREBASE_READ_FALLBACK_ENABLED")
    if firebase_read and _truthy(firebase_read):
        issues.append(
            EnvIssue(
                "FIREBASE_READ_FALLBACK_ENABLED",
                "Firebase read fallback must be disabled",
            )
        )

    access_token_state = key_state(os.getenv("SUPABASE_ACCESS_TOKEN"))
    if access_token_state not in {"personal_access_token", "missing"}:
        issues.append(
            EnvIssue("SUPABASE_ACCESS_TOKEN", "token must use the sbp_ prefix")
        )

    secret_state = key_state(os.getenv("SUPABASE_SECRET_KEY"))
    if secret_state not in {"secret", "legacy_jwt", "missing"}:
        issues.append(
            EnvIssue(
                "SUPABASE_SECRET_KEY",
                "backend key must be sb_secret_ or legacy service_role",
            )
        )

    return issues


def redacted_env_status() -> dict[str, str]:
    """Return set/missing state for relevant cutover env vars.

    Returns:
        dict[str, str]: Safe environment status map.
    """

    names = (*REQUIRED_ENV, *OPTIONAL_ENV)
    return {name: "set" if os.getenv(name) else "missing" for name in names}


def _secret_fragments() -> list[str]:
    """Collect secret fragments to redact from command output.

    Returns:
        list[str]: Non-empty local secret values.
    """

    values = [os.getenv(name, "") for name in SECRET_ENV]
    return [value for value in values if len(value) >= 4]


def redact_text(text: str) -> str:
    """Redact known local secret values from command output.

    Args:
        text: Raw command output.

    Returns:
        str: Redacted text.
    """

    redacted = text
    for fragment in _secret_fragments():
        redacted = redacted.replace(fragment, "<redacted>")
    database_url = os.getenv("DATABASE_URL", "")
    if database_url:
        try:
            password = urlsplit(database_url).password
        except ValueError:
            password = None
        if password:
            redacted = redacted.replace(password, "<redacted>")
    return redacted


def run_command(
    args: list[str],
    *,
    label: str,
    env: dict[str, str] | None = None,
    cwd: Path = ROOT,
) -> None:
    """Run a subprocess and fail with redacted diagnostics.

    Args:
        args: Command argv.
        label: Safe operation label printed before execution.
        env: Optional process environment.
        cwd: Working directory.

    Raises:
        RuntimeError: If the command exits non-zero.
    """

    print(f"[cutover] {label}")
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = redact_text(completed.stdout or "")
    if output.strip():
        print(output.rstrip())
    if completed.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}")


def _bucket_to_dict(bucket: Any) -> dict[str, Any]:
    """Normalize Supabase Storage bucket response shapes.

    Args:
        bucket: Bucket value from supabase-py.

    Returns:
        dict[str, Any]: Normalized bucket data.
    """

    if isinstance(bucket, dict):
        return dict(bucket)
    if hasattr(bucket, "model_dump"):
        return dict(bucket.model_dump())
    if hasattr(bucket, "dict"):
        return dict(bucket.dict())
    data: dict[str, Any] = {}
    for attr in ("id", "name", "public"):
        if hasattr(bucket, attr):
            data[attr] = getattr(bucket, attr)
    return data


def ensure_private_bucket(storage_client: Any, bucket_id: str) -> str:
    """Create or update one Supabase Storage bucket as private.

    Args:
        storage_client: ``client.storage`` object from supabase-py.
        bucket_id: Required bucket id.

    Returns:
        str: Action summary: ``created``, ``updated_private``, or ``already_private``.

    Raises:
        RuntimeError: If bucket creation/update fails in supabase-py.
    """

    buckets = [_bucket_to_dict(bucket) for bucket in storage_client.list_buckets()]
    current = next(
        (
            bucket
            for bucket in buckets
            if str(bucket.get("id") or bucket.get("name") or "") == bucket_id
        ),
        None,
    )
    options = {"public": False}
    if current is None:
        storage_client.create_bucket(bucket_id, options=options)
        return "created"
    if bool(current.get("public")):
        storage_client.update_bucket(bucket_id, options)
        return "updated_private"
    return "already_private"


def ensure_storage_buckets() -> dict[str, str]:
    """Ensure required Supabase Storage buckets exist and are private.

    Returns:
        dict[str, str]: Bucket id to action summary.

    Raises:
        RuntimeError: If Supabase settings or client calls fail.
    """

    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    client = create_client(url, key)
    storage_client = client.storage
    buckets = (
        os.getenv("SUPABASE_STORAGE_BUCKET_ATTACHMENTS", "ajin-attachments"),
        os.getenv("SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS", "ajin-draft-exports"),
    )
    return {
        bucket_id: ensure_private_bucket(storage_client, bucket_id)
        for bucket_id in buckets
    }


def run_cutover(args: argparse.Namespace) -> int:
    """Run preflight or remote cutover.

    Args:
        args: Parsed CLI arguments.

    Returns:
        int: Process exit code.
    """

    env_files = [] if args.no_default_env else list(DEFAULT_ENV_FILES)
    env_files.extend(Path(path) for path in args.env_file)
    env_files = unique_paths(env_files)
    loaded = load_env_files(env_files, override=args.override_env)
    project_ref = (
        args.project_ref or os.getenv("SUPABASE_PROJECT_REF") or DEFAULT_PROJECT_REF
    )
    os.environ.setdefault("SUPABASE_PROJECT_REF", project_ref)

    issues = validate_environment(project_ref)
    report = {
        "mode": "apply" if args.apply else "dry-run",
        "loaded_env_files": loaded,
        "project_ref": project_ref,
        "expected_url": f"https://{project_ref}.supabase.co",
        "env": redacted_env_status(),
        "issues": [issue.__dict__ for issue in issues],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if issues:
        print(
            "[cutover] blocked: fix the environment issues above before remote execution"
        )
        return 2
    if not args.apply:
        print("[cutover] dry-run complete; rerun with --apply to mutate Supabase")
        return 0

    process_env = os.environ.copy()
    process_env["APP_DB_BACKEND"] = "postgres"
    process_env["FIREBASE_WRITE_ENABLED"] = "false"
    process_env["FIREBASE_READ_FALLBACK_ENABLED"] = "false"

    if not args.skip_login:
        run_command(
            ["supabase", "login", "--token", os.environ["SUPABASE_ACCESS_TOKEN"]],
            label="Supabase CLI login",
            env=process_env,
        )
    if not args.skip_link:
        link_args = ["supabase", "link", "--project-ref", project_ref]
        if os.getenv("SUPABASE_DB_PASSWORD"):
            link_args.extend(["--password", os.environ["SUPABASE_DB_PASSWORD"]])
        run_command(link_args, label="Supabase CLI project link", env=process_env)
        run_command(
            ["supabase", "projects", "list", "-o", "json"],
            label="Supabase project list",
            env=process_env,
        )
    if not args.skip_migration:
        run_command(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            label="Alembic upgrade",
            env=process_env,
        )
        run_command(
            [sys.executable, "-m", "alembic", "current"],
            label="Alembic current",
            env=process_env,
        )
    if not args.skip_buckets:
        print("[cutover] Ensure Supabase Storage buckets are private")
        bucket_actions = ensure_storage_buckets()
        print(json.dumps(bucket_actions, ensure_ascii=False, indent=2))
    if not args.skip_verify:
        today_report = (
            ROOT / "outputs" / "supabase-verification" / "cutover-remote-check.md"
        )
        run_command(
            [
                sys.executable,
                "scripts/verify_supabase_remote.py",
                "--strict",
                "--project-ref",
                project_ref,
                "--markdown",
                str(today_report),
            ],
            label="Strict Supabase remote verifier",
            env=process_env,
        )
        run_command(
            ["supabase", "db", "push", "--dry-run", "--linked"],
            label="Supabase CLI db push dry-run",
            env=process_env,
        )
        run_command(
            [
                "supabase",
                "db",
                "advisors",
                "--linked",
                "--type",
                "security",
                "--level",
                "warn",
            ],
            label="Supabase security advisors",
            env=process_env,
        )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: Optional argv for tests.

    Returns:
        argparse.Namespace: Parsed arguments.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Run remote mutations")
    parser.add_argument(
        "--project-ref", default="", help="Expected Supabase project ref"
    )
    parser.add_argument(
        "--env-file", action="append", default=[], help="Dotenv file to load"
    )
    parser.add_argument(
        "--no-default-env", action="store_true", help="Do not load default env files"
    )
    parser.add_argument(
        "--override-env",
        action="store_true",
        help="Let dotenv files override process env",
    )
    parser.add_argument("--skip-login", action="store_true")
    parser.add_argument("--skip-link", action="store_true")
    parser.add_argument("--skip-migration", action="store_true")
    parser.add_argument("--skip-buckets", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argv for tests.

    Returns:
        int: Process exit code.
    """

    try:
        return run_cutover(parse_args(argv))
    except Exception as exc:  # noqa: BLE001
        print(f"[cutover] failed: {redact_text(str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
