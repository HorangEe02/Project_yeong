"""Export manual-review gap rows from Naver Tampermonkey review ingest.

The queue is for operator triage of rows that have no ingredient candidate
hints or still have OCR errors after retries. It is not an importable decision
batch and does not perform database writes. It never stores raw OCR text,
provider payloads, request headers, image bytes, raw model responses, local
paths, or free-text notes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import validate_naver_tampermonkey_review_decisions as validator  # noqa: E402

SCHEMA_VERSION = "naver-tampermonkey-manual-review-gap-v1"
SUMMARY_SCHEMA_VERSION = "naver-tampermonkey-manual-review-gap-summary-v1"
EXPECTED_INPUT_SCHEMA_VERSION = "naver-tampermonkey-review-ingest-v1"
DEFAULT_QUEUE_NAME = "manual-review-gap-queue.jsonl"
DEFAULT_SUMMARY_NAME = "manual-review-gap-queue.summary.json"
LOCAL_PATH_MARKERS = validator.LOCAL_PATH_MARKERS
SHA256_HEX_LENGTH = 64


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the manual-review gap exporter."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--queue-name", default=DEFAULT_QUEUE_NAME)
    parser.add_argument("--summary-name", default=DEFAULT_SUMMARY_NAME)
    return parser.parse_args()


def main() -> None:
    """Write the manual-review gap queue and summary."""
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    try:
        rows, summary = export_gap_queue(
            input_path=input_path,
            output_dir=output_dir,
            queue_name=args.queue_name,
            summary_name=args.summary_name,
        )
        _write_outputs(
            rows=rows,
            summary=summary,
            output_dir=output_dir,
            queue_name=args.queue_name,
            summary_name=args.summary_name,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(input_path=input_path, output_dir=output_dir, error=exc)
        _write_failure_summary(
            failure=failure,
            output_dir=output_dir,
            summary_name=args.summary_name,
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def export_gap_queue(
    *,
    input_path: Path,
    output_dir: Path,
    queue_name: str = DEFAULT_QUEUE_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return manual-review gap rows and a redacted summary.

    Args:
        input_path: Review ingest JSONL path.
        output_dir: Planned output directory.
        queue_name: Queue JSONL filename.
        summary_name: Summary JSON filename.

    Returns:
        Gap rows and summary.
    """
    safe_queue_name = _safe_filename(queue_name, suffix=".jsonl", field_name="queue_name")
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    input_rows = _read_input_rows(input_path)
    rows = [_gap_row(row) for row in input_rows if _gap_reasons(row)]
    summary = _build_summary(
        rows=rows,
        input_rows=input_rows,
        input_path=input_path,
        output_dir=output_dir,
        queue_name=safe_queue_name,
        summary_name=safe_summary_name,
    )
    _reject_unsafe_payload({"rows": rows, "summary": summary})
    return rows, summary


