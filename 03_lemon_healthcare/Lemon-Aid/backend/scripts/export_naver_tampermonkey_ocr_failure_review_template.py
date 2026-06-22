"""Export a redacted review queue for Tampermonkey OCR/LLM failures.

The exporter joins batch manifests with batch OCR observation outputs and emits
only failure metadata needed for operator triage. It never stores raw OCR text,
provider payloads, request headers, image bytes, raw model responses, secrets,
or local paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "naver-tampermonkey-ocr-failure-review-v1"
SUMMARY_SCHEMA_VERSION = "naver-tampermonkey-ocr-failure-review-summary-v1"
DEFAULT_REVIEW_NAME = "ocr-failure-review-template.jsonl"
DEFAULT_SUMMARY_NAME = "ocr-failure-review-template.summary.json"
OBSERVATION_RELATIVE_PATH = Path("paddleocr-observations") / "supplement-ocr-observations.jsonl"
REPORT_NAME = "naver-ocr-provider-comparison.json"
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
    """Export failure review rows and a redacted summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--runner-output-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--review-name", default=DEFAULT_REVIEW_NAME)
    parser.add_argument("--summary-name", default=DEFAULT_SUMMARY_NAME)
    args = parser.parse_args()

    try:
        rows, summary = export_failure_review_template(
            batch_dir=args.batch_dir.expanduser().resolve(),
            runner_output_root=args.runner_output_root.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            review_name=args.review_name,
            summary_name=args.summary_name,
        )
        _write_outputs(
            rows=rows,
            summary=summary,
            output_dir=args.output_dir.expanduser().resolve(),
            review_name=args.review_name,
            summary_name=args.summary_name,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            batch_dir=args.batch_dir,
            runner_output_root=args.runner_output_root,
            output_dir=args.output_dir,
            error=exc,
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def export_failure_review_template(
    *,
    batch_dir: Path,
    runner_output_root: Path,
    output_dir: Path,
    review_name: str = DEFAULT_REVIEW_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build failure review rows and a redacted summary.

    Args:
        batch_dir: Directory containing redacted batch manifests.
        runner_output_root: Batch OCR runner output root.
        output_dir: Planned output directory.
        review_name: Review JSONL filename.
        summary_name: Summary JSON filename.

    Returns:
        Review rows and summary.

    Raises:
        ValueError: If inputs are malformed or unsafe.
    """
    safe_review_name = _safe_filename(review_name, suffix=".jsonl", field_name="review_name")
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    manifest_metadata = _load_batch_manifest_metadata(batch_dir)
    rows: list[dict[str, object]] = []
    missing_manifest_metadata_count = 0

    for batch_output_dir in sorted(runner_output_root.glob("batch-run-*")):
        if not batch_output_dir.is_dir():
            continue
        batch_name = _batch_manifest_name(batch_output_dir)
        observations_path = batch_output_dir / OBSERVATION_RELATIVE_PATH
        if not observations_path.is_file():
            continue
        for observation in _read_jsonl(observations_path):
            fixture_id = _safe_token(str(observation.get("fixture_id") or "unknown"))
            metadata = manifest_metadata.get(fixture_id)
            if metadata is None:
                missing_manifest_metadata_count += 1
                metadata = {}
            review_row = _failure_review_row(
                observation=observation,
                metadata=metadata,
                batch_name=batch_name,
                batch_output_name=batch_output_dir.name,
            )
            if review_row is not None:
                rows.append(review_row)

    summary = _build_summary(
        rows=rows,
        batch_dir=batch_dir,
        runner_output_root=runner_output_root,
        output_dir=output_dir,
        review_name=safe_review_name,
        summary_name=safe_summary_name,
        missing_manifest_metadata_count=missing_manifest_metadata_count,
    )
    _reject_unsafe_payload({"rows": rows, "summary": summary})
    return rows, summary


def _failure_review_row(
    *,
    observation: dict[str, object],
    metadata: dict[str, object],
    batch_name: str,
    batch_output_name: str,
) -> dict[str, object] | None:
    """Return one failure review row, or None when observation is successful.

    Args:
        observation: Redacted OCR observation row.
        metadata: Redacted manifest metadata for the fixture.
        batch_name: Batch manifest filename.
        batch_output_name: Batch output directory name.

    Returns:
        Review row for failures only.
    """
    _reject_unsafe_payload(observation)
    status = str(observation.get("status") or "")
    llm_parse_status = str(observation.get("llm_parse_status") or "")
    is_ocr_failure = status == "error"
    is_llm_failure = status == "completed" and llm_parse_status == "error"
    if not is_ocr_failure and not is_llm_failure:
        return None

    error_code = _safe_optional_token(observation.get("error_code"))
    llm_error_code = _safe_optional_token(observation.get("llm_parse_error_code"))
    failure_kind = "ocr_error" if is_ocr_failure else "llm_parse_error"
    fixture_id = _safe_token(str(observation.get("fixture_id") or "unknown"))
    category_key = _safe_optional_token(metadata.get("category_key")) or "unknown"
    section = _safe_optional_token(metadata.get("section")) or "unknown"
    provider = _safe_optional_token(observation.get("provider")) or "unknown"
    review_task_id = _sha256_text(
        "|".join(
            [
                fixture_id,
                failure_kind,
                error_code or "",
                llm_error_code or "",
            ]
        )
    )
    row = {
        "schema_version": SCHEMA_VERSION,
        "review_task_id": review_task_id,
        "fixture_id": fixture_id,
        "batch_name": _safe_token(batch_name),
        "batch_output_name": _safe_token(batch_output_name),
        "provider": provider,
        "section": section,
        "category_key": category_key,
        "language_targets": _safe_string_list(metadata.get("language_targets")),
        "chronic_fixture_tags": _safe_string_list(metadata.get("chronic_fixture_tags")),
        "failure_kind": failure_kind,
        "status": _safe_token(status),
        "error_code": error_code,
        "llm_parse_status": _safe_optional_token(llm_parse_status),
        "llm_parse_error_code": llm_error_code,
        "suggested_next_action": _suggest_next_action(
            failure_kind=failure_kind,
            error_code=error_code,
            llm_error_code=llm_error_code,
        ),
        "requires_human_review": True,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(row)
    return row


def _load_batch_manifest_metadata(batch_dir: Path) -> dict[str, dict[str, object]]:
    """Load safe metadata from every batch manifest.

    Args:
        batch_dir: Batch manifest directory.

    Returns:
        Mapping of fixture id to safe metadata.
    """
    metadata: dict[str, dict[str, object]] = {}
    for manifest_path in sorted(batch_dir.glob("*.jsonl")):
        for row in _read_jsonl(manifest_path):
            fixture_id = row.get("fixture_id")
            if not isinstance(fixture_id, str) or not fixture_id:
                continue
            db_labeling = row.get("db_labeling")
            db_labeling = db_labeling if isinstance(db_labeling, dict) else {}
            metadata[_safe_token(fixture_id)] = {
                "section": _safe_optional_token(row.get("section")) or "unknown",
                "category_key": _safe_optional_token(db_labeling.get("category_key")) or "unknown",
                "language_targets": _safe_string_list(db_labeling.get("language_targets")),
                "chronic_fixture_tags": _safe_string_list(db_labeling.get("chronic_fixture_tags")),
            }
    return metadata


def _batch_manifest_name(batch_output_dir: Path) -> str:
    """Return the batch manifest name from the per-batch report.

    Args:
        batch_output_dir: Batch runner output directory.

    Returns:
        Safe manifest filename or unknown.
    """
    report_path = batch_output_dir / REPORT_NAME
    if not report_path.is_file():
        return "unknown"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    _reject_unsafe_payload(report)
    manifest_name = report.get("manifest_name")
    return _safe_optional_token(manifest_name) or "unknown"


def _build_summary(
    *,
    rows: list[dict[str, object]],
    batch_dir: Path,
    runner_output_root: Path,
    output_dir: Path,
    review_name: str,
    summary_name: str,
    missing_manifest_metadata_count: int,
) -> dict[str, object]:
    """Build a redacted failure-review summary."""
    failure_kind_counts = Counter(str(row["failure_kind"]) for row in rows)
    category_key_counts = Counter(str(row["category_key"]) for row in rows)
    error_code_counts = Counter(str(row.get("error_code") or "none") for row in rows)
    llm_error_code_counts = Counter(str(row.get("llm_parse_error_code") or "none") for row in rows)
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "review_name": review_name,
        "summary_name": summary_name,
        "batch_dir_name": batch_dir.name,
        "batch_dir_path_hash": _sha256_text(str(batch_dir.expanduser())),
        "runner_output_root_name": runner_output_root.name,
        "runner_output_root_hash": _sha256_text(str(runner_output_root.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_path_hash": _sha256_text(str(output_dir.expanduser())),
        "review_row_count": len(rows),
        "missing_manifest_metadata_count": missing_manifest_metadata_count,
        "failure_kind_counts": dict(sorted(failure_kind_counts.items())),
        "category_key_counts": dict(sorted(category_key_counts.items())),
        "error_code_counts": dict(sorted(error_code_counts.items())),
        "llm_parse_error_code_counts": dict(sorted(llm_error_code_counts.items())),
        "requires_human_review_count": sum(1 for row in rows if row.get("requires_human_review")),
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
    review_name: str,
    summary_name: str,
) -> None:
    """Write review JSONL and summary JSON artifacts."""
    safe_review_name = _safe_filename(review_name, suffix=".jsonl", field_name="review_name")
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / safe_review_name).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (output_dir / safe_summary_name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL rows and reject unsafe payloads."""
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


def _suggest_next_action(
    *,
    failure_kind: str,
    error_code: str | None,
    llm_error_code: str | None,
) -> str:
    """Return a bounded next-action token for failure triage."""
    if failure_kind == "ocr_error" and error_code == "ocr_low_confidence":
        return "inspect_image_quality_or_preprocess"
    if failure_kind == "ocr_error":
        return "inspect_ocr_provider_failure"
    if llm_error_code == "ollama_structured_output":
        return "retry_structured_parser_or_schema_prompt"
    return "inspect_parser_failure"


def _safe_string_list(value: object) -> list[str]:
    """Return safe token list from a JSON value."""
    if not isinstance(value, list):
        return []
    tokens: list[str] = []
    for item in value:
        if isinstance(item, str) and item:
            tokens.append(_safe_token(item))
    return tokens


def _safe_optional_token(value: object) -> str | None:
    """Return a safe token or None."""
    if not isinstance(value, str) or not value:
        return None
    return _safe_token(value)


def _safe_token(value: str) -> str:
    """Return a bounded safe token.

    Raises:
        ValueError: If token is unsafe.
    """
    token = value.strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(token) or any(
        marker in token for marker in LOCAL_PATH_MARKERS
    ):
        raise ValueError("Unsafe token.")
    return token


def _safe_filename(value: str, *, suffix: str, field_name: str) -> str:
    """Return a safe filename with the required suffix."""
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
    runner_output_root: Path,
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
        "runner_output_root_name": runner_output_root.name,
        "runner_output_root_hash": _sha256_text(str(runner_output_root.expanduser())),
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
