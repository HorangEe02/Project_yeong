"""Check AI Agent integration worktree for secret and generated artifacts.

The script reports file paths only. It never reads or prints .env contents.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path


ALLOWED_ENV_FILES = {"backend/.env.example"}
LOCAL_ONLY_FILES = {
    "backend/Nutrition-backend/config/kdca_healthinfo_topics.local.json",
}
SECRET_PARTS = {"api-key", "credentials", "secrets"}
SECRET_FILE_NAMES = {"google-services.json", "GoogleService-Info.plist"}
SECRET_SUFFIXES = {".crt", ".jks", ".key", ".keystore", ".p12", ".p8", ".pem"}
GENERATED_PARTS = {
    ".dart_tool",
    ".local",
    ".pytest_cache",
    "__pycache__",
    "build",
    "coverage",
    "htmlcov",
    "logs",
    "tmp",
    "temp",
}
GENERATED_FILE_NAMES = {
    ".coverage",
    ".flutter-plugins",
    ".flutter-plugins-dependencies",
}
GENERATED_SUFFIXES = {".err", ".log", ".out", ".pyc", ".pyo"}


def run_git(args: list[str], cwd: Path) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
        raise SystemExit(result.returncode)
    return result.stdout


def zsplit(output: bytes) -> list[str]:
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in output.split(b"\0")
        if item
    ]


def normalize(path: str) -> str:
    return path.replace("\\", "/")


def is_env_file(path: str) -> bool:
    normalized = normalize(path)
    if normalized in ALLOWED_ENV_FILES:
        return False

    name = normalized.rsplit("/", 1)[-1]
    if name == ".env" or name.startswith(".env."):
        return True

    return "/.env/" in f"/{normalized}/"


def is_secret_file(path: str) -> bool:
    normalized = normalize(path)
    if normalized in LOCAL_ONLY_FILES:
        return True

    parts = set(normalized.split("/"))
    name = normalized.rsplit("/", 1)[-1]
    suffix = Path(name).suffix.lower()

    return (
        bool(parts & SECRET_PARTS)
        or name in SECRET_FILE_NAMES
        or name.startswith("service-account")
        or suffix in SECRET_SUFFIXES
    )


def is_generated_artifact(path: str) -> bool:
    normalized = normalize(path)
    parts = set(normalized.split("/"))
    name = normalized.rsplit("/", 1)[-1]
    suffix = Path(name).suffix.lower()

    return (
        bool(parts & GENERATED_PARTS)
        or name in GENERATED_FILE_NAMES
        or suffix in GENERATED_SUFFIXES
    )


def classify(path: str) -> str | None:
    if is_env_file(path) or is_secret_file(path):
        return "env-or-secret"
    if is_generated_artifact(path):
        return "generated-artifact"
    return None


def collect_tracked(root: Path) -> list[tuple[str, str]]:
    paths = zsplit(run_git(["ls-files", "-z"], root))
    return [(path, kind) for path in paths if (kind := classify(path))]


def collect_unignored_generated(root: Path) -> list[tuple[str, str]]:
    paths = zsplit(run_git(["ls-files", "--others", "--exclude-standard", "-z"], root))
    return [(path, kind) for path in paths if (kind := classify(path))]


def collect_ignored_summary(root: Path) -> Counter[str]:
    entries = zsplit(
        run_git(["status", "--ignored", "--short", "--untracked-files=all", "-z"], root)
    )
    counts: Counter[str] = Counter()
    for entry in entries:
        if not entry.startswith("!! "):
            continue
        path = entry[3:]
        kind = classify(path) or "other-ignored"
        counts[kind] += 1
    return counts


def print_violations(title: str, violations: list[tuple[str, str]]) -> None:
    if not violations:
        return
    print(title)
    for path, kind in violations:
        print(f"  - [{kind}] {normalize(path)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify that AI Agent integration PRs do not include local secrets or generated artifacts."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root or any path inside the repository.",
    )
    args = parser.parse_args(argv)

    start = Path(args.root).resolve()
    root = Path(
        run_git(["rev-parse", "--show-toplevel"], start)
        .decode("utf-8", errors="replace")
        .strip()
    )

    tracked = collect_tracked(root)
    unignored = collect_unignored_generated(root)
    ignored_summary = collect_ignored_summary(root)

    print(f"Repository: {root}")
    print("Allowed env docs: backend/.env.example")
    print("Ignored summary:")
    if ignored_summary:
        for kind, count in sorted(ignored_summary.items()):
            print(f"  - {kind}: {count}")
    else:
        print("  - none")

    print_violations("Tracked violations:", tracked)
    print_violations("Unignored generated or env-like files:", unignored)

    if tracked or unignored:
        return 1

    print("Preflight passed: no tracked or unignored secret/generated artifacts found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
