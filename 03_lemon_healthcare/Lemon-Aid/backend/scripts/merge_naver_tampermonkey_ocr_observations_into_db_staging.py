"""Merge redacted OCR observations into Naver Tampermonkey DB staging rows.

This script is an opt-in bridge between the folder/category DB-labeling staging
artifact and OCR/Ollama observation artifacts. It never reads or writes raw OCR
text, provider payloads, request headers, image bytes, raw model responses, or
secrets. Only bounded observation metadata and schema-validated ingredient
candidates are carried forward.
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

SCHEMA_VERSION = "naver-tampermonkey-db-labeling-with-ocr-v1"
EXPECTED_STAGING_SCHEMA_VERSION = "naver-tampermonkey-db-labeling-staging-v1"
MAX_TOKEN_LENGTH = 80
MAX_INGREDIENTS_PER_OBSERVATION = 64
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
    """Parse command-line arguments for the OCR observation merge."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--observations", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument(
        "--allow-unmatched-observations",
        action="store_true",
        help="Ignore observations whose fixture_id is absent from staging rows.",
    )
    return parser.parse_args()


def main() -> None:
    """Merge staging and observation rows from CLI arguments."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    staging_path = args.staging.expanduser().resolve()
    observation_paths = [path.expanduser().resolve() for path in args.observations]
    try:
        merged_rows, summary = merge_staging_with_observations(
            staging_path=staging_path,
            observation_paths=observation_paths,
            allow_unmatched_observations=args.allow_unmatched_observations,
        )
        _reject_raw_fields({"rows": merged_rows, "summary": summary})
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in merged_rows
            ),
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
            staging_path=staging_path,
            observation_paths=observation_paths,
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


def merge_staging_with_observations(
    *,
    staging_path: Path,
    observation_paths: Sequence[Path],
    allow_unmatched_observations: bool = False,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Merge redacted observation summaries into DB-labeling staging rows.

    Args:
        staging_path: DB-labeling staging JSONL path.
        observation_paths: One or more collector observation JSONL paths.
        allow_unmatched_observations: Whether to ignore observations absent from
            the staging fixture set.

    Returns:
        Merged staging rows and a redacted summary.

    Raises:
        ValueError: If raw fields are present, fixture ids do not match, or a
            PII-pending review row carries LLM ingredient output.
    """
    staging_rows = _read_jsonl_objects(staging_path)
    observation_rows = _read_observation_rows(observation_paths)
    staging_by_fixture = _index_staging_rows(staging_rows)
    observations_by_fixture: dict[str, list[dict[str, object]]] = {}
    unmatched_observation_count = 0
    for observation in observation_rows:
        fixture_id = _required_str(observation, "fixture_id")
        if fixture_id not in staging_by_fixture:
            unmatched_observation_count += 1
            if not allow_unmatched_observations:
                raise ValueError(f"OCR observation fixture_id is not in staging rows: {fixture_id}")
            continue
        observations_by_fixture.setdefault(fixture_id, []).append(observation)

    merged_rows: list[dict[str, object]] = []
    provider_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    rows_with_ocr = 0
    rows_with_llm = 0
    matched_observation_count = 0
    for row in staging_rows:
        fixture_id = _required_str(row, "fixture_id")
        observations = observations_by_fixture.get(fixture_id, [])
        observation_summaries = [
            _summarize_observation(observation, staging_row=row) for observation in observations
        ]
        matched_observation_count += len(observation_summaries)
        for summary in observation_summaries:
            provider_counts[str(summary["provider"])] += 1
            status_counts[str(summary["status"])] += 1
        merged_row = dict(row)
        merged_row["schema_version"] = SCHEMA_VERSION
        merged_row["ocr_observation_summaries"] = observation_summaries
        merged_row["ocr_observation_count"] = len(observation_summaries)
        if observation_summaries:
            rows_with_ocr += 1
        if any(summary.get("llm_parsed_ingredient_count", 0) for summary in observation_summaries):
            rows_with_llm += 1
        merged_rows.append(merged_row)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "staging_name": staging_path.name,
        "observation_file_count": len(observation_paths),
        "staging_row_count": len(staging_rows),
        "observation_count": len(observation_rows),
        "matched_observation_count": matched_observation_count,
        "unmatched_observation_count": unmatched_observation_count,
        "rows_with_ocr_observations": rows_with_ocr,
        "rows_with_llm_ingredients": rows_with_llm,
        "provider_counts": dict(sorted(provider_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
    }
    _reject_raw_fields({"rows": merged_rows, "summary": summary})
    return merged_rows, summary


def _failure_summary(
    *,
    staging_path: Path,
    observation_paths: Sequence[Path],
    output_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary without filesystem literals."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "staging_name": staging_path.name,
        "staging_path_hash": _sha256_text(str(staging_path.expanduser())),
        "observation_file_count": len(observation_paths),
        "observation_names": [path.name for path in observation_paths],
        "observation_path_hashes": [
            _sha256_text(str(path.expanduser())) for path in observation_paths
        ],
        "output_name": output_path.name,
        "output_path_hash": _sha256_text(str(output_path.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "staging_row_count": 0,
        "observation_count": 0,
        "matched_observation_count": 0,
        "unmatched_observation_count": 0,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_raw_fields(summary)
    return summary


def _summarize_observation(
    observation: dict[str, object],
    *,
    staging_row: dict[str, object],
) -> dict[str, object]:
    """Return a DB-safe observation summary for one fixture/provider row."""
    _reject_raw_fields(observation)
    provider = _required_safe_token(observation, "provider")
    status = _required_safe_token(observation, "status")
    llm_status = _optional_safe_token(observation.get("llm_parse_status"))
    ingredients = _safe_ingredients(observation.get("llm_parsed_ingredients"))
    if _is_pii_pending_review(staging_row) and ingredients:
        raise ValueError(
            f"PII-pending review fixture cannot carry LLM ingredients: {staging_row.get('fixture_id')}"
        )

    row: dict[str, object] = {
        "provider": provider,
        "status": status,
        "text_non_empty": observation.get("text_non_empty") is True,
        "parser_success": observation.get("parser_success") is True,
    }
    _copy_optional_int(observation, row, "char_count")
    _copy_optional_int(observation, row, "line_count")
    _copy_optional_float(observation, row, "latency_ms")
    _copy_optional_token(observation, row, "error_code")
    _copy_optional_token(observation, row, "text_hash")
    if llm_status is not None:
        row["llm_parse_status"] = llm_status
    _copy_optional_int(observation, row, "llm_parse_attempt_count")
    _copy_optional_int(observation, row, "llm_parse_retry_count")
    if ingredients:
        row["llm_parsed_ingredients"] = ingredients
        row["llm_parsed_ingredient_count"] = len(ingredients)
    elif isinstance(observation.get("llm_parsed_ingredient_count"), int):
        row["llm_parsed_ingredient_count"] = max(
            0,
            min(MAX_INGREDIENTS_PER_OBSERVATION, int(observation["llm_parsed_ingredient_count"])),
        )
    flags = _safe_token_list(observation.get("pii_candidate_flags"))
    if flags:
        row["pii_candidate_flags"] = flags
    warnings = _safe_token_list(observation.get("warning_codes"))
    if warnings:
        row["warning_codes"] = warnings
    return row


def _safe_ingredients(value: object) -> list[dict[str, object]]:
    """Return DB-safe ingredient candidate dictionaries from observation output."""
    if not isinstance(value, list):
        return []
    ingredients: list[dict[str, object]] = []
    for item in value[:MAX_INGREDIENTS_PER_OBSERVATION]:
        if not isinstance(item, dict):
            continue
        ingredient: dict[str, object] = {}
        display_name = _optional_string(item.get("display_name"))
        if display_name is not None:
            ingredient["display_name"] = display_name
        nutrient_code = _optional_safe_token(item.get("nutrient_code"))
        if nutrient_code is not None:
            ingredient["nutrient_code"] = nutrient_code
        amount = item.get("amount")
        if isinstance(amount, int | float):
            ingredient["amount"] = float(amount)
        unit = _optional_string(item.get("unit"))
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


def _read_observation_rows(paths: Sequence[Path]) -> list[dict[str, object]]:
    """Read observation JSONL files and reject raw fields."""
    rows: list[dict[str, object]] = []
    for path in paths:
        rows.extend(_read_jsonl_objects(path))
    return rows


def _read_jsonl_objects(path: Path) -> list[dict[str, object]]:
    """Read JSONL objects from disk and reject forbidden raw keys."""
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL rows must be objects.")
        _reject_raw_fields(row)
        rows.append(row)
    return rows


def _index_staging_rows(rows: Sequence[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Return staging rows indexed by fixture id."""
    indexed: dict[str, dict[str, object]] = {}
    for row in rows:
        _reject_raw_fields(row)
        if row.get("schema_version") != EXPECTED_STAGING_SCHEMA_VERSION:
            raise ValueError("Input staging rows must use the DB-labeling staging schema.")
        fixture_id = _required_str(row, "fixture_id")
        if fixture_id in indexed:
            raise ValueError(f"Duplicate staging fixture_id: {fixture_id}")
        indexed[fixture_id] = row
    return indexed


def _is_pii_pending_review(row: dict[str, object]) -> bool:
    """Return whether a row is a review fixture pending local PII clearance."""
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
    if any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
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
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    return stripped


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


def _reject_raw_fields(value: object) -> None:
    """Reject raw OCR/image/provider/model fields before writing artifacts."""
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
            _reject_raw_fields(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_raw_fields(item)
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