def _gap_row(row: dict[str, object]) -> dict[str, object]:
    """Return one bounded manual-review gap row."""
    _validate_input_row(row)
    gap_row = {
        "schema_version": SCHEMA_VERSION,
        "review_task_id": _required_str(row, "review_task_id"),
        "fixture_id": _required_str(row, "fixture_id"),
        "category_key": _required_safe_token(row, "category_key"),
        "section": _optional_safe_token(row.get("section")),
        "gap_reasons": _gap_reasons(row),
        "suggested_operator_actions": _suggest_actions(row),
        "category_display": _category_display(row.get("category_display")),
        "category_reference_url_count": _safe_list_len(row.get("category_reference_urls")),
        "language_targets": _safe_token_list(row.get("language_targets")),
        "chronic_fixture_tags": _safe_token_list(row.get("chronic_fixture_tags")),
        "caution_tags": _safe_token_list(row.get("caution_tags")),
        "product": _product_summary(row.get("product")),
        "image": _image_summary(row.get("image")),
        "ingredient_candidate_count": _non_negative_int(row.get("ingredient_candidate_count")),
        "ocr_observation_count": _non_negative_int(row.get("ocr_observation_count")),
        "ocr_provider_summaries": _ocr_provider_summaries(row.get("ocr_provider_summaries")),
        "review_task": _review_task_summary(row.get("review_task")),
        "decision_batch_importable": False,
        "requires_human_review": True,
        "db_write_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "free_text_review_notes_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload(gap_row)
    return gap_row


def _gap_reasons(row: dict[str, object]) -> list[str]:
    """Return reason codes for including a review row in the gap queue."""
    reasons: list[str] = []
    if _non_negative_int(row.get("ingredient_candidate_count")) == 0:
        reasons.append("ingredient_candidate_count_zero")
    summaries = row.get("ocr_provider_summaries")
    if isinstance(summaries, list):
        for summary in summaries:
            if not isinstance(summary, dict):
                continue
            if summary.get("status") == "error":
                reasons.append("ocr_provider_error")
                break
            if (
                summary.get("llm_parse_status") == "completed"
                and _non_negative_int(summary.get("llm_parsed_ingredient_count")) == 0
            ):
                reasons.append("llm_zero_ingredient_candidates")
                break
    return sorted(set(reasons))


def _suggest_actions(row: dict[str, object]) -> list[str]:
    """Return bounded operator action suggestions for one gap row."""
    reasons = set(_gap_reasons(row))
    actions: list[str] = []
    if "ocr_provider_error" in reasons:
        actions.append("inspect_source_image_and_enter_manual_ingredients")
    if "llm_zero_ingredient_candidates" in reasons:
        actions.append("review_ocr_summary_and_enter_manual_ingredients")
    if "ingredient_candidate_count_zero" in reasons and not actions:
        actions.append("enter_manual_ingredients_or_mark_not_scoreable")
    actions.append("do_not_copy_ocr_output")
    actions.append("do_not_enter_clinical_recommendations")
    return actions


def _build_summary(
    *,
    rows: list[dict[str, object]],
    input_rows: list[dict[str, object]],
    input_path: Path,
    output_dir: Path,
    queue_name: str,
    summary_name: str,
) -> dict[str, object]:
    """Build a redacted manual-review gap summary."""
    reason_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    for row in rows:
        category_counts[_required_safe_token(row, "category_key")] += 1
        for reason in row.get("gap_reasons", []):
            reason_counts[_safe_token(str(reason))] += 1
        for action in row.get("suggested_operator_actions", []):
            action_counts[_safe_token(str(action))] += 1
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_name": _safe_filename(input_path.name, suffix=".jsonl", field_name="input"),
        "input_path_hash": _sha256_text(str(input_path.expanduser())),
        "output_dir_name": _safe_filename(output_dir.name, field_name="output_dir"),
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "queue_filename": queue_name,
        "summary_filename": summary_name,
        "input_row_count": len(input_rows),
        "gap_row_count": len(rows),
        "rows_requiring_manual_ingredients": len(rows),
        "decision_batch_importable": False,
        "db_write_performed": False,
        "reason_counts": dict(sorted(reason_counts.items())),
        "category_key_counts": dict(sorted(category_counts.items())),
        "suggested_operator_action_counts": dict(sorted(action_counts.items())),
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


def _write_outputs(
    *,
    rows: list[dict[str, object]],
    summary: dict[str, object],
    output_dir: Path,
    queue_name: str,
    summary_name: str,
) -> None:
    """Write redacted manual-review gap queue and summary."""
    safe_queue_name = _safe_filename(queue_name, suffix=".jsonl", field_name="queue_name")
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    _reject_unsafe_payload({"rows": rows, "summary": summary})
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / safe_queue_name).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (output_dir / safe_summary_name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_failure_summary(
    *,
    failure: dict[str, object],
    output_dir: Path,
    summary_name: str,
) -> None:
    """Best-effort write of a redacted failure summary."""
    try:
        safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
        _reject_unsafe_payload(failure)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / safe_summary_name).write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError):
        return


