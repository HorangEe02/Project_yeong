"""Preflight supplement review-image PII screening decisions before apply.

This tool checks whether an operator-edited ``decisions.todo.jsonl`` can be
passed to ``apply_supplement_review_pii_screening_decisions.py``. Blank stubs
are treated as pending operator work instead of being auto-cleared.

The script does not read image bytes, does not run OCR, does not call external
providers, does not write to the database, and does not emit local absolute
paths, product directory literals, raw OCR text, or provider payloads.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import apply_supplement_review_pii_screening_decisions as applier  # noqa: E402
from scripts import build_supplement_ocr_benchmark_manifest as benchmark  # noqa: E402
from scripts import export_supplement_review_pii_screening_template as template_export  # noqa: E402

SCHEMA_VERSION = "supplement-review-pii-screening-decision-preflight-v1"
SOURCE_DOC_URLS = template_export.SOURCE_DOC_URLS
VALIDATION_CODE_MARKERS = (
    ("duplicate", "duplicate_fixture_id"),
    ("unsupported_schema", "unsupported_schema"),
    ("unsupported schema", "unsupported_schema"),
    ("missing_decision_object", "missing_decision_object"),
    ("pii_screening_decision object", "missing_decision_object"),
    ("raw field", "unsafe_raw_field"),
    ("local path", "unsafe_path_or_url"),
    ("url literal", "unsafe_path_or_url"),
    ("free-text", "free_text_note"),
    ("unsupported field", "unsupported_field"),
    ("attestation", "missing_required_attestation"),
    ("reason_codes", "invalid_reason_codes"),
    ("operator_ prefix", "invalid_reviewer_id"),
    ("unsafe token", "invalid_token"),
    ("safe token", "invalid_token"),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-all-reviewed", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a redacted PII decision preflight summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    try:
        summary = preflight_pii_screening_decisions(
            candidate_manifest=args.candidate_manifest,
            decisions_path=args.decisions,
            require_all_reviewed=args.require_all_reviewed,
        )
        benchmark._reject_unsafe_payload(summary)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            candidate_manifest=args.candidate_manifest,
            decisions_path=args.decisions,
            output_path=output_path,
            require_all_reviewed=args.require_all_reviewed,
            error=exc,
        )
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


def preflight_pii_screening_decisions(
    *,
    candidate_manifest: Path,
    decisions_path: Path,
    require_all_reviewed: bool = False,
) -> dict[str, Any]:
    """Return redacted readiness for applying PII screening decisions.

    Args:
        candidate_manifest: Review OCR candidate JSONL.
        decisions_path: Operator-edited decision JSONL.
        require_all_reviewed: Whether every candidate must have a completed
            valid decision before the requested apply step is considered ready.

    Returns:
        Redacted preflight summary.

    Raises:
        ValueError: If the candidate manifest itself is unsafe or malformed.
    """
    candidate_rows = applier._read_candidate_rows(candidate_manifest)
    candidate_ids = {
        applier._required_safe_token(row.get("fixture_id"), field_name="fixture_id")
        for row in candidate_rows
    }
    decision_scan = _scan_decision_rows(decisions_path=decisions_path, candidate_ids=candidate_ids)
    missing_decision_count = len(candidate_ids - decision_scan.seen_fixture_ids)
    pending_operator_action_count = (
        missing_decision_count
        + decision_scan.blank_decision_count
        + decision_scan.invalid_decision_count
        + decision_scan.unmatched_decision_count
    )
    ready_for_partial_apply = (
        decision_scan.valid_decision_count > 0
        and decision_scan.invalid_decision_count == 0
        and decision_scan.blank_decision_count == 0
        and decision_scan.unmatched_decision_count == 0
    )
    ready_for_strict_apply = ready_for_partial_apply and missing_decision_count == 0
    ready_for_requested_apply = (
        ready_for_strict_apply if require_all_reviewed else ready_for_partial_apply
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_manifest_name": candidate_manifest.name,
        "decisions_name": decisions_path.name,
        "candidate_row_count": len(candidate_rows),
        "decision_row_count": decision_scan.decision_row_count,
        "valid_decision_count": decision_scan.valid_decision_count,
        "cleared_no_personal_data_count": decision_scan.cleared_no_personal_data_count,
        "blocked_decision_count": decision_scan.blocked_decision_count,
        "blank_decision_count": decision_scan.blank_decision_count,
        "invalid_decision_count": decision_scan.invalid_decision_count,
        "unmatched_decision_count": decision_scan.unmatched_decision_count,
        "missing_decision_count": missing_decision_count,
        "pending_operator_action_count": pending_operator_action_count,
        "decision_counts": dict(sorted(decision_scan.decision_counts.items())),
        "invalid_reason_counts": dict(sorted(decision_scan.invalid_reason_counts.items())),
        "require_all_reviewed": require_all_reviewed,
        "ready_for_partial_apply": ready_for_partial_apply,
        "ready_for_strict_apply": ready_for_strict_apply,
        "ready_for_requested_apply": ready_for_requested_apply,
        "next_operator_action": _next_operator_action(
            blank_count=decision_scan.blank_decision_count,
            invalid_count=decision_scan.invalid_decision_count,
            unmatched_count=decision_scan.unmatched_decision_count,
            missing_count=missing_decision_count,
            ready_for_requested_apply=ready_for_requested_apply,
        ),
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    benchmark._reject_unsafe_payload(summary)
    return summary


class DecisionScan:
    """Aggregate state for one decision JSONL scan."""

    def __init__(self) -> None:
        """Initialize empty counters."""
        self.decision_row_count = 0
        self.valid_decision_count = 0
        self.cleared_no_personal_data_count = 0
        self.blocked_decision_count = 0
        self.blank_decision_count = 0
        self.invalid_decision_count = 0
        self.unmatched_decision_count = 0
        self.seen_fixture_ids: set[str] = set()
        self.decision_counts: Counter[str] = Counter()
        self.invalid_reason_counts: Counter[str] = Counter()


def _scan_decision_rows(*, decisions_path: Path, candidate_ids: set[str]) -> DecisionScan:
    """Scan decision JSONL rows without applying them.

    Args:
        decisions_path: Operator-edited decision JSONL path.
        candidate_ids: Allowed candidate fixture ids.

    Returns:
        DecisionScan aggregate.
    """
    scan = DecisionScan()
    for line in decisions_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        scan.decision_row_count += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            _mark_invalid(scan, "json_decode_error")
            continue
        if not isinstance(row, dict):
            _mark_invalid(scan, "non_object_row")
            continue
        try:
            applier._reject_unsafe_payload(row)
            _scan_decision_row(row, scan=scan, candidate_ids=candidate_ids)
        except ValueError as exc:
            _mark_invalid(scan, _safe_validation_code(exc))
    return scan


def _scan_decision_row(
    row: dict[str, Any],
    *,
    scan: DecisionScan,
    candidate_ids: set[str],
) -> None:
    """Scan one parsed decision row.

    Args:
        row: Parsed JSON object.
        scan: Mutable scan aggregate.
        candidate_ids: Allowed candidate fixture ids.

    Raises:
        ValueError: If the row is malformed or unsafe.
    """
    if row.get("schema_version") not in {None, applier.DECISION_SCHEMA_VERSION}:
        raise ValueError("unsupported_schema")
    fixture_id = applier._required_safe_token(row.get("fixture_id"), field_name="fixture_id")
    if fixture_id in scan.seen_fixture_ids:
        raise ValueError("duplicate_fixture_id")
    scan.seen_fixture_ids.add(fixture_id)
    if fixture_id not in candidate_ids:
        scan.unmatched_decision_count += 1
    decision = row.get("pii_screening_decision")
    if not isinstance(decision, dict):
        raise ValueError("missing_decision_object")
    if _decision_is_blank(decision):
        scan.blank_decision_count += 1
        scan.decision_counts["blank"] += 1
        return
    applier._validate_decision(decision)
    decision_value = applier._required_safe_token(decision.get("decision"), field_name="decision")
    scan.valid_decision_count += 1
    scan.decision_counts[decision_value] += 1
    if decision_value == "cleared_no_personal_data":
        scan.cleared_no_personal_data_count += 1
    else:
        scan.blocked_decision_count += 1


def _decision_is_blank(decision: dict[str, Any]) -> bool:
    """Return whether a decision object is still the untouched template stub.

    Args:
        decision: Decision payload.

    Returns:
        True when no operator decision has been entered.
    """
    return (
        decision.get("decision") in {None, ""}
        and decision.get("reviewer_id") in {None, ""}
        and decision.get("reviewed_at") in {None, ""}
        and decision.get("reason_codes") in (None, [])
        and decision.get("attest_local_screening_completed") is False
        and decision.get("attest_no_personal_data_visible") is False
        and decision.get("attest_no_raw_text_copied") is False
        and decision.get("attest_teacher_ocr_transfer_allowed") is False
    )


def _mark_invalid(scan: DecisionScan, reason: str) -> None:
    """Increment invalid counters.

    Args:
        scan: Mutable scan aggregate.
        reason: Safe invalid reason code.
    """
    scan.invalid_decision_count += 1
    scan.invalid_reason_counts[reason] += 1


def _safe_validation_code(error: ValueError) -> str:
    """Return a bounded non-sensitive validation code.

    Args:
        error: Validation exception.

    Returns:
        Safe reason code.
    """
    message = str(error).strip().lower()
    for marker, code in VALIDATION_CODE_MARKERS:
        if marker in message:
            return code
    return "validation_error"


def _next_operator_action(
    *,
    blank_count: int,
    invalid_count: int,
    unmatched_count: int,
    missing_count: int,
    ready_for_requested_apply: bool,
) -> str:
    """Return the next operator action code.

    Args:
        blank_count: Blank decision row count.
        invalid_count: Invalid decision row count.
        unmatched_count: Decision rows for absent candidates.
        missing_count: Candidates without decision rows.
        ready_for_requested_apply: Whether requested apply mode is ready.

    Returns:
        Stable action code.
    """
    if ready_for_requested_apply:
        return "run_pii_screening_apply"
    if invalid_count:
        return "fix_invalid_pii_decision_rows"
    if unmatched_count:
        return "remove_unmatched_pii_decision_rows"
    if blank_count or missing_count:
        return "complete_operator_pii_review"
    return "review_pii_decision_preflight"


def _failure_summary(
    *,
    candidate_manifest: Path,
    decisions_path: Path,
    output_path: Path,
    require_all_reviewed: bool,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted CLI failure summary.

    Args:
        candidate_manifest: Candidate manifest path.
        decisions_path: Decision JSONL path.
        output_path: Planned output path.
        require_all_reviewed: Strict review flag.
        error: Raised exception.

    Returns:
        Redacted failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "candidate_manifest_name": candidate_manifest.name,
        "decisions_name": decisions_path.name,
        "output_name": output_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_error_message(error),
        "require_all_reviewed": require_all_reviewed,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    benchmark._reject_unsafe_payload(summary)
    return summary


def _safe_error_code(error: Exception) -> str:
    """Return a public error code.

    Args:
        error: Raised exception.

    Returns:
        Error code.
    """
    if isinstance(error, OSError):
        return "local_file_read_error"
    if isinstance(error, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_error_message(error: Exception) -> str:
    """Return a bounded public error message.

    Args:
        error: Raised exception.

    Returns:
        Redacted message.
    """
    if isinstance(error, OSError):
        return "Local file read failed."
    message = str(error).strip()
    if not message:
        return "Validation failed."
    if "/" in message or "\\" in message:
        return "Validation failed."
    if any(marker in message for marker in applier.LOCAL_PATH_OR_URL_MARKERS):
        return "Validation failed."
    return message[:200]


if __name__ == "__main__":
    main()
