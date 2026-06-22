"""Export a non-importable DB-write approval template for Tampermonkey imports.

The template binds an approved import JSONL, matching dry-run artifacts, and a
passing privacy summary by SHA-256. It is intentionally not accepted by the DB
write runner until a human reviewer converts it to
``naver-tampermonkey-db-write-approval-v1`` and sets the required attestations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from scripts import dry_run_naver_tampermonkey_approved_db_import as dry_run  # noqa: E402
from scripts import run_naver_tampermonkey_approved_db_import as db_importer  # noqa: E402

SCHEMA_VERSION = "naver-tampermonkey-db-write-approval-template-v1"
LOCAL_PATH_MARKERS = db_importer.LOCAL_PATH_MARKERS
RAW_FORBIDDEN_KEYS = db_importer.RAW_FORBIDDEN_KEYS
LITERAL_FORBIDDEN_KEYS = db_importer.LITERAL_FORBIDDEN_KEYS


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the approval template exporter."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-input", type=Path, required=True)
    parser.add_argument("--dry-run-plan", type=Path, required=True)
    parser.add_argument("--dry-run-summary", type=Path, required=True)
    parser.add_argument("--privacy-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    return parser.parse_args()


def main() -> None:
    """Write the approval template and redacted summary."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        template, summary = export_db_write_approval_template(
            approved_input_path=args.approved_input.expanduser().resolve(),
            dry_run_plan_path=args.dry_run_plan.expanduser().resolve(),
            dry_run_summary_path=args.dry_run_summary.expanduser().resolve(),
            privacy_summary_path=args.privacy_summary.expanduser().resolve(),
        )
        _write_json(output_path, template)
        _write_json(summary_path, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            approved_input_path=args.approved_input,
            dry_run_plan_path=args.dry_run_plan,
            dry_run_summary_path=args.dry_run_summary,
            privacy_summary_path=args.privacy_summary,
            output_path=output_path,
            error=exc,
        )
        _write_json(summary_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def export_db_write_approval_template(
    *,
    approved_input_path: Path,
    dry_run_plan_path: Path,
    dry_run_summary_path: Path,
    privacy_summary_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return a non-importable reviewer approval template and summary.

    Args:
        approved_input_path: Approved DB import JSONL.
        dry_run_plan_path: Matching dry-run plan JSONL.
        dry_run_summary_path: Matching dry-run summary JSON.
        privacy_summary_path: Passing artifact privacy summary JSON.

    Returns:
        Template object and redacted summary.
    """
    expected_plan_rows, expected_dry_run_summary = dry_run.build_dry_run_import_plan(
        input_path=approved_input_path,
    )
    actual_plan_rows = db_importer._read_jsonl_objects(dry_run_plan_path)
    dry_run_summary = db_importer._read_json_object(dry_run_summary_path)
    privacy_summary = db_importer._read_json_object(privacy_summary_path)
    if actual_plan_rows != expected_plan_rows:
        raise ValueError("Dry-run plan does not match approved input rows.")
    db_importer._validate_dry_run_summary(
        dry_run_summary=dry_run_summary,
        expected_summary=expected_dry_run_summary,
    )
    db_importer._validate_privacy_summary(privacy_summary)

    template = {
        "schema_version": SCHEMA_VERSION,
        "approval_log_schema_version": db_importer.APPROVAL_LOG_SCHEMA_VERSION,
        "approved_for_db_write": False,
        "reviewer_id": "operator_REQUIRED_SAFE_TOKEN",
        "reviewer_id_required_prefix": db_importer.APPROVAL_REVIEWER_ID_PREFIX,
        "approved_at": "REQUIRED_ISO8601_UTC",
        "approved_input_sha256": _sha256_file(approved_input_path),
        "dry_run_plan_sha256": _sha256_file(dry_run_plan_path),
        "dry_run_summary_sha256": _sha256_file(dry_run_summary_path),
        "privacy_summary_sha256": _sha256_file(privacy_summary_path),
        "planned_product_upsert_count": expected_dry_run_summary["planned_product_upsert_count"],
        "planned_ingredient_row_count": expected_dry_run_summary["planned_ingredient_row_count"],
        "attest_dry_run_reviewed": False,
        "attest_privacy_scan_passed": False,
        "attest_reviewer_approved": False,
        "attest_not_clinical_recommendation": False,
        "template_importable": False,
        "free_text_notes_allowed": False,
        "raw_ocr_text_allowed": False,
        "provider_payload_allowed": False,
        "local_path_literals_allowed": False,
        "clinical_recommendations_allowed": False,
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "approved_input_name": approved_input_path.name,
        "dry_run_plan_name": dry_run_plan_path.name,
        "dry_run_summary_name": dry_run_summary_path.name,
        "privacy_summary_name": privacy_summary_path.name,
        "planned_product_upsert_count": expected_dry_run_summary["planned_product_upsert_count"],
        "planned_ingredient_row_count": expected_dry_run_summary["planned_ingredient_row_count"],
        "template_importable": False,
        "db_write_performed": False,
        "external_transfer_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload({"template": template, "summary": summary})
    return template, summary


def _write_json(path: Path, value: dict[str, object]) -> None:
    """Write one JSON object after unsafe-payload rejection."""
    _reject_unsafe_payload(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _failure_summary(
    *,
    approved_input_path: Path,
    dry_run_plan_path: Path,
    dry_run_summary_path: Path,
    privacy_summary_path: Path,
    output_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "approved_input_name": approved_input_path.name,
        "dry_run_plan_name": dry_run_plan_path.name,
        "dry_run_summary_name": dry_run_summary_path.name,
        "privacy_summary_name": privacy_summary_path.name,
        "output_name": output_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "template_importable": False,
        "db_write_performed": False,
        "external_transfer_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys, local path literals, and sensitive literal keys recursively."""
    if isinstance(value, dict):
        lowered_keys = {str(key).lower() for key in value}
        forbidden = RAW_FORBIDDEN_KEYS.intersection(lowered_keys)
        literal_forbidden = LITERAL_FORBIDDEN_KEYS.intersection(lowered_keys)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        if literal_forbidden:
            raise ValueError(
                f"Payload contains forbidden literal field(s): {sorted(literal_forbidden)}"
            )
        for nested in value.values():
            _reject_unsafe_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded non-sensitive CLI error code."""
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


def _sha256_file(path: Path) -> str:
    """Return a SHA-256 digest for a local artifact file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
