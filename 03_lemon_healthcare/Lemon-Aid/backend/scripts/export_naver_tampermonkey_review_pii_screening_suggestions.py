"""Export non-importable model suggestions for review-image PII screening.

The script reads a local-only review PII screening manifest and an optional
model-generated suggestion JSONL. Suggestions are kept separate from operator
decisions: they cannot contain reviewer ids, attestation fields, decision
payloads, raw OCR text, raw model responses, local paths, or free-text notes.
The output is a sanitized suggestion artifact only. It never clears an image for
OCR, never writes to a database, never calls OCR/LLM providers, and never permits
external transfer.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import (  # noqa: E402
    build_naver_tampermonkey_review_pii_screening_manifest as pii_manifest,
)

SCHEMA_VERSION = "naver-tampermonkey-review-pii-screening-suggestions-v1"
EXPECTED_MANIFEST_SCHEMA_VERSION = pii_manifest.SCHEMA_VERSION
SUGGESTION_FIELD = "pii_screening_suggestion"
ALLOWED_SUGGESTION_STATUSES = frozenset(
    {
        "likely_clear",
        "possible_personal_data",
        "needs_operator_review",
        "image_unreadable",
    }
)
ALLOWED_CONFIDENCE_BUCKETS = frozenset({"low", "medium", "high"})
ALLOWED_TOP_LEVEL_KEYS = frozenset({"fixture_id", SUGGESTION_FIELD})
ALLOWED_SUGGESTION_KEYS = frozenset(
    {
        "model_id",
        "generated_at",
        "status_suggestion",
        "confidence_bucket",
        "evidence_codes",
        "reason_codes",
    }
)
DECISION_LIKE_KEYS = frozenset(
    {
        "pii_screening_decision",
        "review_decision",
        "reviewer_id",
        "reviewed_at",
        "status",
    }
)
FREE_TEXT_KEYS = frozenset({"comment", "comments", "note", "notes", "review_note"})
RAW_FORBIDDEN_KEYS = pii_manifest.RAW_FORBIDDEN_KEYS
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
MAX_STRING_FIELD_LENGTH = 240


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for suggestion export."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--suggestions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument("--allow-unmatched-suggestions", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Write sanitized PII screening suggestion rows and a summary."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = export_review_pii_screening_suggestions(
            manifest_path=args.manifest.expanduser().resolve(),
            suggestions_path=args.suggestions.expanduser().resolve(),
            allow_unmatched_suggestions=args.allow_unmatched_suggestions,
        )
    except (OSError, ValueError) as exc:
        failure = _failure_summary(
            manifest_path=args.manifest,
            suggestions_path=args.suggestions,
            error=exc,
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def export_review_pii_screening_suggestions(
    *,
    manifest_path: Path,
    suggestions_path: Path,
    allow_unmatched_suggestions: bool = False,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return sanitized suggestion rows and a redacted summary.

    Args:
        manifest_path: Local-only review PII screening manifest.
        suggestions_path: Model-generated suggestion JSONL.
        allow_unmatched_suggestions: Whether extra suggestion ids are ignored.

    Returns:
        Sanitized non-importable suggestion rows and summary.

    Raises:
        ValueError: If suggestions look like operator decisions or contain unsafe
            fields.
    """
    manifest_rows = _read_manifest_rows(manifest_path)
    suggestions = _read_suggestion_rows(suggestions_path)
    manifest_ids = {_required_str(row, "fixture_id") for row in manifest_rows}
    unmatched_ids = sorted(set(suggestions) - manifest_ids)
    if unmatched_ids and not allow_unmatched_suggestions:
        raise ValueError(f"PII suggestion fixture_id is not in manifest: {unmatched_ids[0]}")

    exported_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    pending_count = 0
    for manifest_row in manifest_rows:
        fixture_id = _required_str(manifest_row, "fixture_id")
        suggestion = suggestions.get(fixture_id)
        if suggestion is None:
            pending_count += 1
            continue
        exported = _suggestion_row(manifest_row, suggestion=suggestion)
        exported_rows.append(exported)
        status_counts[str(exported["status_suggestion"])] += 1
        confidence_counts[str(exported["confidence_bucket"])] += 1

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_name": manifest_path.name,
        "suggestions_name": suggestions_path.name,
        "manifest_row_count": len(manifest_rows),
        "suggestion_row_count": len(suggestions),
        "exported_suggestion_count": len(exported_rows),
        "pending_without_suggestion_count": pending_count,
        "unmatched_suggestion_count": len(unmatched_ids),
        "status_suggestion_counts": dict(sorted(status_counts.items())),
        "confidence_bucket_counts": dict(sorted(confidence_counts.items())),
        "decision_importable_rows": 0,
        "operator_decision_required_rows": len(exported_rows),
        "external_transfer_allowed_rows": 0,
        "db_write_performed": False,
        "external_transfer_performed": False,
        "ocr_or_llm_call_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "free_text_notes_stored": False,
    }
    _reject_unsafe_payload({"rows": exported_rows, "summary": summary})
    return exported_rows, summary


