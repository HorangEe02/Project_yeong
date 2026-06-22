"""Export safe review decision templates for Naver Tampermonkey review rows.

The output is an operator/UI contract, not an importable decision batch. It
contains stable review identifiers, bounded candidate hints, and the required
human decision fields. It never stores raw OCR text, raw provider payloads,
request headers, image bytes, local paths, free-text review notes, or secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import validate_naver_tampermonkey_review_decisions as validator  # noqa: E402

SCHEMA_VERSION = "naver-tampermonkey-review-decision-template-v1"
EXPECTED_INPUT_SCHEMA_VERSION = "naver-tampermonkey-review-ingest-v1"
EXPECTED_GAP_QUEUE_SCHEMA_VERSION = "naver-tampermonkey-manual-review-gap-v1"
DECISION_ROW_SCHEMA_VERSION = "naver-tampermonkey-review-decision-v1"
DEFAULT_MAX_CANDIDATES = 12
MAX_TEXT_LENGTH = validator.MAX_TEXT_LENGTH
MAX_INGREDIENT_NAME_LENGTH = 160
LOCAL_PATH_MARKERS = validator.LOCAL_PATH_MARKERS
REVIEW_DECISION_CONTRACT = {
    "allowed_statuses": sorted(validator.ALLOWED_DECISION_STATUSES),
    "decision_row_schema_version_required": DECISION_ROW_SCHEMA_VERSION,
    "reviewer_id_required_prefix": "operator_",
    "approved_required_fields": [
        "status",
        "reviewer_id",
        "reviewed_at",
        "display_name",
        "ingredients",
        *validator.APPROVED_ATTESTATIONS,
    ],
    "rejected_or_needs_changes_required_fields": [
        "status",
        "reviewer_id",
        "reviewed_at",
        "reason_codes",
    ],
    "reviewed_at_required_format": "timezone_aware_iso8601",
    "approved_attestations_required": list(validator.APPROVED_ATTESTATIONS),
    "approved_ingredient_display_name_max_length": MAX_INGREDIENT_NAME_LENGTH,
    "approved_ingredient_max_count": validator.MAX_INGREDIENTS_PER_PRODUCT,
    "approved_ingredient_identity_unique_by": [
        "normalized_display_name",
        "nutrient_code",
    ],
    "approved_ingredient_amount_type": "number_or_null",
    "approved_ingredient_source_required": "human_reviewed",
    "approved_ingredient_packaging_quantity_text_allowed": False,
    "reviewed_text_executable_or_url_content_allowed": False,
    "free_text_notes_allowed": False,
    "raw_ocr_text_allowed": False,
    "provider_payload_allowed": False,
    "local_path_literals_allowed": False,
    "clinical_recommendations_allowed": False,
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for exporting review templates."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=DEFAULT_MAX_CANDIDATES,
        help="Maximum safe ingredient candidate hints per review row.",
    )
    parser.add_argument(
        "--gap-queue",
        type=Path,
        default=None,
        help="Optional manual-review gap queue JSONL. When set, export only those review rows.",
    )
    return parser.parse_args()


def main() -> None:
    """Write review decision templates and a redacted summary."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    input_path = args.input.expanduser().resolve()
    try:
        rows, summary = export_review_decision_template_rows(
            input_path=input_path,
            max_candidates=args.max_candidates,
            gap_queue_path=(
                args.gap_queue.expanduser().resolve() if args.gap_queue is not None else None
            ),
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
        failure = _failure_summary(input_path=input_path, output_path=output_path, error=exc)
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


def export_review_decision_template_rows(
    *,
    input_path: Path,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    gap_queue_path: Path | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return safe review decision template rows for a review ingest artifact.

    Args:
        input_path: Review ingest JSONL path.
        max_candidates: Maximum candidate hints retained per row.
        gap_queue_path: Optional manual-review gap queue for narrowing rows.

    Returns:
        Template rows and a redacted summary.

    Raises:
        ValueError: If any input row is unsafe, not a review ingest row, or not
            eligible for human review.
    """
    candidate_limit = _candidate_limit(max_candidates)
    input_rows = _read_input_rows(input_path)
    gap_contexts = _read_gap_contexts(gap_queue_path) if gap_queue_path is not None else None
    if gap_contexts is not None:
        input_by_review_id = {_required_str(row, "review_task_id"): row for row in input_rows}
        missing_ids = sorted(set(gap_contexts) - set(input_by_review_id))
        if missing_ids:
            raise ValueError(f"Gap queue review_task_id is not in review ingest: {missing_ids[0]}")
        input_rows = [input_by_review_id[review_task_id] for review_task_id in sorted(gap_contexts)]
    rows = [
        _template_row(
            row,
            max_candidates=candidate_limit,
            gap_context=(
                gap_contexts.get(_required_str(row, "review_task_id"))
                if gap_contexts is not None
                else None
            ),
        )
        for row in input_rows
    ]
    total_candidates = sum(
        len(row["candidate_context"]["ingredient_candidates"])  # type: ignore[index]
        for row in rows
    )
    rows_with_candidates = sum(
        1
        for row in rows
        if row["candidate_context"]["ingredient_candidates"]  # type: ignore[index]
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_name": input_path.name,
        "row_count": len(rows),
        "rows_with_candidate_hints": rows_with_candidates,
        "total_candidate_hints": total_candidates,
        "max_candidates_per_row": candidate_limit,
        "gap_queue_name": gap_queue_path.name if gap_queue_path is not None else None,
        "gap_queue_row_count": len(gap_contexts) if gap_contexts is not None else None,
        "gap_queue_filter_applied": gap_contexts is not None,
        "decision_batch_importable": False,
        "requires_human_review": True,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "free_text_review_notes_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload({"rows": rows, "summary": summary})
    return rows, summary


def _failure_summary(
    *,
    input_path: Path,
    output_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "input_name": input_path.name,
        "input_path_hash": _sha256_text(str(input_path.expanduser())),
        "output_name": output_path.name,
        "output_path_hash": _sha256_text(str(output_path.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "row_count": 0,
        "rows_with_candidate_hints": 0,
        "total_candidate_hints": 0,
        "decision_batch_importable": False,
        "requires_human_review": True,
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


def _template_row(
    row: dict[str, object],
    *,
    max_candidates: int,
    gap_context: dict[str, object] | None = None,
) -> dict[str, object]:
    """Return one safe review template row."""
    _validate_review_row(row)
    category_key = _required_safe_token(row, "category_key")
    template = {
        "schema_version": SCHEMA_VERSION,
        "review_task_id": _required_str(row, "review_task_id"),
        "fixture_id": _required_str(row, "fixture_id"),
        "category_key": category_key,
        "review_decision_contract": REVIEW_DECISION_CONTRACT,
        "decision_entry_template": _decision_entry_template(row),
        "candidate_context": {
            "ingredient_candidates": _candidate_ingredients(
                row.get("ingredient_candidates"),
                max_candidates=max_candidates,
            ),
            "ocr_observation_count": _non_negative_int(row.get("ocr_observation_count")),
            "ingredient_candidate_count": _non_negative_int(row.get("ingredient_candidate_count")),
        },
    }
    if gap_context is not None:
        template["gap_context"] = gap_context
    _reject_unsafe_payload(template)
    return template


def _decision_entry_template(row: dict[str, object]) -> dict[str, object]:
    """Return a non-importable review decision skeleton for operators."""
    return {
        "schema_version": DECISION_ROW_SCHEMA_VERSION,
        "review_task_id": _required_str(row, "review_task_id"),
        "fixture_id": _required_str(row, "fixture_id"),
        "review_decision": {
            "status": None,
            "reviewer_id": None,
            "reviewed_at": None,
            "display_name": None,
            "ingredients": [
                {
                    "display_name": None,
                    "nutrient_code": None,
                    "amount": None,
                    "unit": None,
                    "source": validator.APPROVED_INGREDIENT_SOURCE,
                }
            ],
            "reason_codes": [],
            "attest_pii_screening_completed": False,
            "attest_no_raw_ocr_text": False,
            "attest_not_clinical_recommendation": False,
        },
        "decision_batch_importable": False,
    }


def _read_gap_contexts(path: Path) -> dict[str, dict[str, object]]:
    """Read a safe manual-review gap queue keyed by review task id."""
    contexts: dict[str, dict[str, object]] = {}
    for row in _read_input_rows(path):
        if row.get("schema_version") != EXPECTED_GAP_QUEUE_SCHEMA_VERSION:
            raise ValueError("Gap queue rows must use manual-review gap schema.")
        if row.get("requires_human_review") is not True:
            raise ValueError("Gap queue rows must require human review.")
        if row.get("decision_batch_importable") is not False:
            raise ValueError("Gap queue rows must not be importable decision batches.")
        if row.get("db_write_performed") is not False:
            raise ValueError("Gap queue rows must not perform DB writes.")
        review_task_id = _required_str(row, "review_task_id")
        if review_task_id in contexts:
            raise ValueError(f"Duplicate review_task_id in gap queue: {review_task_id}")
        contexts[review_task_id] = {
            "gap_reasons": _safe_token_list(row.get("gap_reasons")),
            "suggested_operator_actions": _safe_token_list(row.get("suggested_operator_actions")),
            "ingredient_candidate_count": _non_negative_int(row.get("ingredient_candidate_count")),
            "ocr_observation_count": _non_negative_int(row.get("ocr_observation_count")),
        }
    return contexts


def _candidate_ingredients(value: object, *, max_candidates: int) -> list[dict[str, object]]:
    """Return bounded ingredient candidate hints for human review."""
    if not isinstance(value, list):
        return []
    candidates: list[dict[str, object]] = []
    for item in value:
        if len(candidates) >= max_candidates:
            break
        if not isinstance(item, dict):
            continue
        display_name = _optional_string(
            item.get("display_name"),
            max_length=MAX_INGREDIENT_NAME_LENGTH,
        )
        if display_name is None:
            continue
        candidate = {
            "display_name": display_name,
            "nutrient_code": _optional_safe_token(item.get("nutrient_code")),
            "amount": _optional_non_negative_number(item.get("amount")),
            "unit": _optional_string(item.get("unit"), max_length=40),
            "confidence": _optional_confidence(item.get("confidence")),
            "source": _optional_safe_token(item.get("source")),
            "provider": _optional_safe_token(item.get("provider")),
        }
        candidates.append({key: val for key, val in candidate.items() if val is not None})
    return candidates


def _validate_review_row(row: dict[str, object]) -> None:
    """Validate the review ingest row before template export."""
    _reject_unsafe_payload(row)
    if row.get("schema_version") != EXPECTED_INPUT_SCHEMA_VERSION:
        raise ValueError("Review template input rows must use review ingest schema.")
    if row.get("requires_human_review") is not True:
        raise ValueError("Review template rows must require human review.")
    if row.get("is_clinical_recommendation") is not False:
        raise ValueError("Review template rows must not be clinical recommendations.")
    if row.get("clinical_recommendation_forbidden") is not True:
        raise ValueError("Review template rows must keep clinical recommendation forbidden.")


def _read_input_rows(path: Path) -> list[dict[str, object]]:
    """Read input JSONL rows and reject unsafe payloads."""
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL rows must be objects.")
        _reject_unsafe_payload(row)
        review_task_id = _required_str(row, "review_task_id")
        if review_task_id in seen:
            raise ValueError(f"Duplicate review_task_id: {review_task_id}")
        seen.add(review_task_id)
        rows.append(row)
    return rows


def _candidate_limit(value: int) -> int:
    """Return a bounded positive candidate limit."""
    if value < 0:
        raise ValueError("max_candidates must be non-negative.")
    return min(value, validator.MAX_INGREDIENTS_PER_PRODUCT)


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = row.get(key)
    text = _optional_string(value)
    if text is None:
        raise ValueError(f"Row requires string field: {key}")
    return text


def _required_safe_token(row: dict[str, object], key: str) -> str:
    """Return a required bounded token field."""
    value = _optional_safe_token(row.get(key))
    if value is None:
        raise ValueError(f"Row requires safe token field: {key}")
    return value


def _optional_safe_token(value: object) -> str | None:
    """Return a bounded safe token or None."""
    return validator._safe_token(value)


def _safe_token_list(value: object) -> list[str]:
    """Return sorted unique safe tokens from a list value."""
    if not isinstance(value, list):
        return []
    tokens: list[str] = []
    for item in value:
        token = _optional_safe_token(item)
        if token is not None:
            tokens.append(token)
    return sorted(set(tokens))


def _optional_string(value: object, *, max_length: int = MAX_TEXT_LENGTH) -> str | None:
    """Return a bounded string while rejecting local path literals."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    validator.reject_executable_text_value(stripped)
    return stripped[:max_length]


def _optional_non_negative_number(value: object) -> float | None:
    """Return a non-negative number or None."""
    if isinstance(value, int | float) and value >= 0:
        return float(value)
    return None


def _optional_confidence(value: object) -> float | None:
    """Return a bounded confidence value or None."""
    if isinstance(value, int | float) and 0 <= value <= 1:
        return float(value)
    return None


def _non_negative_int(value: object) -> int:
    """Return a non-negative integer, defaulting missing values to zero."""
    return value if isinstance(value, int) and value >= 0 else 0


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys, local path literals, and sensitive literal keys recursively."""
    validator._reject_unsafe_payload(value)


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