def _failure_summary(
    *,
    input_path: Path,
    output_dir: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted failure summary."""
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "input_name": input_path.name,
        "input_path_hash": _sha256_text(str(input_path.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "gap_row_count": 0,
        "decision_batch_importable": False,
        "db_write_performed": False,
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


def _read_input_rows(path: Path) -> list[dict[str, object]]:
    """Read review ingest JSONL rows and reject unsafe payloads."""
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL rows must be objects.")
        _validate_input_row(row)
        review_task_id = _required_str(row, "review_task_id")
        if review_task_id in seen:
            raise ValueError(f"Duplicate review_task_id: {review_task_id}")
        seen.add(review_task_id)
        rows.append(row)
    return rows


def _validate_input_row(row: dict[str, object]) -> None:
    """Validate one review ingest row before gap export."""
    _reject_unsafe_payload(row)
    if row.get("schema_version") != EXPECTED_INPUT_SCHEMA_VERSION:
        raise ValueError("Manual-review gap input rows must use review ingest schema.")
    if row.get("requires_human_review") is not True:
        raise ValueError("Manual-review gap rows must require human review.")
    if row.get("clinical_recommendation_forbidden") is not True:
        raise ValueError("Clinical recommendation guard must remain enabled.")
    if row.get("is_clinical_recommendation") is not False:
        raise ValueError("Clinical recommendation rows are not allowed.")


def _category_display(value: object) -> dict[str, str]:
    """Return safe localized category display names."""
    if not isinstance(value, dict):
        return {}
    output: dict[str, str] = {}
    for key in ("ko", "en"):
        text = _optional_string(value.get(key), max_length=80)
        if text:
            output[key] = text
    return output


def _product_summary(value: object) -> dict[str, object]:
    """Return safe product identifiers without product directory literals."""
    if not isinstance(value, dict):
        return {}
    product: dict[str, object] = {}
    product_id = _optional_string(value.get("product_id"), max_length=80)
    product_hash = _optional_sha256(value.get("product_dir_hash"))
    if product_id:
        product["product_id"] = product_id
    if product_hash:
        product["product_dir_hash"] = product_hash
    return product


def _image_summary(value: object) -> dict[str, object]:
    """Return safe image identifiers without paths or image bytes."""
    if not isinstance(value, dict):
        return {}
    image: dict[str, object] = {}
    image_ref_hash = _optional_sha256(value.get("image_ref_hash"))
    image_sha256 = _optional_sha256(value.get("image_sha256"))
    root_token = _optional_string(value.get("root_token"), max_length=80)
    if image_ref_hash:
        image["image_ref_hash"] = image_ref_hash
    if image_sha256:
        image["image_sha256"] = image_sha256
    if root_token:
        image["root_token"] = root_token
    return image


def _ocr_provider_summaries(value: object) -> list[dict[str, object]]:
    """Return bounded OCR summary fields relevant to manual review."""
    if not isinstance(value, list):
        return []
    summaries: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        summary = {
            "provider": _optional_safe_token(item.get("provider")),
            "status": _optional_safe_token(item.get("status")),
            "error_code": _optional_safe_token(item.get("error_code")),
            "text_non_empty": item.get("text_non_empty") is True,
            "char_count": _non_negative_int(item.get("char_count")),
            "parser_success": item.get("parser_success") is True,
            "llm_parse_status": _optional_safe_token(item.get("llm_parse_status")),
            "llm_parsed_ingredient_count": _non_negative_int(
                item.get("llm_parsed_ingredient_count")
            ),
        }
        summaries.append({key: val for key, val in summary.items() if val is not None})
    return summaries


def _review_task_summary(value: object) -> dict[str, object]:
    """Return bounded review-task status fields."""
    if not isinstance(value, dict):
        return {}
    return {
        "status": _optional_safe_token(value.get("status")),
        "priority": _optional_safe_token(value.get("priority")),
        "db_import_ready": value.get("db_import_ready") is True,
        "reason_codes": _safe_token_list(value.get("reasons")),
        "blocked_reason_codes": _safe_token_list(value.get("blocked_reasons")),
    }


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = _optional_string(row.get(key), max_length=validator.MAX_TEXT_LENGTH)
    if value is None:
        raise ValueError(f"Row requires string field: {key}")
    return value


def _required_safe_token(row: dict[str, object], key: str) -> str:
    """Return a required bounded safe token field."""
    value = _optional_safe_token(row.get(key))
    if value is None:
        raise ValueError(f"Row requires safe token field: {key}")
    return value


def _optional_safe_token(value: object) -> str | None:
    """Return a safe token or None."""
    return validator._safe_token(value)


def _safe_token(value: str) -> str:
    """Return a safe token string."""
    token = validator._safe_token(value)
    if token is None:
        raise ValueError("Unsafe token.")
    return token


def _optional_string(value: object, *, max_length: int = validator.MAX_TEXT_LENGTH) -> str | None:
    """Return a bounded string while rejecting local path literals."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    return stripped[:max_length]


def _safe_token_list(value: object) -> list[str]:
    """Return bounded safe-token list values."""
    if not isinstance(value, list):
        return []
    tokens: list[str] = []
    for item in value:
        token = _optional_safe_token(item)
        if token is not None:
            tokens.append(token)
    return tokens


def _safe_list_len(value: object) -> int:
    """Return length for safe list values."""
    return len(value) if isinstance(value, list) else 0


def _non_negative_int(value: object) -> int:
    """Return a non-negative integer, defaulting missing values to zero."""
    return value if isinstance(value, int) and value >= 0 else 0


def _optional_sha256(value: object) -> str | None:
    """Return a SHA-256 hex digest string or None."""
    if (
        isinstance(value, str)
        and len(value) == SHA256_HEX_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    ):
        return value
    return None


def _safe_filename(value: str, *, suffix: str | None = None, field_name: str = "filename") -> str:
    """Return a safe filename token."""
    token = value.strip()
    if "/" in token or "\\" in token or not token:
        raise ValueError(f"Unsafe {field_name}.")
    if suffix is not None and not token.endswith(suffix):
        raise ValueError(f"{field_name} must end with {suffix}.")
    safe = _optional_safe_token(token)
    if safe is None:
        raise ValueError(f"Unsafe {field_name}.")
    return safe


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys, local path literals, and sensitive literal keys recursively."""
    validator._reject_unsafe_payload(value)


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


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for a UTF-8 text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
