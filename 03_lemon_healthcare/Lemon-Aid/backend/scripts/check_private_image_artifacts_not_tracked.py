"""Check private supplement image artifacts are not tracked by Git.

The supplement learning pipeline may materialize local contact sheets or review
images for operator decisions, but source/review/detail-page images must not be
committed. This gate uses ``git ls-files`` so local untracked working files can
exist while tracked private image files fail the check.

References:
    https://git-scm.com/docs/git-ls-files
    https://docs.python.org/3/library/subprocess.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "private-image-tracking-check-v1"
DEFAULT_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
MAX_TRACKED_IMAGE_HASHES = 50
SOURCE_DOC_URLS = (
    "https://git-scm.com/docs/git-ls-files",
    "https://docs.python.org/3/library/subprocess.html",
)


class PrivateImageTrackingError(ValueError):
    """Raised when the private-image tracking check cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional test argument list.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--path", type=Path, action="append", required=True)
    parser.add_argument(
        "--image-extension",
        action="append",
        help="Private image extension to reject when tracked. Defaults to jpg/jpeg/png/webp.",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run the tracking check and print a JSON summary.

    Args:
        argv: Optional test argument list.
    """
    args = parse_args(argv)
    image_extensions = tuple(args.image_extension or DEFAULT_IMAGE_EXTENSIONS)
    try:
        report = build_private_image_tracking_report(
            repo_root=args.repo_root.expanduser().resolve(),
            paths=[path.expanduser().resolve() for path in args.path],
            image_extensions=image_extensions,
        )
        if args.output is not None:
            output_path = args.output.expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        print(json.dumps(_cli_summary(report), ensure_ascii=False, sort_keys=True))
    except (OSError, PrivateImageTrackingError, subprocess.SubprocessError) as exc:
        report = _failure_summary(
            repo_root=args.repo_root.expanduser().resolve(),
            paths=[path.expanduser().resolve() for path in args.path],
            image_extensions=image_extensions,
            error=exc,
        )
        if args.output is not None:
            output_path = args.output.expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        print(json.dumps(_cli_summary(report), ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None
    if report["tracked_private_image_count"]:
        raise SystemExit(1)


def build_private_image_tracking_report(
    *,
    repo_root: Path,
    paths: list[Path],
    image_extensions: tuple[str, ...] = DEFAULT_IMAGE_EXTENSIONS,
    tracked_files: list[str] | None = None,
) -> dict[str, Any]:
    """Build a redacted report of tracked private image artifacts.

    Args:
        repo_root: Git repository root.
        paths: Repository-contained paths to inspect.
        image_extensions: Image suffixes that must not be tracked.
        tracked_files: Optional test override for tracked repo-relative paths.

    Returns:
        JSON-serializable tracking report.

    Raises:
        PrivateImageTrackingError: If inputs are outside the repository or git
            output contains unsafe path values.
    """
    normalized_extensions = _normalize_extensions(image_extensions)
    repo_root = repo_root.expanduser().resolve()
    protected_paths = [
        _repo_relative_path(repo_root=repo_root, path=path.expanduser().resolve()) for path in paths
    ]
    if tracked_files is None:
        tracked_files = _git_tracked_files(repo_root=repo_root, protected_paths=protected_paths)
    tracked_image_files = [
        item
        for item in tracked_files
        if Path(item).suffix.lower() in normalized_extensions
        and _is_under_any_path(item, protected_paths)
    ]
    for tracked_file in tracked_image_files:
        _reject_unsafe_path_literal(tracked_file)

    extension_counts = Counter(Path(item).suffix.lower() for item in tracked_image_files)
    report = {
        "schema_version": SCHEMA_VERSION,
        "passed": not tracked_image_files,
        "repo_root_name": repo_root.name,
        "repo_root_hash": _sha256_text(str(repo_root)),
        "path_names": [path.name for path in paths],
        "path_hashes": [_sha256_text(str(path.expanduser().resolve())) for path in paths],
        "protected_path_count": len(protected_paths),
        "image_extensions": list(normalized_extensions),
        "tracked_private_image_count": len(tracked_image_files),
        "tracked_private_image_extension_counts": dict(sorted(extension_counts.items())),
        "tracked_private_image_path_hashes": [
            _sha256_text(item)[:24] for item in tracked_image_files[:MAX_TRACKED_IMAGE_HASHES]
        ],
        "tracked_private_image_hashes_truncated": len(tracked_image_files)
        > MAX_TRACKED_IMAGE_HASHES,
        "git_ls_files_checked": True,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(report)
    return report


def _git_tracked_files(*, repo_root: Path, protected_paths: list[str]) -> list[str]:
    """Return tracked paths under the protected paths.

    Args:
        repo_root: Git repository root.
        protected_paths: Repo-relative pathspecs.

    Returns:
        Repo-relative tracked file paths.
    """
    command = ["git", "-C", str(repo_root), "ls-files", "--", *protected_paths]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _repo_relative_path(*, repo_root: Path, path: Path) -> str:
    """Return a Git pathspec relative to the repository root.

    Args:
        repo_root: Git repository root.
        path: Absolute path to protect.

    Returns:
        POSIX-style repo-relative pathspec.

    Raises:
        PrivateImageTrackingError: If ``path`` is outside ``repo_root``.
    """
    try:
        relative = path.relative_to(repo_root)
    except ValueError as exc:
        raise PrivateImageTrackingError("Protected path is outside the repository.") from exc
    return "." if str(relative) == "." else relative.as_posix()


def _is_under_any_path(repo_relative_file: str, protected_paths: list[str]) -> bool:
    """Return whether a tracked file belongs to any protected pathspec.

    Args:
        repo_relative_file: Repo-relative tracked file path.
        protected_paths: Repo-relative protected pathspecs.

    Returns:
        True when the file is under a protected path.
    """
    for protected_path in protected_paths:
        if protected_path == ".":
            return True
        if repo_relative_file == protected_path or repo_relative_file.startswith(
            protected_path.rstrip("/") + "/"
        ):
            return True
    return False


def _normalize_extensions(values: tuple[str, ...]) -> tuple[str, ...]:
    """Return normalized image suffixes.

    Args:
        values: Candidate suffixes.

    Returns:
        Lowercase suffixes that start with a dot.

    Raises:
        PrivateImageTrackingError: If no suffixes are supplied.
    """
    normalized = tuple(
        sorted(
            {value.lower() if value.startswith(".") else f".{value.lower()}" for value in values}
        )
    )
    if not normalized:
        raise PrivateImageTrackingError("At least one image extension is required.")
    return normalized


def _reject_unsafe_payload(value: Any) -> None:
    """Reject local path literals in a report payload.

    Args:
        value: Report payload.

    Raises:
        PrivateImageTrackingError: If the payload contains a local path literal.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in ("/Users/", "/Volumes/", "/private/", "file://"):
        if marker in serialized:
            raise PrivateImageTrackingError("Report contains a local path literal.")


def _reject_unsafe_path_literal(value: str) -> None:
    """Reject tracked path values that would leak local absolute paths.

    Args:
        value: Repo-relative Git path.

    Raises:
        PrivateImageTrackingError: If ``value`` is an absolute/local path.
    """
    for marker in ("/Users/", "/Volumes/", "/private/", "file://"):
        if marker in value:
            raise PrivateImageTrackingError("Git tracked path contains a local path literal.")


def _sha256_text(value: str) -> str:
    """Return a SHA-256 hash for a string.

    Args:
        value: Input string.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cli_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Return a short CLI summary.

    Args:
        report: Full report.

    Returns:
        Bounded summary for terminal output.
    """
    return {
        "schema_version": report.get("schema_version"),
        "passed": report.get("passed") is True,
        "tracked_private_image_count": report.get("tracked_private_image_count", 0),
        "protected_path_count": report.get("protected_path_count", 0),
    }


def _failure_summary(
    *,
    repo_root: Path,
    paths: list[Path],
    image_extensions: tuple[str, ...],
    error: BaseException,
) -> dict[str, Any]:
    """Return a redacted failure report.

    Args:
        repo_root: Git repository root.
        paths: Protected paths.
        image_extensions: Image suffixes that were requested.
        error: Failure exception.

    Returns:
        JSON-serializable failure report.
    """
    report = {
        "schema_version": SCHEMA_VERSION,
        "passed": False,
        "status": "error",
        "repo_root_name": repo_root.name,
        "repo_root_hash": _sha256_text(str(repo_root)),
        "path_names": [path.name for path in paths],
        "path_hashes": [_sha256_text(str(path)) for path in paths],
        "image_extensions": list(_normalize_extensions(image_extensions)),
        "tracked_private_image_count": 0,
        "error_type": type(error).__name__,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(report)
    return report


if __name__ == "__main__":
    main()
