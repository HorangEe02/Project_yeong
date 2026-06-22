"""Split a redacted Naver Tampermonkey OCR manifest into resumable batches.

This utility does not run OCR. It preserves collector-compatible manifest rows
while writing small JSONL batches that can be evaluated independently with
``run_naver_tampermonkey_ocr_eval.py --resume``. The summary intentionally
stores counts and artifact names only, never raw OCR text, provider payloads,
request headers, image bytes, raw model responses, secrets, or local paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "naver-tampermonkey-manifest-batches-v1"
DEFAULT_BATCH_SIZE = 8
DEFAULT_BATCH_PREFIX = "manifest-batch"
SAFE_FILENAME_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
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
        "service_key",
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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed CLI arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--batch-prefix", default=DEFAULT_BATCH_PREFIX)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output-dir>/manifest-batches.summary.json.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing batch JSONL and summary files.",
    )
    return parser.parse_args()


def main() -> None:
    """Split the manifest and write a redacted summary."""
    args = parse_args()
    manifest_path = args.manifest.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_dir / "manifest-batches.summary.json"
    )
    try:
        batches, summary = split_manifest_batches(
            manifest_path=manifest_path,
            output_dir=output_dir,
            batch_size=args.batch_size,
            batch_prefix=args.batch_prefix,
        )
        _write_batches(
            batches=batches,
            summary=summary,
            output_dir=output_dir,
            summary_path=summary_path,
            overwrite=args.overwrite,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            manifest_path=manifest_path,
            output_dir=output_dir,
            error=exc,
        )
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def split_manifest_batches(
    *,
    manifest_path: Path,
    output_dir: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    batch_prefix: str = DEFAULT_BATCH_PREFIX,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return resumable manifest batch payloads and a redacted summary.

    Args:
        manifest_path: Source JSONL or JSON manifest path.
        output_dir: Planned output directory used for redacted summary metadata.
        batch_size: Maximum rows per batch.
        batch_prefix: Safe file-name prefix for generated batch manifests.

    Returns:
        Batch payloads and redacted summary.

    Raises:
        ValueError: If inputs are unsafe or malformed.
    """
    safe_prefix = _safe_filename_token(batch_prefix, field_name="batch_prefix")
    if batch_size < 1:
        raise ValueError("batch_size must be positive.")
    rows = _read_manifest_rows(manifest_path)
    batches: list[dict[str, object]] = []
    batch_summaries: list[dict[str, object]] = []
    for batch_index, start in enumerate(range(0, len(rows), batch_size), 1):
        batch_rows = rows[start : start + batch_size]
        batch_name = f"{safe_prefix}-{batch_index:03d}.jsonl"
        batches.append({"name": batch_name, "rows": batch_rows})
        batch_summaries.append(
            {
                "name": batch_name,
                "row_count": len(batch_rows),
                "row_index_start": start,
                "row_index_end": start + len(batch_rows) - 1,
                "section_counts": _field_counts(batch_rows, "section"),
                "category_key_counts": _category_key_counts(batch_rows),
            }
        )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_name": manifest_path.name,
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_path_hash": _sha256_text(str(output_dir.expanduser())),
        "batch_prefix": safe_prefix,
        "batch_size": batch_size,
        "input_row_count": len(rows),
        "batch_count": len(batches),
        "section_counts": _field_counts(rows, "section"),
        "category_key_counts": _category_key_counts(rows),
        "batches": batch_summaries,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload({"batches": batches, "summary": summary})
    return batches, summary


