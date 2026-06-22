"""Apply operator PII screening decisions to supplement review OCR candidates.

Review images can contain names, faces, addresses, order details, or other
personal data. This script keeps those images fail-closed until a human
operator explicitly attests that no personal data is visible. Only attested
``cleared_no_personal_data`` rows become eligible for teacher OCR comparison.

The script does not read image bytes, does not run OCR, does not call external
providers, does not write to the database, and does not emit local absolute
paths, product directory literals, raw OCR text, or provider payloads.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import build_supplement_learning_candidate_manifests as candidates  # noqa: E402

SCHEMA_VERSION = "supplement-review-pii-screening-apply-v1"
DECISION_SCHEMA_VERSION = "supplement-review-pii-screening-decision-v1"
OUTPUT_ROW_SCHEMA_VERSION = candidates.OCR_ROW_SCHEMA_VERSION
EXPECTED_CANDIDATE_SCHEMA_VERSION = candidates.OCR_ROW_SCHEMA_VERSION
ALLOWED_DECISIONS = frozenset(
    {
        "cleared_no_personal_data",
        "contains_personal_data",
        "needs_rescreen",
        "reject",
    }
)
REQUIRED_CLEARED_ATTESTATIONS = (
    "attest_local_screening_completed",
    "attest_no_personal_data_visible",
    "attest_no_raw_text_copied",
    "attest_teacher_ocr_transfer_allowed",
)
ALLOWED_DECISION_KEYS = frozenset(
    {
        "decision",
        "reviewer_id",
        "reviewed_at",
        "reason_codes",
        *REQUIRED_CLEARED_ATTESTATIONS,
    }
)
ALLOWED_REASON_CODES = frozenset(
    {
        "no_personal_data_visible",
        "face_visible",
        "name_visible",
        "contact_visible",
        "address_visible",
        "receipt_or_order_visible",
        "other_personal_data_visible",
        "unreadable",
        "needs_manual_rescreen",
        "wrong_image_type",
    }
)
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:+-]{1,96}$")
OPERATOR_REVIEWER_ID_PATTERN = re.compile(r"^operator_[A-Za-z0-9_.:-]{1,71}$")
RAW_FORBIDDEN_KEYS = candidates.RAW_FORBIDDEN_KEYS | frozenset(
    {
        "image_path",
        "local_path",
        "object_url",
        "provider_response",
        "source_path",
    }
)
LOCAL_PATH_OR_URL_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "http://",
    "https://",
    "\\Users\\",
    "\\Volumes\\",
)
FREE_TEXT_KEYS = frozenset({"comment", "comments", "note", "notes", "review_note"})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument("--allow-unmatched-decisions", action="store_true")
    parser.add_argument("--require-all-reviewed", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Apply decisions and write the updated supplement OCR candidate manifest.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = apply_pii_screening_decisions(
            candidate_manifest=args.candidate_manifest,
            decisions_path=args.decisions,
            allow_unmatched_decisions=args.allow_unmatched_decisions,
            require_all_reviewed=args.require_all_reviewed,
        )
        _reject_unsafe_payload({"rows": rows, "summary": summary})
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
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
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def apply_pii_screening_decisions(
    *,
    candidate_manifest: Path,
    decisions_path: Path,
    allow_unmatched_decisions: bool = False,
    require_all_reviewed: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply operator decisions to supplement review OCR candidates.

    Args:
        candidate_manifest: JSONL produced by
            ``build_supplement_learning_candidate_manifests.py``.
        decisions_path: Operator decision JSONL.
        allow_unmatched_decisions: Whether decisions for absent fixture ids are
            ignored. The default rejects stale or misplaced decision files.
        require_all_reviewed: Whether every input candidate must have a
            decision.

    Returns:
        Updated candidate rows and a redacted summary.

    Raises:
        ValueError: If any row is unsafe, malformed, duplicated, or stale.
    """
    candidate_rows = _read_candidate_rows(candidate_manifest)
    decisions = _read_decision_rows(decisions_path)
    candidate_ids = {
        _required_safe_token(row.get("fixture_id"), field_name="fixture_id")
        for row in candidate_rows
    }
    unmatched_ids = sorted(set(decisions) - candidate_ids)
    if unmatched_ids and not allow_unmatched_decisions:
        raise ValueError(
            f"PII decision fixture_id is not in candidate manifest: {unmatched_ids[0]}"
        )

    output_rows: list[dict[str, Any]] = []
    decision_counts: Counter[str] = Counter()
    skip_counts: Counter[str] = Counter()
    pending_count = 0

    for row in candidate_rows:
        fixture_id = _required_safe_token(row.get("fixture_id"), field_name="fixture_id")
        decision = decisions.get(fixture_id)
        if decision is None:
            pending_count += 1
            decision_counts["pending"] += 1
            output_rows.append(dict(row))
            continue

        decision_value = _required_safe_token(decision.get("decision"), field_name="decision")
        decision_counts[decision_value] += 1
        if decision_value == "cleared_no_personal_data":
            output_rows.append(_cleared_candidate_row(row, decision=decision))
        else:
            skip_counts[f"{decision_value}_blocked"] += 1

    if require_all_reviewed and pending_count:
        raise ValueError("PII screening requires every supplement review candidate to be reviewed.")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_manifest_name": candidate_manifest.name,
        "decisions_name": decisions_path.name,
        "candidate_row_count": len(candidate_rows),
        "decision_row_count": len(decisions),
        "unmatched_decision_count": len(unmatched_ids),
        "pending_count": pending_count,
        "decision_counts": dict(sorted(decision_counts.items())),
        "skip_reason_counts": dict(sorted(skip_counts.items())),
        "cleared_row_count": sum(1 for row in output_rows if _candidate_is_teacher_allowed(row)),
        "teacher_ocr_allowed_rows": sum(
            1 for row in output_rows if row.get("teacher_ocr_allowed") is True
        ),
        "external_transfer_allowed_rows": sum(
            1 for row in output_rows if row.get("external_transfer_allowed") is True
        ),
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload({"rows": output_rows, "summary": summary})
    return output_rows, summary


