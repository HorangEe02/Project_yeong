"""Check OCR evaluation artifacts for raw text, secrets, and local paths.

This script is a local/CI gate for generated OCR artifacts. It parses JSON and
JSONL files structurally, scans Markdown reports textually, rejects forbidden
raw payload keys, and scans bounded string values for local filesystem literals.
It does not upload files, open a database connection, call OCR providers, or
call LLM services.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "ocr-artifact-privacy-check-v1"
DEFAULT_EXTENSIONS = (".json", ".jsonl", ".md")
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "ocr_text",
        "provider_payload",
        "raw_image",
        "raw_model_response",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "secret",
        "service_key",
    }
)
LITERAL_FORBIDDEN_KEYS = frozenset(
    {
        "absolute_path",
        "image_path",
        "local_path",
        "product_dir",
    }
)
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
MARKDOWN_FORBIDDEN_TOKENS = tuple(sorted(RAW_FORBIDDEN_KEYS - {"secret"}))
MARKDOWN_FORBIDDEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])("
    + "|".join(re.escape(key) for key in MARKDOWN_FORBIDDEN_TOKENS)
    + r")(?![A-Za-z0-9_])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PrivacyFinding:
    """One privacy finding in an artifact."""

    path: str
    location: str
    reason: str


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for artifact privacy checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        action="append",
        required=True,
        help="Artifact file or directory to scan. May be repeated.",
    )
    parser.add_argument(
        "--extension",
        action="append",
        choices=DEFAULT_EXTENSIONS,
        help="File extension to scan. Defaults to JSON, JSONL, and Markdown.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Skip missing paths instead of failing.",
    )
    parser.add_argument(
        "--strict-literal-keys",
        action="store_true",
        help="Also reject image_path/product_dir-style keys used only by source manifests.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the privacy check and print a JSON summary."""
    args = parse_args()
    paths = [path.expanduser().resolve() for path in args.path]
    try:
        summary = check_artifact_privacy(
            paths=paths,
            extensions=tuple(args.extension or DEFAULT_EXTENSIONS),
            allow_missing=args.allow_missing,
            strict_literal_keys=args.strict_literal_keys,
        )
    except (OSError, ValueError) as exc:
        summary = _failure_summary(
            paths=paths,
            extensions=tuple(args.extension or DEFAULT_EXTENSIONS),
            allow_missing=args.allow_missing,
            strict_literal_keys=args.strict_literal_keys,
            error=exc,
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if summary["finding_count"] or summary.get("status") == "error":
        raise SystemExit(1)


def check_artifact_privacy(
    *,
    paths: list[Path],
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    allow_missing: bool = False,
    strict_literal_keys: bool = False,
) -> dict[str, object]:
    """Return a privacy-check summary for OCR artifacts.

    Args:
        paths: Files or directories to scan.
        extensions: File extensions to include.
        allow_missing: Whether missing paths are skipped.
        strict_literal_keys: Whether source-manifest path keys are rejected even
            when their values are tokenized.

    Returns:
        JSON-serializable summary with finding counts and finding details.

    Raises:
        FileNotFoundError: If a requested path is missing and ``allow_missing``
            is false.
        ValueError: If unsupported file extensions are requested.
    """
    normalized_extensions = _normalize_extensions(extensions)
    files = _collect_files(
        paths=paths,
        extensions=normalized_extensions,
        allow_missing=allow_missing,
    )
    findings: list[PrivacyFinding] = []
    json_value_count = 0
    for path in files:
        file_findings, values_seen = _scan_file(
            path,
            strict_literal_keys=strict_literal_keys,
        )
        findings.extend(file_findings)
        json_value_count += values_seen

    return {
        "schema_version": SCHEMA_VERSION,
        "path_names": [path.name for path in paths],
        "path_hashes": [_sha256_text(str(path.expanduser())) for path in paths],
        "extensions": list(normalized_extensions),
        "strict_literal_keys": strict_literal_keys,
        "file_count": len(files),
        "json_value_count": json_value_count,
        "finding_count": len(findings),
        "passed": not findings,
        "findings": [
            {"path": item.path, "location": item.location, "reason": item.reason}
            for item in findings
        ],
        "db_write_performed": False,
        "external_transfer_performed": False,
    }


def _collect_files(
    *,
    paths: list[Path],
    extensions: tuple[str, ...],
    allow_missing: bool,
) -> list[Path]:
    """Return files matching the configured extensions."""
    files: list[Path] = []
    for path in paths:
        if not path.exists():
            if allow_missing:
                continue
            raise FileNotFoundError("Artifact path is missing.")
        if path.is_file():
            if path.suffix in extensions:
                files.append(path)
            continue
        files.extend(
            file for file in sorted(path.rglob("*")) if file.is_file() and file.suffix in extensions
        )
    return sorted(set(files))


def _scan_file(path: Path, *, strict_literal_keys: bool) -> tuple[list[PrivacyFinding], int]:
    """Scan one JSON, JSONL, or Markdown artifact."""
    findings: list[PrivacyFinding] = []
    values_seen = 0
    if path.suffix == ".md":
        return _scan_markdown_file(path)
    if path.suffix == ".jsonl":
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                findings.append(
                    PrivacyFinding(
                        path=path.name,
                        location=f"line:{line_number}",
                        reason=f"invalid_jsonl:{exc.msg}",
                    )
                )
                continue
            values_seen += _scan_value(
                value,
                findings=findings,
                path=path,
                location=f"line:{line_number}",
                strict_literal_keys=strict_literal_keys,
            )
        return findings, values_seen

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [PrivacyFinding(path=path.name, location="$", reason=f"invalid_json:{exc.msg}")], 0
    values_seen += _scan_value(
        value,
        findings=findings,
        path=path,
        location="$",
        strict_literal_keys=strict_literal_keys,
    )
    return findings, values_seen


def _scan_markdown_file(path: Path) -> tuple[list[PrivacyFinding], int]:
    """Scan one Markdown report for raw-key tokens and local path literals."""
    findings: list[PrivacyFinding] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        if any(marker in line for marker in LOCAL_PATH_MARKERS):
            findings.append(
                PrivacyFinding(
                    path=path.name,
                    location=f"line:{line_number}",
                    reason="local_path_literal",
                )
            )
        for match in MARKDOWN_FORBIDDEN_PATTERN.finditer(line):
            findings.append(
                PrivacyFinding(
                    path=path.name,
                    location=f"line:{line_number}",
                    reason=f"forbidden_raw_token:{match.group(1).lower()}",
                )
            )
    return findings, len(lines)


def _scan_value(
    value: Any,
    *,
    findings: list[PrivacyFinding],
    path: Path,
    location: str,
    strict_literal_keys: bool,
) -> int:
    """Scan a decoded JSON value recursively and return visited value count."""
    count = 1
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            nested_location = f"{location}.{key_text}"
            if key_lower in RAW_FORBIDDEN_KEYS:
                findings.append(
                    PrivacyFinding(
                        path=path.name,
                        location=nested_location,
                        reason=f"forbidden_raw_key:{key_text}",
                    )
                )
            if strict_literal_keys and key_lower in LITERAL_FORBIDDEN_KEYS:
                findings.append(
                    PrivacyFinding(
                        path=path.name,
                        location=nested_location,
                        reason=f"forbidden_literal_key:{key_text}",
                    )
                )
            count += _scan_value(
                nested,
                findings=findings,
                path=path,
                location=nested_location,
                strict_literal_keys=strict_literal_keys,
            )
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            count += _scan_value(
                nested,
                findings=findings,
                path=path,
                location=f"{location}[{index}]",
                strict_literal_keys=strict_literal_keys,
            )
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        findings.append(
            PrivacyFinding(
                path=path.name,
                location=location,
                reason="local_path_literal",
            )
        )
    return count


def _normalize_extensions(values: tuple[str, ...]) -> tuple[str, ...]:
    """Return supported extensions with leading dots."""
    normalized = tuple(value if value.startswith(".") else f".{value}" for value in values)
    unsupported = sorted(set(normalized) - set(DEFAULT_EXTENSIONS))
    if unsupported:
        raise ValueError(f"Unsupported extension(s): {unsupported}")
    return normalized


def _failure_summary(
    *,
    paths: list[Path],
    extensions: tuple[str, ...],
    allow_missing: bool,
    strict_literal_keys: bool,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted privacy-check failure summary."""
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "path_names": [path.name for path in paths],
        "path_hashes": [_sha256_text(str(path.expanduser())) for path in paths],
        "extensions": list(extensions),
        "allow_missing": allow_missing,
        "strict_literal_keys": strict_literal_keys,
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "file_count": 0,
        "json_value_count": 0,
        "finding_count": 0,
        "passed": False,
        "findings": [],
        "db_write_performed": False,
        "external_transfer_performed": False,
    }


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for a UTF-8 text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded non-sensitive CLI error code."""
    if isinstance(exc, OSError):
        return "local_file_operation_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message without filesystem details."""
    message = "Local file operation failed." if isinstance(exc, OSError) else str(exc).strip()
    if (
        not message
        or any(marker in message for marker in LOCAL_PATH_MARKERS)
        or "/" in message
        or "\\" in message
    ):
        return "Validation failed."
    return message[:200]


if __name__ == "__main__":
    main()