def _write_batches(
    *,
    batches: list[dict[str, object]],
    summary: dict[str, object],
    output_dir: Path,
    summary_path: Path,
    overwrite: bool,
) -> None:
    """Write batch JSONL files and a redacted summary.

    Args:
        batches: Batch payloads returned by ``split_manifest_batches``.
        summary: Redacted summary payload.
        output_dir: Destination directory.
        summary_path: Destination summary path.
        overwrite: Whether existing files may be replaced.

    Raises:
        FileExistsError: If a destination exists and overwrite is disabled.
        OSError: If filesystem operations fail.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    for batch in batches:
        name = str(batch["name"])
        path = output_dir / name
        if path.exists() and not overwrite:
            raise FileExistsError("Batch manifest already exists.")
        rows = batch["rows"]
        if not isinstance(rows, list):
            raise ValueError("Batch rows must be a list.")
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    if summary_path.exists() and not overwrite:
        raise FileExistsError("Batch summary already exists.")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_manifest_rows(path: Path) -> list[dict[str, object]]:
    """Read JSONL or JSON manifest rows.

    Args:
        path: Manifest path.

    Returns:
        Manifest row objects.

    Raises:
        ValueError: If rows are malformed or unsafe.
    """
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, object]]
    if path.suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    else:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("cases"), list):
            rows = [item for item in parsed["cases"] if isinstance(item, dict)]
        elif isinstance(parsed, list):
            rows = [item for item in parsed if isinstance(item, dict)]
        else:
            raise ValueError("Manifest must be JSONL, a JSON list, or an object with cases.")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Manifest rows must be objects.")
        _reject_unsafe_payload(row)
    return rows


def _field_counts(rows: list[dict[str, object]], field_name: str) -> dict[str, int]:
    """Return counts for a top-level string field.

    Args:
        rows: Manifest rows.
        field_name: Field to count.

    Returns:
        Sorted count mapping.
    """
    counts: Counter[str] = Counter()
    for row in rows:
        value = row.get(field_name)
        counts[str(value) if isinstance(value, str) and value else "unknown"] += 1
    return dict(sorted(counts.items()))


def _category_key_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    """Return counts for DB labeling category keys.

    Args:
        rows: Manifest rows.

    Returns:
        Sorted category-key count mapping.
    """
    counts: Counter[str] = Counter()
    for row in rows:
        db_labeling = row.get("db_labeling")
        category_key = None
        if isinstance(db_labeling, dict):
            raw_key = db_labeling.get("category_key")
            if isinstance(raw_key, str) and raw_key:
                category_key = raw_key
        counts[category_key or "unknown"] += 1
    return dict(sorted(counts.items()))


def _safe_filename_token(value: str, *, field_name: str) -> str:
    """Return a safe filename token.

    Args:
        value: Candidate token.
        field_name: Field name used in errors.

    Returns:
        Safe token.

    Raises:
        ValueError: If the token is unsafe.
    """
    token = value.strip()
    if not SAFE_FILENAME_TOKEN_PATTERN.fullmatch(token):
        raise ValueError(f"{field_name} must be a bounded filename token.")
    return token


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys and local path literals recursively.

    Args:
        value: JSON-like payload.

    Raises:
        ValueError: If unsafe keys or local paths are found.
    """
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested in value.values():
            _reject_unsafe_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


def _failure_summary(
    *,
    manifest_path: Path,
    output_dir: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary.

    Args:
        manifest_path: Source manifest path.
        output_dir: Planned output directory.
        error: Failure exception.

    Returns:
        Public-safe failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "manifest_name": manifest_path.name,
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_path_hash": _sha256_text(str(output_dir.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "input_row_count": 0,
        "batch_count": 0,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded public error code.

    Args:
        exc: Failure exception.

    Returns:
        Error code.
    """
    if isinstance(exc, OSError):
        return "local_file_operation_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a public error message without local filesystem details.

    Args:
        exc: Failure exception.

    Returns:
        Bounded public error message.
    """
    if isinstance(exc, OSError):
        message = "Local file operation failed."
    elif isinstance(exc, json.JSONDecodeError):
        message = "JSON decode failed."
    else:
        message = str(exc).strip()
    if (
        not message
        or any(marker in message for marker in LOCAL_PATH_MARKERS)
        or "/" in message
        or "\\" in message
    ):
        return "Validation failed."
    return message[:200]


def _sha256_text(value: str) -> str:
    """Return SHA-256 for text.

    Args:
        value: Text value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