def _cleared_candidate_row(
    row: dict[str, Any],
    *,
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Return a candidate row unlocked for teacher OCR comparison.

    Args:
        row: Original review OCR candidate row.
        decision: Validated operator decision object.

    Returns:
        Updated JSON-safe candidate row.

    Raises:
        ValueError: If required cleared attestations are missing.
    """
    for key in REQUIRED_CLEARED_ATTESTATIONS:
        if decision.get(key) is not True:
            raise ValueError(f"Cleared supplement PII decision requires attestation: {key}")
    cleared = dict(row)
    cleared.update(
        {
            "contains_personal_data": False,
            "pii_screening_status": "operator_cleared_no_personal_data",
            "ground_truth_status": "pending_manual_transcription",
            "external_transfer_allowed": True,
            "teacher_ocr_allowed": True,
            "local_processing_allowed": True,
            "operator_decision_required": False,
            "pii_screening": {
                "decision": "cleared_no_personal_data",
                "reviewer_id": _required_operator_reviewer_id(decision),
                "reviewed_at": _required_safe_token(
                    decision.get("reviewed_at"),
                    field_name="reviewed_at",
                ),
                "reason_codes": _safe_reason_codes(decision.get("reason_codes")),
            },
            "db_write_performed": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
        }
    )
    _reject_unsafe_payload(cleared)
    return cleared


def _read_candidate_rows(path: Path) -> list[dict[str, Any]]:
    """Read supplement review OCR candidate rows.

    Args:
        path: Candidate JSONL path.

    Returns:
        Candidate rows.

    Raises:
        ValueError: If the manifest contains unsupported rows.
    """
    rows = _read_jsonl_objects(path)
    seen: set[str] = set()
    for row in rows:
        _reject_unsafe_payload(row)
        if row.get("schema_version") != EXPECTED_CANDIDATE_SCHEMA_VERSION:
            raise ValueError("Supplement OCR candidate rows use an unsupported schema.")
        if row.get("candidate_purpose") != "ocr_ground_truth_review":
            raise ValueError("Supplement PII decisions only apply to review OCR candidates.")
        if row.get("source_kind") != "review":
            raise ValueError("Supplement PII decisions only apply to review source rows.")
        fixture_id = _required_safe_token(row.get("fixture_id"), field_name="fixture_id")
        if fixture_id in seen:
            raise ValueError(f"Duplicate supplement OCR candidate fixture_id: {fixture_id}")
        seen.add(fixture_id)
        if (
            row.get("external_transfer_allowed") is True
            and row.get("contains_personal_data") is not False
        ):
            raise ValueError("External transfer requires contains_personal_data=false.")
    return rows


def _read_decision_rows(path: Path) -> dict[str, dict[str, Any]]:
    """Read operator PII decision rows keyed by fixture id.

    Args:
        path: Decision JSONL path.

    Returns:
        Mapping from fixture id to decision object.

    Raises:
        ValueError: If decisions are unsafe, malformed, or duplicated.
    """
    decisions: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl_objects(path):
        _reject_unsafe_payload(row)
        if row.get("schema_version") not in {None, DECISION_SCHEMA_VERSION}:
            raise ValueError("Supplement PII decision row uses an unsupported schema.")
        fixture_id = _required_safe_token(row.get("fixture_id"), field_name="fixture_id")
        if fixture_id in decisions:
            raise ValueError(f"Duplicate supplement PII decision fixture_id: {fixture_id}")
        decision = row.get("pii_screening_decision")
        if not isinstance(decision, dict):
            raise ValueError("Supplement PII decision rows require pii_screening_decision object.")
        _validate_decision(decision)
        decisions[fixture_id] = dict(decision)
    return decisions


def _validate_decision(decision: dict[str, Any]) -> None:
    """Validate one operator PII decision object.

    Args:
        decision: Decision payload.

    Raises:
        ValueError: If the decision is unsafe or incomplete.
    """
    _reject_unsafe_payload(decision)
    keys = {str(key).lower() for key in decision}
    if FREE_TEXT_KEYS.intersection(keys):
        raise ValueError("Supplement PII decision cannot include free-text notes.")
    unexpected = sorted(keys - ALLOWED_DECISION_KEYS)
    if unexpected:
        raise ValueError(f"Supplement PII decision contains unsupported field: {unexpected[0]}")
    decision_value = _required_safe_token(decision.get("decision"), field_name="decision")
    if decision_value not in ALLOWED_DECISIONS:
        raise ValueError(f"Unsupported supplement PII decision: {decision_value}")
    _required_operator_reviewer_id(decision)
    _required_safe_token(decision.get("reviewed_at"), field_name="reviewed_at")
    if decision_value == "cleared_no_personal_data":
        for key in REQUIRED_CLEARED_ATTESTATIONS:
            if decision.get(key) is not True:
                raise ValueError(f"Cleared supplement PII decision requires attestation: {key}")
    elif not _safe_reason_codes(decision.get("reason_codes")):
        raise ValueError(f"{decision_value} supplement PII decisions require reason_codes.")


def _read_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows and reject non-object records.

    Args:
        path: JSONL path.

    Returns:
        JSON object rows.

    Raises:
        ValueError: If any row is not a JSON object.
    """
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL rows must be objects.")
        _reject_unsafe_payload(row)
        rows.append(row)
    return rows


def _candidate_is_teacher_allowed(row: dict[str, Any]) -> bool:
    """Return whether a row is unlocked for teacher OCR comparison.

    Args:
        row: Candidate row.

    Returns:
        True if the privacy and teacher OCR gates are open.
    """
    return (
        row.get("candidate_purpose") == "ocr_ground_truth_review"
        and row.get("source_kind") == "review"
        and row.get("contains_personal_data") is False
        and row.get("pii_screening_status") == "operator_cleared_no_personal_data"
        and row.get("external_transfer_allowed") is True
        and row.get("teacher_ocr_allowed") is True
    )


def _required_operator_reviewer_id(row: dict[str, Any]) -> str:
    """Return a reviewer id that proves a human/operator approval.

    Args:
        row: Decision object.

    Returns:
        Reviewer id.

    Raises:
        ValueError: If the reviewer id is missing or not operator-scoped.
    """
    reviewer_id = _required_safe_token(row.get("reviewer_id"), field_name="reviewer_id")
    if not OPERATOR_REVIEWER_ID_PATTERN.fullmatch(reviewer_id):
        raise ValueError("Supplement PII reviewer_id must use the operator_ prefix.")
    return reviewer_id


def _required_safe_token(value: Any, *, field_name: str) -> str:
    """Return a required bounded token.

    Args:
        value: Raw value.
        field_name: Field name used in validation errors.

    Returns:
        Safe token string.

    Raises:
        ValueError: If the value is missing or unsafe.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Row requires safe token field: {field_name}")
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_OR_URL_MARKERS):
        raise ValueError("Payload contains local path or URL literal.")
    if not SAFE_TOKEN_PATTERN.fullmatch(stripped):
        raise ValueError(f"Unsafe token field: {field_name}")
    return stripped


def _safe_reason_codes(value: Any) -> list[str]:
    """Return allowlisted reason codes.

    Args:
        value: Raw reason code list.

    Returns:
        Sanitized reason codes.

    Raises:
        ValueError: If reason codes are malformed or unsupported.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Supplement PII reason_codes must be a list.")
    codes: list[str] = []
    for item in value:
        code = _required_safe_token(item, field_name="reason_codes")
        if code not in ALLOWED_REASON_CODES:
            raise ValueError(f"Unsupported supplement PII reason_code: {code}")
        codes.append(code)
    return codes


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw fields, local paths, URLs, and product directory literals.

    Args:
        value: Arbitrary JSON-like payload.

    Raises:
        ValueError: If unsafe content is found.
    """
    if isinstance(value, dict):
        keys = {str(key).lower() for key in value}
        forbidden = RAW_FORBIDDEN_KEYS.intersection(keys)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        if "product_dir" in keys:
            raise ValueError("Payload must not store product_dir literals.")
        for nested in value.values():
            _reject_unsafe_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_OR_URL_MARKERS):
        raise ValueError("Payload contains local path or URL literal.")


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
        require_all_reviewed: CLI strict-review flag.
        error: Raised exception.

    Returns:
        JSON-safe failure payload.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "candidate_manifest_name": candidate_manifest.name,
        "decisions_name": decisions_path.name,
        "output_name": output_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "require_all_reviewed": require_all_reviewed,
        "candidate_row_count": 0,
        "decision_row_count": 0,
        "cleared_row_count": 0,
        "teacher_ocr_allowed_rows": 0,
        "external_transfer_allowed_rows": 0,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_error_code(error: Exception) -> str:
    """Return a non-sensitive error code.

    Args:
        error: Raised exception.

    Returns:
        Public error code.
    """
    if isinstance(error, OSError):
        return "local_file_read_error"
    if isinstance(error, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_public_error_message(error: Exception) -> str:
    """Return a bounded public error message without filesystem details.

    Args:
        error: Raised exception.

    Returns:
        Redacted error message.
    """
    if isinstance(error, OSError):
        return "Local file read failed."
    message = str(error).strip()
    if not message:
        return "Validation failed."
    if any(marker in message for marker in LOCAL_PATH_OR_URL_MARKERS):
        return "Validation failed."
    if "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


if __name__ == "__main__":
    main()
