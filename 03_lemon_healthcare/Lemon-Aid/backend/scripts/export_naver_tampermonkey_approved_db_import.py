"""Export approved Naver Tampermonkey review tasks for DB import.

This script is the narrow handoff after the review UI. It reads
``naver-tampermonkey-review-ingest-v1`` rows and exports only rows with an
explicit human ``review_decision.status=approved`` plus safety attestations.
Unapproved rows are skipped by default, and no database write is performed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import validate_naver_tampermonkey_review_decisions as validator  # noqa: E402

SCHEMA_VERSION = "naver-tampermonkey-approved-db-import-v1"
EXPECTED_INPUT_SCHEMA_VERSION = "naver-tampermonkey-review-ingest-v1"
SOURCE_MANIFEST_VERSION = "naver-tm-review-ingest-v1"
MAX_TOKEN_LENGTH = 80
MAX_TEXT_LENGTH = 200
MAX_INGREDIENTS_PER_PRODUCT = 128
APPROVED_INGREDIENT_SOURCE = "human_reviewed"
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
OPERATOR_REVIEWER_ID_PATTERN = re.compile(r"^operator_[A-Za-z0-9_.:-]{1,71}$")
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
    """Parse command-line arguments for the approved DB import exporter."""
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
        "--require-all-approved",
        action="store_true",
        help="Fail if any input row is not approved for DB import.",
    )
    return parser.parse_args()


def main() -> None:
    """Write approved DB import rows and a redacted summary."""
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = export_approved_db_import_rows(
            input_path=input_path,
            require_all_approved=args.require_all_approved,
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


def export_approved_db_import_rows(
    *,
    input_path: Path,
    require_all_approved: bool = False,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return DB import candidates approved by human review.

    Args:
        input_path: Review ingest JSONL path.
        require_all_approved: Whether to fail when any row is unapproved.

    Returns:
        Approved import candidate rows and a redacted summary.

    Raises:
        ValueError: If a row has unsafe payloads, wrong schema, unsafe approval
            metadata, uncleared PII, or unapproved rows while
            ``require_all_approved`` is set.
    """
    input_rows = _read_input_rows(input_path)
    approved_rows: list[dict[str, object]] = []
    skipped_unapproved = 0
    skipped_rejected = 0
    for row in input_rows:
        decision = row.get("review_decision")
        if not isinstance(decision, dict):
            skipped_unapproved += 1
            continue
        status = _optional_safe_token(decision.get("status"))
        if status != "approved":
            if status == "rejected":
                skipped_rejected += 1
            else:
                skipped_unapproved += 1
            continue
        approved_rows.append(_approved_import_row(row, decision=decision))

    if require_all_approved and len(approved_rows) != len(input_rows):
        raise ValueError(
            "All review ingest rows must be approved when --require-all-approved is set."
        )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_name": input_path.name,
        "input_row_count": len(input_rows),
        "approved_row_count": len(approved_rows),
        "skipped_unapproved_count": skipped_unapproved,
        "skipped_rejected_count": skipped_rejected,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload({"rows": approved_rows, "summary": summary})
    return approved_rows, summary


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
        "input_row_count": 0,
        "approved_row_count": 0,
        "skipped_unapproved_count": 0,
        "skipped_rejected_count": 0,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _approved_import_row(
    row: dict[str, object],
    *,
    decision: dict[str, object],
) -> dict[str, object]:
    """Convert one approved review row into a DB import candidate."""
    _reject_unsafe_payload({"row": row, "decision": decision})
    validator.reject_executable_text_payload(decision)
    if row.get("schema_version") != EXPECTED_INPUT_SCHEMA_VERSION:
        raise ValueError("Approved import input rows must use review ingest schema.")
    fixture_id = _required_str(row, "fixture_id")
    if row.get("contains_personal_data") is not False:
        raise ValueError(f"Approved DB import requires PII clearance: {fixture_id}")
    _require_attestation(decision, "attest_pii_screening_completed")
    _require_attestation(decision, "attest_no_raw_ocr_text")
    _require_attestation(decision, "attest_not_clinical_recommendation")

    ingredients = _approved_ingredients(decision.get("ingredients"))
    if not ingredients:
        raise ValueError(f"Approved DB import requires reviewed ingredients: {fixture_id}")
    display_name = _required_bounded_string(decision, "display_name")
    reviewer_id = _required_operator_reviewer_id(decision)
    reviewed_at = _required_timezone_aware_iso_datetime(decision, "reviewed_at")
    category_key = _optional_safe_token(decision.get("category_key")) or _required_safe_token(
        row, "category_key"
    )
    source_product_id = _source_product_id(row)
    import_row = {
        "schema_version": SCHEMA_VERSION,
        "source_provider": "naver_tampermonkey_review",
        "source_product_id": source_product_id,
        "product_name": display_name,
        "normalized_product_name": _normalize_text(display_name),
        "manufacturer": _optional_string(decision.get("manufacturer")),
        "category": category_key,
        "source_manifest_version": SOURCE_MANIFEST_VERSION,
        "is_active": True,
        "is_clinical_recommendation": False,
        "clinical_recommendation_forbidden": True,
        "source_payload": {
            "fixture_id": fixture_id,
            "review_task_id": _required_str(row, "review_task_id"),
            "image_sha256": _nested_string(row, "image", "image_sha256"),
            "image_ref_hash": _nested_string(row, "image", "image_ref_hash"),
            "language_targets": _safe_token_list(row.get("language_targets")),
            "chronic_fixture_tags": _safe_token_list(row.get("chronic_fixture_tags")),
            "caution_tags": _safe_token_list(row.get("caution_tags")),
            "reviewer_id": reviewer_id,
            "reviewed_at": reviewed_at,
            "ocr_observation_count": _non_negative_int(row.get("ocr_observation_count")),
            "ingredient_candidate_count": _non_negative_int(row.get("ingredient_candidate_count")),
        },
        "ingredients": [
            {
                **ingredient,
                "sort_order": index,
                "source_payload": {
                    "reviewer_id": reviewer_id,
                    "reviewed_at": reviewed_at,
                    "source_review_task_id": _required_str(row, "review_task_id"),
                },
            }
            for index, ingredient in enumerate(ingredients)
        ],
        "import_gate": {
            "ready_for_db_import": True,
            "human_review_approved": True,
            "pii_screening_completed": True,
        },
    }
    _reject_unsafe_payload(import_row)
    return import_row


