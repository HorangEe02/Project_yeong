"""Validate review UI decisions before approved DB import export.

The validator reads ``naver-tampermonkey-review-ingest-v1`` rows and checks any
attached ``review_decision`` objects. It is intentionally read-only: no DB write,
no OCR call, and no artifact mutation. Pending rows are allowed by default so the
operator can validate an in-progress review queue.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "naver-tampermonkey-review-decision-validation-v1"
EXPECTED_INPUT_SCHEMA_VERSION = "naver-tampermonkey-review-ingest-v1"
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
ALLOWED_DECISION_STATUSES = frozenset({"approved", "rejected", "needs_changes"})
APPROVED_ATTESTATIONS = (
    "attest_pii_screening_completed",
    "attest_no_raw_ocr_text",
    "attest_not_clinical_recommendation",
)
PACKAGING_QUANTITY_INGREDIENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^(?:g|mg|kg|ml|l)\s*(?:x\s*)?\d*\s*(?:포|정|캡슐|캡셀|개입)?\s*\(?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\d+(?:[,.]\d+)?\s*(?:mg|g|kg|ml|l|mcg|μg|ug|㎍|iu|%)\s*\(?$",
        re.IGNORECASE,
    ),
    re.compile(r"^정\s*(?:x\s*)?\d*\s*(?:개입)?\s*\(?$", re.IGNORECASE),
    re.compile(
        r"^(?:1일|일일|하루|daily)?\s*\d+\s*"
        r"(?:정|포|캡슐|캡셀|개입|tablet|tablets|capsule|capsules|softgel|softgels|count)\s*\(?$",
        re.IGNORECASE,
    ),
)
EXECUTABLE_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"[\x00-\x1f\x7f]"),
    re.compile(r"[<>]"),
    re.compile(r"\b(?:javascript|data|vbscript)\s*:", re.IGNORECASE),
    re.compile(r"\b(?:https?://|www\.)", re.IGNORECASE),
)
FREE_TEXT_DECISION_KEYS = frozenset(
    {
        "comment",
        "comments",
        "free_text_note",
        "note",
        "notes",
        "raw_note",
        "review_note",
        "reviewer_note",
    }
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
    """Parse command-line arguments for review decision validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. When omitted, only stdout is written.",
    )
    parser.add_argument(
        "--require-reviewed",
        action="store_true",
        help="Fail when rows are still missing review_decision.",
    )
    return parser.parse_args()


def main() -> None:
    """Validate review decisions and write a redacted summary."""
    args = parse_args()
    try:
        summary = validate_review_decisions(
            input_path=args.input.expanduser().resolve(),
            require_reviewed=args.require_reviewed,
        )
    except (OSError, ValueError) as exc:
        summary = _failure_summary(
            input_path=args.input,
            require_reviewed=args.require_reviewed,
            error=exc,
        )
        if args.summary is not None:
            summary_path = args.summary.expanduser().resolve()
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None
    if args.summary is not None:
        summary_path = args.summary.expanduser().resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def validate_review_decisions(
    *,
    input_path: Path,
    require_reviewed: bool = False,
) -> dict[str, object]:
    """Validate review UI decision payloads.

    Args:
        input_path: Review ingest JSONL path.
        require_reviewed: Whether every row must include a decision.

    Returns:
        Redacted validation summary.

    Raises:
        ValueError: If any decision is unsafe, malformed, or violates approval
            gates.
    """
    rows = _read_rows(input_path)
    status_counts: Counter[str] = Counter()
    pending_count = 0
    approved_ingredient_count = 0
    for row in rows:
        _validate_row_schema(row)
        decision = row.get("review_decision")
        if decision is None:
            pending_count += 1
            status_counts["pending"] += 1
            continue
        if not isinstance(decision, dict):
            raise ValueError("review_decision must be an object.")
        status = _validate_decision(row, decision)
        status_counts[status] += 1
        if status == "approved":
            approved_ingredient_count += len(decision.get("ingredients", []))  # type: ignore[arg-type]

    if require_reviewed and pending_count:
        raise ValueError("Review decision validation requires every row to be reviewed.")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_name": input_path.name,
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
    _reject_unsafe_payload(summary)
    return summary


