"""Apply structured review decisions to Naver Tampermonkey review ingest rows.

This operator workflow joins a separate decision JSONL onto
``naver-tampermonkey-review-ingest-v1`` rows by ``review_task_id``. It writes a
new review ingest artifact with attached ``review_decision`` objects, then
validates the output with the review-decision validator before returning. Raw OCR
text, provider payloads, free-text review notes, local paths, and secrets are
rejected before any output file is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import validate_naver_tampermonkey_review_decisions as validator  # noqa: E402

SCHEMA_VERSION = "naver-tampermonkey-review-decision-apply-v1"
EXPECTED_REVIEW_INGEST_SCHEMA_VERSION = "naver-tampermonkey-review-ingest-v1"
EXPECTED_DECISION_SCHEMA_VERSION = "naver-tampermonkey-review-decision-v1"
RAW_FORBIDDEN_KEYS = validator.RAW_FORBIDDEN_KEYS
LITERAL_FORBIDDEN_KEYS = validator.LITERAL_FORBIDDEN_KEYS
LOCAL_PATH_MARKERS = validator.LOCAL_PATH_MARKERS


@dataclass(frozen=True)
class DecisionRecord:
    """Decision row plus the fixture id it was authored for."""

    fixture_id: str
    decision: dict[str, object]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for applying review decisions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-ingest", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Allow replacing an existing review_decision on a review ingest row.",
    )
    parser.add_argument(
        "--allow-unmatched-decisions",
        action="store_true",
        help="Ignore decision rows whose review_task_id is not present in review ingest.",
    )
    parser.add_argument(
        "--require-reviewed",
        action="store_true",
        help="Validate that every output row has a review_decision.",
    )
    return parser.parse_args()


def main() -> None:
    """Apply decisions and write an updated review ingest artifact."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    review_ingest_path = args.review_ingest.expanduser().resolve()
    decisions_path = args.decisions.expanduser().resolve()
    try:
        rows, summary = apply_review_decisions(
            review_ingest_path=review_ingest_path,
            decisions_path=decisions_path,
            output_name=output_path.name,
            overwrite_existing=args.overwrite_existing,
            allow_unmatched_decisions=args.allow_unmatched_decisions,
            require_reviewed=args.require_reviewed,
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
            review_ingest_path=review_ingest_path,
            decisions_path=decisions_path,
            output_path=output_path,
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


def apply_review_decisions(
    *,
    review_ingest_path: Path,
    decisions_path: Path,
    output_name: str,
    overwrite_existing: bool = False,
    allow_unmatched_decisions: bool = False,
    require_reviewed: bool = False,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return review ingest rows with validated review decisions attached.

    Args:
        review_ingest_path: Review ingest JSONL path.
        decisions_path: Decision JSONL path keyed by ``review_task_id``.
        output_name: Planned output filename for validation summary metadata.
        overwrite_existing: Whether existing decisions may be replaced.
        allow_unmatched_decisions: Whether unmatched decision rows are ignored.
        require_reviewed: Whether every output row must be reviewed.

    Returns:
        Updated review ingest rows and a redacted summary.

    Raises:
        ValueError: If raw fields, duplicate decisions, unsafe decisions, or
            unmatched decisions are found.
    """
    review_rows = _read_review_ingest_rows(review_ingest_path)
    decisions = _read_decision_rows(decisions_path)
    review_ids = {_required_str(row, "review_task_id") for row in review_rows}
    matched_decision_ids: set[str] = set()
    merged_rows: list[dict[str, object]] = []

    for row in review_rows:
        review_task_id = _required_str(row, "review_task_id")
        decision_record = decisions.get(review_task_id)
        merged_row = dict(row)
        if decision_record is not None:
            if "review_decision" in merged_row and not overwrite_existing:
                raise ValueError(f"Review row already has review_decision: {review_task_id}")
            _validate_decision_fixture_match(row=row, decision_record=decision_record)
            merged_row["review_decision"] = decision_record.decision
            matched_decision_ids.add(review_task_id)
        _reject_unsafe_payload(merged_row)
        merged_rows.append(merged_row)

    unmatched_ids = sorted(set(decisions) - review_ids)
    if unmatched_ids and not allow_unmatched_decisions:
        raise ValueError(f"Decision review_task_id is not in review ingest: {unmatched_ids[0]}")

    validation_summary = _validate_rows(
        rows=merged_rows,
        output_name=output_name,
        require_reviewed=require_reviewed,
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "review_ingest_name": review_ingest_path.name,
        "decisions_name": decisions_path.name,
        "output_name": output_name,
        "review_row_count": len(review_rows),
        "decision_row_count": len(decisions),
        "matched_decision_count": len(matched_decision_ids),
        "unmatched_decision_count": len(unmatched_ids),
        "pending_count": validation_summary["pending_count"],
        "decision_status_counts": validation_summary["decision_status_counts"],
        "require_reviewed": require_reviewed,
        "overwrite_existing": overwrite_existing,
        "allow_unmatched_decisions": allow_unmatched_decisions,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "free_text_review_notes_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload({"rows": merged_rows, "summary": summary})
    return merged_rows, summary


def _failure_summary(
    *,
    review_ingest_path: Path,
    decisions_path: Path,
    output_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "review_ingest_name": review_ingest_path.name,
        "review_ingest_path_hash": _sha256_text(str(review_ingest_path.expanduser())),
        "decisions_name": decisions_path.name,
        "decisions_path_hash": _sha256_text(str(decisions_path.expanduser())),
        "output_name": output_path.name,
        "output_path_hash": _sha256_text(str(output_path.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "review_row_count": 0,
        "decision_row_count": 0,
        "matched_decision_count": 0,
        "unmatched_decision_count": 0,
        "pending_count": 0,
        "decision_status_counts": {},
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "free_text_review_notes_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _validate_rows(
    *,
    rows: list[dict[str, object]],
    output_name: str,
    require_reviewed: bool,
) -> dict[str, object]:
    """Validate merged rows using the review decision validator rules."""
    status_counts: Counter[str] = Counter()
    pending_count = 0
    approved_ingredient_count = 0
    for row in rows:
        validator._validate_row_schema(row)
        decision = row.get("review_decision")
        if decision is None:
            pending_count += 1
            status_counts["pending"] += 1
            continue
        if not isinstance(decision, dict):
            raise ValueError("review_decision must be an object.")
        status = validator._validate_decision(row, decision)
        status_counts[status] += 1
        if status == "approved":
            approved_ingredient_count += len(decision.get("ingredients", []))  # type: ignore[arg-type]
    if require_reviewed and pending_count:
        raise ValueError("Review decision validation requires every row to be reviewed.")
    return {
        "schema_version": validator.SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_name": output_name,
        "row_count": len(rows),
        "pending_count": pending_count,
        "decision_status_counts": dict(sorted(status_counts.items())),
        "approved_ingredient_count": approved_ingredient_count,
        "require_reviewed": require_reviewed,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "free_text_review_notes_stored": False,
        "clinical_recommendations_stored": False,
    }


def _read_review_ingest_rows(path: Path) -> list[dict[str, object]]:
    """Read review ingest JSONL rows and reject unsafe payloads."""
    rows = _read_jsonl_objects(path)
    seen: set[str] = set()
    for row in rows:
        if row.get("schema_version") != EXPECTED_REVIEW_INGEST_SCHEMA_VERSION:
            raise ValueError("Review ingest rows must use review ingest schema.")
        review_task_id = _required_str(row, "review_task_id")
        if review_task_id in seen:
            raise ValueError(f"Duplicate review_task_id in review ingest: {review_task_id}")
        seen.add(review_task_id)
    return rows


def _read_decision_rows(path: Path) -> dict[str, DecisionRecord]:
    """Read decision JSONL rows keyed by review task id."""
    decisions: dict[str, DecisionRecord] = {}
    for row in _read_jsonl_objects(path):
        if row.get("schema_version") != EXPECTED_DECISION_SCHEMA_VERSION:
            raise ValueError("Decision rows must use review decision schema.")
        review_task_id = _required_str(row, "review_task_id")
        if review_task_id in decisions:
            raise ValueError(f"Duplicate review decision for review_task_id: {review_task_id}")
        row_fixture_id = _required_str(row, "fixture_id")
        decision = row.get("review_decision")
        if not isinstance(decision, dict):
            raise ValueError("Decision rows require object field: review_decision")
        decision_fixture_id = decision.get("fixture_id")
        if (
            isinstance(decision_fixture_id, str)
            and row_fixture_id.strip() != decision_fixture_id.strip()
        ):
            raise ValueError("Decision fixture_id does not match row fixture_id.")
        clean_decision = dict(decision)
        clean_decision.pop("review_task_id", None)
        clean_decision.pop("fixture_id", None)
        status = validator._validate_decision(
            _minimal_validation_row(row),
            clean_decision,
        )
        clean_decision["status"] = status
        _reject_unsafe_payload(clean_decision)
        decisions[review_task_id] = DecisionRecord(
            fixture_id=row_fixture_id,
            decision=clean_decision,
        )
    return decisions


def _validate_decision_fixture_match(
    *,
    row: dict[str, object],
    decision_record: DecisionRecord,
) -> None:
    """Validate that a decision row was authored for the matched review row."""
    row_fixture_id = _required_str(row, "fixture_id")
    if decision_record.fixture_id != row_fixture_id:
        raise ValueError("Decision fixture_id does not match review ingest fixture_id.")


def _minimal_validation_row(row: dict[str, object]) -> dict[str, object]:
    """Return a minimal review row envelope for standalone decision validation."""
    return {
        "schema_version": EXPECTED_REVIEW_INGEST_SCHEMA_VERSION,
        "review_task_id": _required_str(row, "review_task_id"),
        "fixture_id": _required_str(row, "fixture_id"),
        "requires_human_review": True,
        "contains_personal_data": row.get("contains_personal_data", False),
        "is_clinical_recommendation": False,
        "clinical_recommendation_forbidden": True,
    }


def _read_jsonl_objects(path: Path) -> list[dict[str, object]]:
    """Read JSONL objects from disk."""
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


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Row requires string field: {key}")
    if any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    return value.strip()


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


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for a UTF-8 text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


if __name__ == "__main__":
    main()