def _approved_ingredients(value: object) -> list[dict[str, object]]:
    """Return reviewed ingredient rows compatible with reference-product import."""
    if not isinstance(value, list):
        return []
    ingredients: list[dict[str, object]] = []
    seen_ingredient_keys: set[tuple[str, str]] = set()
    for item in value[:MAX_INGREDIENTS_PER_PRODUCT]:
        if not isinstance(item, dict):
            continue
        display_name = _required_bounded_string(item, "display_name", max_length=160)
        validator.reject_packaging_quantity_ingredient_name(display_name)
        nutrient_code = _optional_safe_token(item.get("nutrient_code"))
        dedupe_key = (_normalize_text(display_name), nutrient_code or "")
        if dedupe_key in seen_ingredient_keys:
            raise ValueError("Approved DB import ingredients must be unique per product.")
        seen_ingredient_keys.add(dedupe_key)
        ingredient: dict[str, object] = {
            "standard_name": display_name,
            "nutrient_code": nutrient_code,
            "amount": _approved_ingredient_amount(item.get("amount")),
            "unit": _optional_string(item.get("unit"), max_length=40),
            "source": _approved_ingredient_source(item.get("source")),
        }
        ingredients.append({key: val for key, val in ingredient.items() if val is not None})
    return ingredients


def _read_input_rows(path: Path) -> list[dict[str, object]]:
    """Read review ingest JSONL rows and reject unsafe payloads."""
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


def _source_product_id(row: dict[str, object]) -> str:
    """Return a stable source product id for the approved import row."""
    review_task_id = _required_str(row, "review_task_id")
    fixture_id = _required_str(row, "fixture_id")
    image_sha256 = _nested_string(row, "image", "image_sha256") or ""
    return hashlib.sha256(f"{review_task_id}|{fixture_id}|{image_sha256}".encode()).hexdigest()


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


def _require_attestation(row: dict[str, object], key: str) -> None:
    """Require an explicit true safety attestation."""
    if row.get(key) is not True:
        raise ValueError(f"Approved DB import requires attestation: {key}")


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


def _required_operator_reviewer_id(row: dict[str, object]) -> str:
    """Return a reviewer id that represents an operator, not a model."""
    reviewer_id = _required_safe_token(row, "reviewer_id")
    if not OPERATOR_REVIEWER_ID_PATTERN.fullmatch(reviewer_id):
        raise ValueError("reviewer_id must use the operator_ prefix.")
    return reviewer_id


def _required_timezone_aware_iso_datetime(row: dict[str, object], key: str) -> str:
    """Return a required timezone-aware ISO datetime string."""
    value = _required_bounded_string(row, key)
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Row requires timezone-aware ISO datetime field: {key}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Row requires timezone-aware ISO datetime field: {key}")
    return value


def _optional_safe_token(value: object) -> str | None:
    """Return a bounded token string or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if len(stripped) > MAX_TOKEN_LENGTH or not SAFE_TOKEN_PATTERN.fullmatch(stripped):
        raise ValueError(f"Unsafe token value: {stripped[:MAX_TOKEN_LENGTH]}")
    return stripped


def _required_bounded_string(
    row: dict[str, object],
    key: str,
    *,
    max_length: int = MAX_TEXT_LENGTH,
) -> str:
    """Return a required bounded string field."""
    value = _optional_string(row.get(key), max_length=max_length)
    if value is None:
        raise ValueError(f"Row requires string field: {key}")
    return value


def _optional_string(value: object, *, max_length: int = MAX_TEXT_LENGTH) -> str | None:
    """Return a stripped bounded string while rejecting local path literals."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    validator.reject_executable_text_value(stripped)
    return stripped[:max_length]


def _optional_non_negative_number(value: object) -> float | None:
    """Return a non-negative number or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float) and value >= 0:
        return float(value)
    return None


def _approved_ingredient_amount(value: object) -> float | None:
    """Return an approved ingredient amount or reject malformed values."""
    if value is None:
        return None
    amount = _optional_non_negative_number(value)
    if amount is None:
        raise ValueError("Approved DB import ingredient amount must be a non-negative number.")
    return amount


def _approved_ingredient_source(value: object) -> str:
    """Return the only source allowed for approved human-review ingredients."""
    source = _optional_safe_token(value)
    if source is not None and source != APPROVED_INGREDIENT_SOURCE:
        raise ValueError("Approved DB import ingredient source must be human_reviewed.")
    return APPROVED_INGREDIENT_SOURCE


def _non_negative_int(value: object) -> int:
    """Return a non-negative integer, defaulting missing values to zero."""
    return value if isinstance(value, int) and value >= 0 else 0


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


def _nested_string(row: dict[str, object], object_key: str, value_key: str) -> str | None:
    """Return a nested string field if present."""
    value = row.get(object_key)
    if not isinstance(value, dict):
        return None
    return _optional_string(value.get(value_key))


def _normalize_text(value: str) -> str:
    """Return a conservative lookup key for reviewed supplement names."""
    return " ".join(value.casefold().split())[:MAX_TEXT_LENGTH]


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