def _failure_summary(
    *,
    input_path: Path,
    require_reviewed: bool,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted validation failure summary for CLI errors."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "input_name": input_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "require_reviewed": require_reviewed,
        "row_count": 0,
        "pending_count": 0,
        "decision_status_counts": {},
        "approved_ingredient_count": 0,
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


def _validate_row_schema(row: dict[str, object]) -> None:
    """Validate the review ingest row envelope."""
    _reject_unsafe_payload(row)
    if row.get("schema_version") != EXPECTED_INPUT_SCHEMA_VERSION:
        raise ValueError("Review decision input rows must use review ingest schema.")
    if row.get("requires_human_review") is not True:
        raise ValueError("Review ingest rows must require human review.")
    if row.get("is_clinical_recommendation") is not False:
        raise ValueError("Review ingest rows must not be clinical recommendations.")
    if row.get("clinical_recommendation_forbidden") is not True:
        raise ValueError("Review ingest rows must keep clinical recommendation forbidden.")


def _validate_decision(row: dict[str, object], decision: dict[str, object]) -> str:
    """Validate one review decision object and return its status."""
    _reject_unsafe_payload(decision)
    reject_executable_text_payload(decision)
    _reject_free_text_notes(decision)
    status = _required_safe_token(decision, "status")
    if status not in ALLOWED_DECISION_STATUSES:
        raise ValueError(f"Unsupported review decision status: {status}")
    _required_operator_reviewer_id(decision)
    _required_timezone_aware_iso_datetime(decision, "reviewed_at")
    if status == "approved":
        _validate_approved_decision(row, decision)
    else:
        reason_codes = _safe_token_list(decision.get("reason_codes"))
        if not reason_codes:
            raise ValueError(f"{status} review decisions require reason_codes.")
        if decision.get("ingredients"):
            raise ValueError(f"{status} review decisions cannot include import ingredients.")
    return status


def _validate_approved_decision(row: dict[str, object], decision: dict[str, object]) -> None:
    """Validate approval-only safety gates and reviewed ingredients."""
    if row.get("contains_personal_data") is not False:
        raise ValueError("Approved review decisions require PII clearance.")
    for key in APPROVED_ATTESTATIONS:
        if decision.get(key) is not True:
            raise ValueError(f"Approved review decision requires attestation: {key}")
    _required_string(decision, "display_name")
    ingredients = decision.get("ingredients")
    if not isinstance(ingredients, list) or not ingredients:
        raise ValueError("Approved review decisions require reviewed ingredients.")
    if len(ingredients) > MAX_INGREDIENTS_PER_PRODUCT:
        raise ValueError("Approved review decision has too many ingredients.")
    seen_ingredient_keys: set[tuple[str, str]] = set()
    for ingredient in ingredients:
        if not isinstance(ingredient, dict):
            raise ValueError("Approved review ingredients must be objects.")
        _reject_unsafe_payload(ingredient)
        display_name = _required_string(ingredient, "display_name", max_length=160)
        reject_packaging_quantity_ingredient_name(display_name)
        nutrient_code = ingredient.get("nutrient_code")
        if nutrient_code is not None:
            nutrient_code = _safe_token(nutrient_code)
        dedupe_key = (_normalize_ingredient_name(display_name), nutrient_code or "")
        if dedupe_key in seen_ingredient_keys:
            raise ValueError("Approved review ingredients must be unique per product.")
        seen_ingredient_keys.add(dedupe_key)
        source = ingredient.get("source")
        if source is not None and _safe_token(source) != APPROVED_INGREDIENT_SOURCE:
            raise ValueError("Approved review ingredient source must be human_reviewed.")
        amount = ingredient.get("amount")
        if amount is not None and (
            isinstance(amount, bool) or not isinstance(amount, int | float) or amount < 0
        ):
            raise ValueError("Approved review ingredient amount must be a non-negative number.")
        unit = ingredient.get("unit")
        if unit is not None:
            _required_string(ingredient, "unit", max_length=40)


def _read_rows(path: Path) -> list[dict[str, object]]:
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


def _required_safe_token(row: dict[str, object], key: str) -> str:
    """Return a required bounded token field."""
    value = row.get(key)
    token = _safe_token(value)
    if token is None:
        raise ValueError(f"Row requires safe token field: {key}")
    return token


def _required_operator_reviewer_id(row: dict[str, object]) -> str:
    """Return a reviewer id that represents an operator, not a model."""
    reviewer_id = _required_safe_token(row, "reviewer_id")
    if not OPERATOR_REVIEWER_ID_PATTERN.fullmatch(reviewer_id):
        raise ValueError("reviewer_id must use the operator_ prefix.")
    return reviewer_id


def _required_timezone_aware_iso_datetime(row: dict[str, object], key: str) -> str:
    """Return a required timezone-aware ISO datetime string."""
    value = _required_string(row, key)
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Row requires timezone-aware ISO datetime field: {key}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Row requires timezone-aware ISO datetime field: {key}")
    return value


def _normalize_ingredient_name(value: str) -> str:
    """Return a conservative ingredient de-duplication key."""
    return " ".join(value.casefold().split())[:MAX_TEXT_LENGTH]


def reject_packaging_quantity_ingredient_name(value: str) -> None:
    """Reject package-count or dosage-only text masquerading as an ingredient.

    Args:
        value: Human-reviewed ingredient display name.

    Raises:
        ValueError: If the display name is only a packaging quantity, serving
            count, or dosage fragment rather than a nutritional ingredient.
    """
    if _looks_like_packaging_quantity_ingredient(value):
        raise ValueError("Approved review ingredient name must not be packaging quantity text.")


def reject_executable_text_payload(value: object) -> None:
    """Reject HTML, script-protocol, URL, or control-character text recursively.

    Args:
        value: Review decision payload or a bounded reviewed string.

    Raises:
        ValueError: If the payload contains text that could become executable
            when later rendered by an unsafe UI sink.
    """
    if isinstance(value, dict):
        for nested in value.values():
            reject_executable_text_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            reject_executable_text_payload(item)
    elif isinstance(value, str):
        reject_executable_text_value(value)


def reject_executable_text_value(value: str) -> None:
    """Reject one reviewed text value that looks executable or URL-like."""
    if any(pattern.search(value) for pattern in EXECUTABLE_TEXT_PATTERNS):
        raise ValueError("Reviewed text contains executable or URL-like content.")


def _looks_like_packaging_quantity_ingredient(value: str) -> bool:
    """Return whether text is package/count-only noise instead of an ingredient."""
    normalized = _normalize_ingredient_name(value).replace(chr(0xD7), "x")
    if not normalized:
        return False
    return any(pattern.fullmatch(normalized) for pattern in PACKAGING_QUANTITY_INGREDIENT_PATTERNS)


def _safe_token(value: object) -> str | None:
    """Return a bounded token string or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if len(stripped) > MAX_TOKEN_LENGTH or not SAFE_TOKEN_PATTERN.fullmatch(stripped):
        raise ValueError(f"Unsafe token value: {stripped[:MAX_TOKEN_LENGTH]}")
    return stripped


def _safe_token_list(value: object) -> list[str]:
    """Return sorted unique safe tokens from a list value."""
    if not isinstance(value, list):
        return []
    tokens: list[str] = []
    for item in value:
        token = _safe_token(item)
        if token is not None:
            tokens.append(token)
    return sorted(set(tokens))


def _required_string(
    row: dict[str, object],
    key: str,
    *,
    max_length: int = MAX_TEXT_LENGTH,
) -> str:
    """Return a required bounded string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Row requires string field: {key}")
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    reject_executable_text_value(stripped)
    if len(stripped) > max_length:
        raise ValueError(f"Row string field is too long: {key}")
    return stripped


def _reject_free_text_notes(value: dict[str, object]) -> None:
    """Reject free-text review notes that could accidentally store sensitive text."""
    keys = {str(key).lower() for key in value}
    forbidden = FREE_TEXT_DECISION_KEYS.intersection(keys)
    if forbidden:
        raise ValueError(f"Review decision contains free-text note field(s): {sorted(forbidden)}")


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
    """Return a non-sensitive CLI error code."""
    if isinstance(exc, OSError):
        return "local_file_read_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message without filesystem details."""
    if isinstance(exc, OSError):
        return "Local file read failed."
    message = str(exc).strip()
    if not message:
        return "Validation failed."
    if any(marker in message for marker in LOCAL_PATH_MARKERS):
        return "Validation failed."
    if "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


if __name__ == "__main__":
    main()
