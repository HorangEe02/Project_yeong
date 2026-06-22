"""Export retry manifests from Tampermonkey OCR failure review rows.

This script converts a redacted failure review queue back into collector-
compatible manifest rows by joining each failure row with the original batch
manifest row. It is used to rerun only selected failures, such as
``ocr_low_confidence`` rows with alternate OCR settings or
``ollama_structured_output`` rows with a parser retry. It does not persist raw
OCR text, provider payloads, request headers, image bytes, raw model responses,
secrets, or local paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

SCHEMA_VERSION = "naver-tampermonkey-ocr-retry-manifest-v1"
SUMMARY_SCHEMA_VERSION = "naver-tampermonkey-ocr-retry-manifest-summary-v1"
EXPECTED_REVIEW_SCHEMA_VERSION = "naver-tampermonkey-ocr-failure-review-v1"
DEFAULT_MANIFEST_NAME = "ocr-retry-manifest.jsonl"
DEFAULT_SUMMARY_NAME = "ocr-retry-manifest.summary.json"
FailureKind = Literal["all", "ocr_error", "llm_parse_error"]
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
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


def main() -> None:
    """Export a retry manifest and redacted summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--failure-review", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest-name", default=DEFAULT_MANIFEST_NAME)
    parser.add_argument("--summary-name", default=DEFAULT_SUMMARY_NAME)
    parser.add_argument(
        "--failure-kind",
        choices=("all", "ocr_error", "llm_parse_error"),
        default="all",
    )
    parser.add_argument(
        "--suggested-next-action",
        action="append",
        default=(),
        help="Optional bounded action filter. Can be provided multiple times.",
    )
    args = parser.parse_args()

    try:
        rows, summary = export_retry_manifest(
            batch_dir=args.batch_dir.expanduser().resolve(),
            failure_review_path=args.failure_review.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            manifest_name=args.manifest_name,
            summary_name=args.summary_name,
            failure_kind=args.failure_kind,
            suggested_next_actions=tuple(args.suggested_next_action or ()),
        )
        _write_outputs(
            rows=rows,
            summary=summary,
            output_dir=args.output_dir.expanduser().resolve(),
            manifest_name=args.manifest_name,
            summary_name=args.summary_name,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            batch_dir=args.batch_dir,
            failure_review_path=args.failure_review,
            output_dir=args.output_dir,
            error=exc,
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def export_retry_manifest(
    *,
    batch_dir: Path,
    failure_review_path: Path,
    output_dir: Path,
    manifest_name: str = DEFAULT_MANIFEST_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
    failure_kind: FailureKind = "all",
    suggested_next_actions: tuple[str, ...] = (),
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build collector-compatible retry rows from failure review rows.

    Args:
        batch_dir: Directory containing original redacted batch manifests.
        failure_review_path: Redacted failure review JSONL path.
        output_dir: Planned output directory.
        manifest_name: Retry manifest filename.
        summary_name: Summary filename.
        failure_kind: Failure kind filter.
        suggested_next_actions: Optional suggested action filter.

    Returns:
        Retry rows and summary.

    Raises:
        ValueError: If input rows are malformed or unsafe.
    """
    safe_manifest_name = _safe_filename(manifest_name, suffix=".jsonl", field_name="manifest_name")
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    action_filter = tuple(_safe_token(action) for action in suggested_next_actions)
    manifest_rows = _load_batch_rows(batch_dir)
    review_rows = _read_jsonl(failure_review_path)
    retry_rows: list[dict[str, object]] = []
    skipped_missing_fixture_count = 0

    for review_row in review_rows:
        _validate_review_row(review_row)
        if not _review_row_matches(
            review_row,
            failure_kind=failure_kind,
            suggested_next_actions=action_filter,
        ):
            continue
        fixture_id = _safe_token(str(review_row["fixture_id"]))
        source_row = manifest_rows.get(fixture_id)
        if source_row is None:
            skipped_missing_fixture_count += 1
            continue
        retry_row = _retry_row_from_source(
            source_row=source_row,
            review_row=review_row,
        )
        retry_rows.append(retry_row)

    summary = _build_summary(
        rows=retry_rows,
        batch_dir=batch_dir,
        failure_review_path=failure_review_path,
        output_dir=output_dir,
        manifest_name=safe_manifest_name,
        summary_name=safe_summary_name,
        failure_kind=failure_kind,
        suggested_next_actions=action_filter,
        input_review_row_count=len(review_rows),
        skipped_missing_fixture_count=skipped_missing_fixture_count,
    )
    _reject_unsafe_payload({"rows": retry_rows, "summary": summary})
    return retry_rows, summary


def _load_batch_rows(batch_dir: Path) -> dict[str, dict[str, object]]:
    """Load original batch manifest rows keyed by fixture id."""
    rows: dict[str, dict[str, object]] = {}
    for manifest_path in sorted(batch_dir.glob("*.jsonl")):
        for row in _read_jsonl(manifest_path):
            fixture_id = row.get("fixture_id")
            if not isinstance(fixture_id, str) or not fixture_id:
                continue
            rows[_safe_token(fixture_id)] = row
    return rows


def _validate_review_row(row: dict[str, object]) -> None:
    """Validate a failure review row envelope."""
    if row.get("schema_version") != EXPECTED_REVIEW_SCHEMA_VERSION:
        raise ValueError("Failure review rows must use the expected schema version.")
    if row.get("requires_human_review") is not True:
        raise ValueError("Failure review rows must require human review.")
    _safe_token(str(row.get("review_task_id") or ""))
    _safe_token(str(row.get("fixture_id") or ""))
    failure_kind = row.get("failure_kind")
    if failure_kind not in {"ocr_error", "llm_parse_error"}:
        raise ValueError("Failure review row has unsupported failure_kind.")
    _reject_unsafe_payload(row)


def _review_row_matches(
    row: dict[str, object],
    *,
    failure_kind: FailureKind,
    suggested_next_actions: tuple[str, ...],
) -> bool:
    """Return whether a failure row should be exported for retry."""
    if failure_kind != "all" and row.get("failure_kind") != failure_kind:
        return False
    return not suggested_next_actions or row.get("suggested_next_action") in suggested_next_actions


def _retry_row_from_source(
    *,
    source_row: dict[str, object],
    review_row: dict[str, object],
) -> dict[str, object]:
    """Return one collector-compatible retry row with bounded metadata."""
    _reject_unsafe_payload(source_row)
    retry_row = json.loads(json.dumps(source_row, ensure_ascii=False))
    if not isinstance(retry_row, dict):
        raise ValueError("Source manifest row must be an object.")
    retry_row["retry_metadata"] = {
        "schema_version": SCHEMA_VERSION,
        "source_review_task_id": _safe_token(str(review_row["review_task_id"])),
        "failure_kind": _safe_token(str(review_row["failure_kind"])),
        "source_error_code": _safe_optional_token(review_row.get("error_code")),
        "source_llm_parse_error_code": _safe_optional_token(review_row.get("llm_parse_error_code")),
        "suggested_next_action": _safe_token(str(review_row["suggested_next_action"])),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(retry_row)
    return retry_row


def _build_summary(
    *,
    rows: list[dict[str, object]],
    batch_dir: Path,
    failure_review_path: Path,
    output_dir: Path,
    manifest_name: str,
    summary_name: str,
    failure_kind: FailureKind,
    suggested_next_actions: tuple[str, ...],
    input_review_row_count: int,
    skipped_missing_fixture_count: int,
) -> dict[str, object]:
    """Build a redacted retry manifest summary."""
    failure_kind_counts = Counter()
    action_counts = Counter()
    category_key_counts = Counter()
    for row in rows:
        retry_metadata = row.get("retry_metadata")
        if isinstance(retry_metadata, dict):
            failure_kind_counts[str(retry_metadata.get("failure_kind") or "unknown")] += 1
            action_counts[str(retry_metadata.get("suggested_next_action") or "unknown")] += 1
        db_labeling = row.get("db_labeling")
        category_key = "unknown"
        if isinstance(db_labeling, dict) and isinstance(db_labeling.get("category_key"), str):
            category_key = db_labeling["category_key"]
        category_key_counts[category_key] += 1
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_name": manifest_name,
        "summary_name": summary_name,
        "batch_dir_name": batch_dir.name,
        "batch_dir_path_hash": _sha256_text(str(batch_dir.expanduser())),
        "failure_review_name": failure_review_path.name,
        "failure_review_path_hash": _sha256_text(str(failure_review_path.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_path_hash": _sha256_text(str(output_dir.expanduser())),
        "failure_kind_filter": failure_kind,
        "suggested_next_action_filters": list(suggested_next_actions),
        "input_review_row_count": input_review_row_count,
        "retry_row_count": len(rows),
        "skipped_missing_fixture_count": skipped_missing_fixture_count,
        "failure_kind_counts": dict(sorted(failure_kind_counts.items())),
        "suggested_next_action_counts": dict(sorted(action_counts.items())),
        "category_key_counts": dict(sorted(category_key_counts.items())),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _write_outputs(
    *,
    rows: list[dict[str, object]],
    summary: dict[str, object],
    output_dir: Path,
    manifest_name: str,
    summary_name: str,
) -> None:
    """Write retry manifest JSONL and summary JSON."""
    safe_manifest_name = _safe_filename(manifest_name, suffix=".jsonl", field_name="manifest_name")
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / safe_manifest_name).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (output_dir / safe_summary_name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL object rows and reject unsafe content."""
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL rows must be objects.")
        _reject_unsafe_payload(row)
        rows.append(row)
    return rows


def _safe_optional_token(value: object) -> str | None:
    """Return a safe token or None."""
    if not isinstance(value, str) or not value:
        return None
    return _safe_token(value)


def _safe_token(value: str) -> str:
    """Return a bounded public-safe token."""
    token = value.strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(token) or any(
        marker in token for marker in LOCAL_PATH_MARKERS
    ):
        raise ValueError("Unsafe token.")
    return token


def _safe_filename(value: str, *, suffix: str, field_name: str) -> str:
    """Return a safe output filename with the required suffix."""
    token = value.strip()
    if not token.endswith(suffix):
        raise ValueError(f"{field_name} has an unexpected suffix.")
    stem = token[: -len(suffix)]
    _safe_token(stem)
    return token


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys and local path literals recursively."""
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
    batch_dir: Path,
    failure_review_path: Path,
    output_dir: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary."""
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "batch_dir_name": batch_dir.name,
        "batch_dir_path_hash": _sha256_text(str(batch_dir.expanduser())),
        "failure_review_name": failure_review_path.name,
        "failure_review_path_hash": _sha256_text(str(failure_review_path.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_path_hash": _sha256_text(str(output_dir.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded public error code."""
    if isinstance(exc, OSError):
        return "local_file_operation_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message."""
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
    """Return SHA-256 for text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