def _failure_summary(
    *,
    manifest_path: Path,
    suggestions_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted suggestion export failure summary."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "manifest_name": manifest_path.name,
        "suggestions_name": suggestions_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "manifest_row_count": 0,
        "suggestion_row_count": 0,
        "exported_suggestion_count": 0,
        "pending_without_suggestion_count": 0,
        "unmatched_suggestion_count": 0,
        "status_suggestion_counts": {},
        "confidence_bucket_counts": {},
        "decision_importable_rows": 0,
        "operator_decision_required_rows": 0,
        "external_transfer_allowed_rows": 0,
        "db_write_performed": False,
        "external_transfer_performed": False,
        "ocr_or_llm_call_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "free_text_notes_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _suggestion_row(
    manifest_row: dict[str, object],
    *,
    suggestion: dict[str, object],
) -> dict[str, object]:
    """Return one sanitized suggestion row that cannot be imported as a decision."""
    status = _required_choice(
        suggestion,
        "status_suggestion",
        allowed=ALLOWED_SUGGESTION_STATUSES,
    )
    confidence = _required_choice(
        suggestion,
        "confidence_bucket",
        allowed=ALLOWED_CONFIDENCE_BUCKETS,
    )
    row = {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": _required_str(manifest_row, "fixture_id"),
        "source": "naver_tampermonkey",
        "section": "review",
        "image_ref_hash": _required_str(manifest_row, "image_ref_hash"),
        "category_key": _required_safe_token(manifest_row, "category_key"),
        "status_suggestion": status,
        "confidence_bucket": confidence,
        "evidence_codes": _safe_token_list(suggestion.get("evidence_codes")),
        "reason_codes": _safe_token_list(suggestion.get("reason_codes")),
        "model": {
            "model_id": _required_safe_token(suggestion, "model_id"),
            "generated_at": _required_str(suggestion, "generated_at"),
        },
        "decision_importable": False,
        "operator_decision_required": True,
        "contains_personal_data": None,
        "external_transfer_allowed": False,
        "local_processing_allowed": True,
        "raw_artifacts_stored": False,
        "raw_model_response_stored": False,
    }
    _reject_unsafe_payload(row)
    return row


def _read_manifest_rows(path: Path) -> list[dict[str, object]]:
    """Read local-only review PII screening manifest rows."""
    rows = _read_jsonl_objects(path)
    seen: set[str] = set()
    for row in rows:
        if row.get("schema_version") != EXPECTED_MANIFEST_SCHEMA_VERSION:
            raise ValueError("PII screening manifest rows use an unsupported schema.")
        if row.get("section") != "review" or row.get("external_transfer_allowed") is not False:
            raise ValueError("PII screening rows must remain local-only review rows.")
        fixture_id = _required_str(row, "fixture_id")
        if fixture_id in seen:
            raise ValueError(f"Duplicate fixture_id in PII manifest: {fixture_id}")
        seen.add(fixture_id)
    return rows


def _read_suggestion_rows(path: Path) -> dict[str, dict[str, object]]:
    """Read model suggestion rows keyed by fixture id."""
    suggestions: dict[str, dict[str, object]] = {}
    for row in _read_jsonl_objects(path):
        _reject_decision_like_payload(row)
        keys = {str(key).lower() for key in row}
        unexpected = sorted(keys - ALLOWED_TOP_LEVEL_KEYS)
        if unexpected:
            raise ValueError(f"PII suggestion row contains unsupported field: {unexpected[0]}")
        fixture_id = _required_str(row, "fixture_id")
        if fixture_id in suggestions:
            raise ValueError(f"Duplicate PII suggestion fixture_id: {fixture_id}")
        suggestion = row.get(SUGGESTION_FIELD)
        if not isinstance(suggestion, dict):
            raise ValueError(f"PII suggestion rows require object field: {SUGGESTION_FIELD}")
        _validate_suggestion(suggestion)
        suggestions[fixture_id] = dict(suggestion)
    return suggestions


def _validate_suggestion(suggestion: dict[str, object]) -> None:
    """Validate one model-generated PII screening suggestion."""
    _reject_unsafe_payload(suggestion)
    _reject_decision_like_payload(suggestion)
    keys = {str(key).lower() for key in suggestion}
    unexpected = sorted(keys - ALLOWED_SUGGESTION_KEYS)
    if unexpected:
        raise ValueError(f"PII suggestion contains unsupported field: {unexpected[0]}")
    _required_safe_token(suggestion, "model_id")
    _required_str(suggestion, "generated_at")
    _required_choice(suggestion, "status_suggestion", allowed=ALLOWED_SUGGESTION_STATUSES)
    _required_choice(suggestion, "confidence_bucket", allowed=ALLOWED_CONFIDENCE_BUCKETS)
    _safe_token_list(suggestion.get("evidence_codes"))
    _safe_token_list(suggestion.get("reason_codes"))


def _read_jsonl_objects(path: Path) -> list[dict[str, object]]:
    """Read JSONL object rows and reject unsafe payloads."""
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


def _required_choice(
    row: dict[str, object],
    key: str,
    *,
    allowed: frozenset[str],
) -> str:
    """Return a required safe token that must be one of ``allowed``."""
    value = _required_safe_token(row, key)
    if value not in allowed:
        raise ValueError(f"Unsupported PII suggestion {key}: {value}")
    return value


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required bounded string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Row requires string field: {key}")
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    if len(stripped) > MAX_STRING_FIELD_LENGTH:
        raise ValueError(f"String field is too long: {key}")
    return stripped


def _required_safe_token(row: dict[str, object], key: str) -> str:
    """Return a required safe token field."""
    token = _safe_token(row.get(key))
    if token is None:
        raise ValueError(f"Row requires safe token field: {key}")
    return token


def _safe_token(value: object) -> str | None:
    """Return a bounded token or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    if not SAFE_TOKEN_PATTERN.fullmatch(stripped):
        raise ValueError(f"Unsafe token value: {stripped[:80]}")
    return stripped


def _safe_token_list(value: object) -> list[str]:
    """Return a safe token list."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Token lists must be arrays.")
    tokens: list[str] = []
    for item in value:
        token = _safe_token(item)
        if token is None:
            raise ValueError("Token lists require non-empty safe string values.")
        tokens.append(token)
    return tokens


def _reject_decision_like_payload(value: object) -> None:
    """Reject fields that could be mistaken for an operator decision."""
    if isinstance(value, dict):
        keys = {str(key).lower() for key in value}
        forbidden = DECISION_LIKE_KEYS.intersection(keys)
        if forbidden:
            raise ValueError(
                f"PII suggestion cannot include decision field(s): {sorted(forbidden)}"
            )
        attestation_keys = sorted(key for key in keys if key.startswith("attest_"))
        if attestation_keys:
            raise ValueError(
                f"PII suggestion cannot include attestation field: {attestation_keys[0]}"
            )
        if FREE_TEXT_KEYS.intersection(keys):
            raise ValueError("PII suggestion cannot include free-text notes.")
        for nested in value.values():
            _reject_decision_like_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_decision_like_payload(item)


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys, product directory literals, and local paths."""
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
