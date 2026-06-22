"""Export Naver Tampermonkey DB staging rows for a review UI ingest queue.

The input must be the privacy-safe ``naver-tampermonkey-db-labeling-with-ocr-v1``
artifact. The output is still not a production DB import: every row remains a
human-review task, and only bounded OCR/Ollama metadata plus ingredient
candidates are exposed. Raw OCR text, raw provider payloads, request headers,
model responses, image bytes, and local filesystem literals are rejected before
writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "naver-tampermonkey-review-ingest-v1"
EXPECTED_INPUT_SCHEMA_VERSION = "naver-tampermonkey-db-labeling-with-ocr-v1"
MAX_TOKEN_LENGTH = 80
MAX_TEXT_LENGTH = 160
MAX_URL_LENGTH = 512
MAX_INGREDIENTS_PER_TASK = 128
SHA256_HEX_LENGTH = 64
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
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
LITERAL_FORBIDDEN_KEYS = frozenset(
    {
        "absolute_path",
        "image_path",
        "local_path",
        "product_dir",
    }
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the review ingest exporter."""
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
        "--source-run-id",
        default=None,
        help="Optional operator run id to attach to every review task.",
    )
    return parser.parse_args()


def main() -> None:
    """Write review ingest rows and a redacted summary."""
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = export_review_ingest_rows(
            input_path=input_path,
            source_run_id=args.source_run_id,
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
            input_path=input_path,
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


def export_review_ingest_rows(
    *,
    input_path: Path,
    source_run_id: str | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return review ingest rows and a privacy-safe summary.

    Args:
        input_path: JSONL path using ``naver-tampermonkey-db-labeling-with-ocr-v1``.
        source_run_id: Optional operator run id for traceability.

    Returns:
        Review ingest rows and a summary dictionary.

    Raises:
        ValueError: If input rows use the wrong schema, include raw fields, leak
            local path literals, or expose LLM ingredients for PII-pending review
            rows.
    """
    input_rows = _read_input_rows(input_path)
    review_rows = [
        _review_row_from_input_row(row, source_run_id=source_run_id) for row in input_rows
    ]
    summary = build_summary(rows=review_rows, input_path=input_path)
    _reject_unsafe_payload({"rows": review_rows, "summary": summary})
    return review_rows, summary


def build_summary(
    *,
    rows: Sequence[dict[str, object]],
    input_path: Path,
) -> dict[str, object]:
    """Return a redacted summary for review ingest output."""
    category_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    rows_with_ocr = 0
    rows_with_llm = 0
    total_ingredient_candidates = 0
    pii_pending_review_rows = 0
    db_import_ready_rows = 0
    for row in rows:
        category_counts[str(row.get("category_key") or "unknown")] += 1
        section_counts[str(row.get("section") or "unknown")] += 1
        review_task = row.get("review_task")
        if isinstance(review_task, dict):
            status_counts[str(review_task.get("status") or "unknown")] += 1
            if review_task.get("db_import_ready") is True:
                db_import_ready_rows += 1
        if row.get("ocr_observation_count"):
            rows_with_ocr += 1
        if row.get("ingredient_candidate_count"):
            rows_with_llm += 1
            total_ingredient_candidates += int(row["ingredient_candidate_count"])
        if row.get("pii_screening_status") == "pending_local_screening":
            pii_pending_review_rows += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_name": input_path.name,
        "row_count": len(rows),
        "review_required_rows": len(rows),
        "db_import_ready_rows": db_import_ready_rows,
        "rows_with_ocr_observations": rows_with_ocr,
        "rows_with_llm_ingredient_candidates": rows_with_llm,
        "total_ingredient_candidates": total_ingredient_candidates,
        "pii_pending_review_rows": pii_pending_review_rows,
        "category_counts": dict(sorted(category_counts.items())),
        "section_counts": dict(sorted(section_counts.items())),
        "review_status_counts": dict(sorted(status_counts.items())),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
    }


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
        "review_required_rows": 0,
        "db_import_ready_rows": 0,
        "rows_with_ocr_observations": 0,
        "rows_with_llm_ingredient_candidates": 0,
        "total_ingredient_candidates": 0,
        "pii_pending_review_rows": 0,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _review_row_from_input_row(
    row: dict[str, object],
    *,
    source_run_id: str | None,
) -> dict[str, object]:
    """Convert one merged DB-labeling row into a review UI task."""
    _reject_unsafe_payload(row)
    if row.get("schema_version") != EXPECTED_INPUT_SCHEMA_VERSION:
        raise ValueError("Review ingest input rows must use DB-labeling-with-OCR schema.")

    fixture_id = _required_str(row, "fixture_id")
    observation_summaries = _safe_observation_summaries(row.get("ocr_observation_summaries"))
    ingredient_candidates = _ingredient_candidates(observation_summaries)
    if _is_pii_pending_review(row) and ingredient_candidates:
        raise ValueError(f"PII-pending review row cannot expose LLM ingredients: {fixture_id}")

    blocked_reasons = _blocked_reasons(row, ingredient_candidates)
    review_reasons = _review_reasons(row, observation_summaries, ingredient_candidates)
    task_id = _review_task_id(
        fixture_id=fixture_id, image_sha256=_required_str(row, "image_sha256")
    )
    review_row: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "review_task_id": task_id,
        "fixture_id": fixture_id,
        "source": _optional_string(row.get("source")) or "naver_tampermonkey",
        "section": _optional_string(row.get("section")) or "unknown",
        "image": {
            "root_token": _optional_string(row.get("image_root_token")),
            "image_ref_hash": _optional_sha256(row.get("image_ref_hash")),
            "image_sha256": _optional_sha256(row.get("image_sha256")),
        },
        "product": {
            "product_id": _optional_string(row.get("product_id")),
            "product_dir_hash": _optional_sha256(row.get("product_dir_hash")),
        },
        "category_key": _required_safe_token(row, "category_key"),
        "category_display": {
            "ko": _optional_string(row.get("display_name_ko")),
            "en": _optional_string(row.get("display_name_en")),
        },
        "language_targets": _safe_token_list(row.get("language_targets")),
        "chronic_fixture_tags": _safe_token_list(row.get("chronic_fixture_tags")),
        "caution_tags": _safe_token_list(row.get("caution_tags")),
        "category_reference_urls": _safe_url_list(row.get("source_urls")),
        "contains_personal_data": row.get("contains_personal_data"),
        "pii_screening_status": _optional_safe_token(row.get("pii_screening_status")),
        "external_transfer_allowed": row.get("external_transfer_allowed") is True,
        "local_processing_allowed": row.get("local_processing_allowed") is True,
        "requires_human_review": True,
        "is_clinical_recommendation": False,
        "clinical_recommendation_forbidden": True,
        "ocr_observation_count": len(observation_summaries),
        "ocr_provider_summaries": observation_summaries,
        "ingredient_candidate_count": len(ingredient_candidates),
        "ingredient_candidates": ingredient_candidates,
        "review_task": {
            "status": "needs_human_review",
            "priority": "normal",
            "reasons": review_reasons,
            "db_import_ready": False,
            "blocked_reasons": blocked_reasons,
        },
    }
    if source_run_id:
        review_row["source_run_id"] = source_run_id
    _reject_unsafe_payload(review_row)
    return review_row


def _safe_observation_summaries(value: object) -> list[dict[str, object]]:
    """Return bounded OCR provider summaries for review display."""
    if not isinstance(value, list):
        return []
    summaries: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        _reject_unsafe_payload(item)
        summary: dict[str, object] = {
            "provider": _required_safe_token(item, "provider"),
            "status": _required_safe_token(item, "status"),
            "text_non_empty": item.get("text_non_empty") is True,
            "parser_success": item.get("parser_success") is True,
        }
        _copy_optional_int(item, summary, "char_count")
        _copy_optional_int(item, summary, "line_count")
        _copy_optional_float(item, summary, "latency_ms")
        _copy_optional_token(item, summary, "error_code")
        _copy_optional_token(item, summary, "text_hash")
        _copy_optional_token(item, summary, "llm_parse_status")
        _copy_optional_int(item, summary, "llm_parse_attempt_count")
        _copy_optional_int(item, summary, "llm_parse_retry_count")
        ingredients = _safe_ingredients(item.get("llm_parsed_ingredients"))
        if ingredients:
            summary["llm_parsed_ingredients"] = ingredients
            summary["llm_parsed_ingredient_count"] = len(ingredients)
        elif isinstance(item.get("llm_parsed_ingredient_count"), int):
            summary["llm_parsed_ingredient_count"] = max(
                0,
                min(MAX_INGREDIENTS_PER_TASK, int(item["llm_parsed_ingredient_count"])),
            )
        flags = _safe_token_list(item.get("pii_candidate_flags"))
        if flags:
            summary["pii_candidate_flags"] = flags
        warnings = _safe_token_list(item.get("warning_codes"))
        if warnings:
            summary["warning_codes"] = warnings
        summaries.append(summary)
    return summaries


def _ingredient_candidates(
    observation_summaries: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    """Flatten safe LLM ingredient candidates across provider observations."""
    candidates: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for observation in observation_summaries:
        provider = str(observation.get("provider") or "unknown")
        ingredients = observation.get("llm_parsed_ingredients")
        if not isinstance(ingredients, list):
            continue
        for ingredient in ingredients:
            if not isinstance(ingredient, dict):
                continue
            candidate = dict(ingredient)
            candidate["provider"] = provider
            key = (
                candidate.get("display_name"),
                candidate.get("nutrient_code"),
                candidate.get("amount"),
                candidate.get("unit"),
                provider,
            )
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
            if len(candidates) >= MAX_INGREDIENTS_PER_TASK:
                return candidates
    return candidates


def _safe_ingredients(value: object) -> list[dict[str, object]]:
    """Return review-safe ingredient candidate dictionaries."""
    if not isinstance(value, list):
        return []
    ingredients: list[dict[str, object]] = []
    for item in value[:MAX_INGREDIENTS_PER_TASK]:
        if not isinstance(item, dict):
            continue
        ingredient: dict[str, object] = {}
        display_name = _bounded_string(item.get("display_name"), max_length=MAX_TEXT_LENGTH)
        if display_name is not None:
            ingredient["display_name"] = display_name
        nutrient_code = _optional_safe_token(item.get("nutrient_code"))
        if nutrient_code is not None:
            ingredient["nutrient_code"] = nutrient_code
        amount = item.get("amount")
        if isinstance(amount, int | float):
            ingredient["amount"] = float(amount)
        unit = _bounded_string(item.get("unit"), max_length=32)
        if unit is not None:
            ingredient["unit"] = unit
        confidence = item.get("confidence")
        if isinstance(confidence, int | float):
            ingredient["confidence"] = max(0.0, min(1.0, float(confidence)))
        source = _optional_safe_token(item.get("source"))
        if source is not None:
            ingredient["source"] = source
        if ingredient:
            ingredients.append(ingredient)
    return ingredients


def _blocked_reasons(
    row: dict[str, object],
    ingredient_candidates: Sequence[dict[str, object]],
) -> list[str]:
    """Return reasons why this review task cannot be imported automatically."""
    reasons = ["human_review_required"]
    if row.get("contains_personal_data") is not False:
        reasons.append("pii_status_not_cleared")
    if row.get("pii_screening_status") == "pending_local_screening":
        reasons.append("pii_pending_local_screening")
    if not ingredient_candidates:
        reasons.append("ingredient_candidates_need_review")
    return sorted(set(reasons))


def _review_reasons(
    row: dict[str, object],
    observation_summaries: Sequence[dict[str, object]],
    ingredient_candidates: Sequence[dict[str, object]],
) -> list[str]:
    """Return operator-facing review reason tokens."""
    reasons = ["category_label_needs_human_review"]
    if observation_summaries:
        reasons.append("ocr_observation_available")
    if ingredient_candidates:
        reasons.append("llm_ingredient_candidates_available")
    if row.get("pii_screening_status") == "pending_local_screening":
        reasons.append("pii_screening_required")
    if row.get("external_transfer_allowed") is not True:
        reasons.append("external_transfer_not_allowed")
    return sorted(set(reasons))


def _read_input_rows(path: Path) -> list[dict[str, object]]:
    """Read merged DB-labeling JSONL rows and reject unsafe payloads."""
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


def _review_task_id(*, fixture_id: str, image_sha256: str) -> str:
    """Return a stable review task id from non-secret fixture identifiers."""
    return hashlib.sha256(f"{fixture_id}|{image_sha256}".encode()).hexdigest()


def _sha256_text(value: str) -> str:
    """Return SHA-256 for redacted path identifiers."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_error_code(exc: BaseException) -> str:
    """Return a non-sensitive CLI error code."""
    if isinstance(exc, OSError):
        return "local_file_error"
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


def _is_pii_pending_review(row: dict[str, object]) -> bool:
    """Return whether a review row still needs local PII clearance."""
    return (
        row.get("section") == "review"
        and row.get("contains_personal_data") is not False
        and row.get("pii_screening_status") == "pending_local_screening"
    )


def _copy_optional_int(source: dict[str, object], target: dict[str, object], key: str) -> None:
    """Copy a non-negative integer field if present."""
    value = source.get(key)
    if isinstance(value, int) and value >= 0:
        target[key] = value


def _copy_optional_float(source: dict[str, object], target: dict[str, object], key: str) -> None:
    """Copy a non-negative float field if present."""
    value = source.get(key)
    if isinstance(value, int | float) and value >= 0:
        target[key] = float(value)


def _copy_optional_token(source: dict[str, object], target: dict[str, object], key: str) -> None:
    """Copy a bounded token string field if present."""
    value = _optional_safe_token(source.get(key))
    if value is not None:
        target[key] = value


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Row requires string field: {key}")
    return value.strip()


def _required_safe_token(row: dict[str, object], key: str) -> str:
    """Return a required bounded token field."""
    value = _optional_safe_token(row.get(key))
    if value is None:
        raise ValueError(f"Row requires safe token field: {key}")
    return value


def _optional_safe_token(value: object) -> str | None:
    """Return a bounded token string or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if len(stripped) > MAX_TOKEN_LENGTH or not SAFE_TOKEN_PATTERN.fullmatch(stripped):
        raise ValueError(f"Unsafe token value: {stripped[:MAX_TOKEN_LENGTH]}")
    return stripped


def _optional_string(value: object) -> str | None:
    """Return a stripped optional string."""
    return _bounded_string(value, max_length=MAX_TEXT_LENGTH)


def _bounded_string(value: object, *, max_length: int) -> str | None:
    """Return a stripped bounded string while rejecting local path literals."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    return stripped[:max_length]


def _optional_sha256(value: object) -> str | None:
    """Return a SHA-256 hex string or None."""
    if not isinstance(value, str):
        return None
    stripped = value.strip().lower()
    if len(stripped) == SHA256_HEX_LENGTH and all(char in "0123456789abcdef" for char in stripped):
        return stripped
    return None


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


def _safe_url_list(value: object) -> list[str]:
    """Return bounded HTTP(S) reference URLs."""
    if not isinstance(value, list):
        return []
    urls: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        url = item.strip()
        if len(url) > MAX_URL_LENGTH:
            continue
        if url.startswith(("https://", "http://")):
            urls.append(url)
    return sorted(set(urls))


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


if __name__ == "__main__":
    main()
