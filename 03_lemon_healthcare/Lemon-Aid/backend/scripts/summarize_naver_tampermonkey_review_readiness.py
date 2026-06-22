"""Summarize Naver Tampermonkey OCR review readiness without raw artifacts.

This gate reads only previously generated redacted JSON summaries. It does not
read OCR JSONL rows, source images, raw OCR text, provider payloads, model
responses, request headers, local paths, secrets, or database records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "naver-tampermonkey-review-readiness-summary-v1"
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
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
UNSAFE_TRUE_FLAGS = (
    "raw_artifacts_stored",
    "raw_ocr_text_stored",
    "raw_provider_payload_stored",
    "raw_model_response_stored",
    "local_path_literals_stored",
    "clinical_recommendations_stored",
    "db_write_performed",
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for review-readiness summarization."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-summary", type=Path, required=True)
    parser.add_argument("--review-ingest-summary", type=Path, required=True)
    parser.add_argument("--gap-queue-summary", type=Path, required=True)
    parser.add_argument("--gap-template-summary", type=Path, required=True)
    parser.add_argument("--gate-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--require-db-ready",
        action="store_true",
        help="Exit non-zero when the derived DB import readiness is false.",
    )
    return parser.parse_args()


def main() -> None:
    """Write a redacted review-readiness summary."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    input_paths = {
        "evaluation": args.evaluation_summary.expanduser().resolve(),
        "review_ingest": args.review_ingest_summary.expanduser().resolve(),
        "gap_queue": args.gap_queue_summary.expanduser().resolve(),
        "gap_template": args.gap_template_summary.expanduser().resolve(),
        "review_import_gate": args.gate_summary.expanduser().resolve(),
    }
    try:
        summary = summarize_review_readiness(input_paths=input_paths)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        if args.require_db_ready and summary["ready_for_db_import"] is not True:
            raise SystemExit(1)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def summarize_review_readiness(
    *,
    input_paths: dict[str, Path],
) -> dict[str, object]:
    """Return a redacted readiness summary from generated summary JSON files.

    Args:
        input_paths: Mapping of input labels to generated summary JSON paths.

    Returns:
        JSON-serializable readiness summary.

    Raises:
        ValueError: If summaries contain raw fields, unsafe literals, or are not
            JSON objects.
    """
    inputs = {label: _read_summary(path) for label, path in input_paths.items()}
    evaluation = inputs["evaluation"]
    review_ingest = inputs["review_ingest"]
    gap_queue = inputs["gap_queue"]
    gap_template = inputs["gap_template"]
    gate = inputs["review_import_gate"]

    provider = _primary_provider_summary(evaluation)
    privacy_failed_flags = sorted(_true_unsafe_flags(inputs))
    fixture_count = _non_negative_int(evaluation.get("fixture_count"))
    observation_count = _non_negative_int(evaluation.get("observation_count"))
    provider_error_count = _non_negative_int(provider.get("error_count"))
    review_row_count = _non_negative_int(review_ingest.get("row_count"))
    review_required_rows = _non_negative_int(review_ingest.get("review_required_rows"))
    db_import_ready_rows = _non_negative_int(review_ingest.get("db_import_ready_rows"))
    gap_row_count = _non_negative_int(gap_queue.get("gap_row_count"))
    gap_template_row_count = _non_negative_int(gap_template.get("row_count"))
    gap_pending_count = _non_negative_int(gate.get("gap_pending_count"))
    approved_row_count = _non_negative_int(gate.get("approved_row_count"))
    planned_product_upsert_count = _non_negative_int(gate.get("planned_product_upsert_count"))

    blocking_reasons = _blocking_reasons(
        privacy_failed_flags=privacy_failed_flags,
        fixture_count=fixture_count,
        observation_count=observation_count,
        provider_error_count=provider_error_count,
        review_required_rows=review_required_rows,
        db_import_ready_rows=db_import_ready_rows,
        gap_row_count=gap_row_count,
        gap_template_row_count=gap_template_row_count,
        gap_pending_count=gap_pending_count,
        approved_row_count=approved_row_count,
        planned_product_upsert_count=planned_product_upsert_count,
    )
    ready_for_db_import = not blocking_reasons
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {label: path.name for label, path in sorted(input_paths.items())},
        "input_path_hashes": {
            label: _sha256_text(str(path.expanduser()))
            for label, path in sorted(input_paths.items())
        },
        "fixture_count": fixture_count,
        "observation_count": observation_count,
        "provider_id": provider.get("provider_id"),
        "provider_completed_count": _non_negative_int(provider.get("completed_count")),
        "provider_error_count": provider_error_count,
        "review_row_count": review_row_count,
        "review_required_rows": review_required_rows,
        "db_import_ready_rows": db_import_ready_rows,
        "gap_row_count": gap_row_count,
        "gap_template_row_count": gap_template_row_count,
        "gap_pending_count": gap_pending_count,
        "approved_row_count": approved_row_count,
        "planned_product_upsert_count": planned_product_upsert_count,
        "ready_for_db_import": ready_for_db_import,
        "human_review_required": gap_pending_count > 0
        or db_import_ready_rows < review_required_rows,
        "blocking_reasons": blocking_reasons,
        "privacy_failed_flags": privacy_failed_flags,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
        "db_write_performed": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _blocking_reasons(
    *,
    privacy_failed_flags: list[str],
    fixture_count: int,
    observation_count: int,
    provider_error_count: int,
    review_required_rows: int,
    db_import_ready_rows: int,
    gap_row_count: int,
    gap_template_row_count: int,
    gap_pending_count: int,
    approved_row_count: int,
    planned_product_upsert_count: int,
) -> list[str]:
    """Return stable readiness blocker codes."""
    reasons: list[str] = []
    if privacy_failed_flags:
        reasons.append("privacy_flags_failed")
    if fixture_count != observation_count:
        reasons.append("observation_coverage_incomplete")
    if provider_error_count:
        reasons.append("ocr_provider_errors_present")
    if gap_row_count and gap_template_row_count != gap_row_count:
        reasons.append("gap_template_incomplete")
    if gap_pending_count:
        reasons.append("manual_gap_review_pending")
    if db_import_ready_rows < review_required_rows:
        reasons.append("review_rows_not_db_import_ready")
    if approved_row_count == 0:
        reasons.append("no_approved_import_rows")
    if planned_product_upsert_count != approved_row_count:
        reasons.append("dry_run_plan_mismatch")
    return sorted(set(reasons))


def _read_summary(path: Path) -> dict[str, object]:
    """Read one generated summary JSON and reject unsafe content."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Readiness inputs must be JSON objects.")
    _reject_unsafe_payload(value)
    return value


def _primary_provider_summary(evaluation: dict[str, object]) -> dict[str, object]:
    """Return the first provider summary from an OCR evaluation."""
    providers = evaluation.get("providers")
    if not isinstance(providers, dict) or not providers:
        return {}
    provider_id = sorted(str(key) for key in providers)[0]
    provider = providers.get(provider_id)
    if not isinstance(provider, dict):
        return {"provider_id": provider_id}
    return {"provider_id": provider_id, **provider}


def _true_unsafe_flags(inputs: dict[str, dict[str, object]]) -> set[str]:
    """Return unsafe boolean flags that are true in any input summary."""
    failures: set[str] = set()
    for label, summary in inputs.items():
        for key in UNSAFE_TRUE_FLAGS:
            if summary.get(key) is True:
                failures.add(f"{label}:{key}")
    return failures


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys and local path literals recursively."""
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if lowered in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"Payload contains forbidden raw key: {key_text}")
            _reject_unsafe_payload(nested)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


def _failure_summary(
    *,
    input_paths: dict[str, Path],
    output_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted failure summary."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "input_names": {label: path.name for label, path in sorted(input_paths.items())},
        "input_path_hashes": {
            label: _sha256_text(str(path.expanduser()))
            for label, path in sorted(input_paths.items())
        },
        "output_name": output_path.name,
        "output_path_hash": _sha256_text(str(output_path.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "ready_for_db_import": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
        "db_write_performed": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded non-sensitive error code."""
    if isinstance(exc, OSError):
        return "local_file_operation_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message without filesystem details."""
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


def _non_negative_int(value: object) -> int:
    """Return a non-negative integer, defaulting missing values to zero."""
    return value if isinstance(value, int) and value >= 0 else 0


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for a UTF-8 text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
