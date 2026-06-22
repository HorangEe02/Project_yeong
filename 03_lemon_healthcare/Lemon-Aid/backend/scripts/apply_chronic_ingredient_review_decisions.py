"""Apply human-reviewed chronic ingredient decisions to V3 expected snapshots.

This operator tool converts a separate decision JSONL into a new expected/
snapshot directory. It never mutates the source expected directory in place.
Decision rows are strictly structured so raw OCR text, provider payloads, raw
model responses, local paths, free-text review notes, and secrets cannot enter
the generated ground-truth snapshots or summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPT_DIR.parent / "Nutrition-backend"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from src.models.schemas.supplement_snapshot import (  # noqa: E402
    SupplementParsedSnapshotV3,
)

SCHEMA_VERSION = "chronic-ingredient-review-decision-apply-v1"
DECISION_SCHEMA_VERSION = "chronic-ingredient-review-decision-v1"
DEFAULT_FIXTURE_PREFIX = "naver-chronic-"
DEFAULT_SNAPSHOT_VERSION = "v3"
REVIEWER_PATTERN = re.compile(r"^operator_[A-Za-z0-9_.-]{1,64}$")
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:+-]{1,120}$")
MAX_INGREDIENTS = 80
MAX_TEXT_LENGTH = 160
PENDING_REVIEW_WARNINGS = frozenset(
    {
        "auto_expected_requires_human_verification",
        "ground_truth_pending_human_review",
    }
)
NON_VERIFIED_WARNING_CODES = {
    "needs_changes": "human_review_needs_changes",
    "not_scoreable": "human_review_not_scoreable",
}
REQUIRED_ATTESTATIONS = frozenset(
    {
        "human_verified_from_local_fixture",
        "no_raw_ocr_text_copied",
        "no_provider_payload_copied",
        "no_secret_or_local_path_copied",
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
        "secret",
        "service_key",
    }
)
LITERAL_FORBIDDEN_KEYS = frozenset(
    {
        "api_token",
        "auth_header",
        "comment",
        "connection_string",
        "database_url",
        "db_url",
        "env",
        "free_text",
        "local_path",
        "note",
        "notes",
        "password",
        "review_note",
        "token",
    }
)
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
ALLOWED_VERIFICATION_STATUSES = frozenset({"verified", "needs_changes", "not_scoreable"})


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed CLI arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-dir", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output-dir>/apply-summary.json.",
    )
    parser.add_argument("--fixture-prefix", default=DEFAULT_FIXTURE_PREFIX)
    parser.add_argument("--snapshot-version", default=DEFAULT_SNAPSHOT_VERSION)
    parser.add_argument(
        "--allow-unmatched-decisions",
        action="store_true",
        help="Ignore decision rows whose fixture_id is not present in expected-dir.",
    )
    parser.add_argument(
        "--overwrite-output",
        action="store_true",
        help="Allow replacing existing output snapshot files.",
    )
    return parser.parse_args()


def main() -> None:
    """Apply chronic ingredient review decisions and write a redacted summary."""
    args = parse_args()
    expected_dir = args.expected_dir.expanduser().resolve()
    decisions_path = args.decisions.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_dir / "apply-summary.json"
    )
    try:
        outputs, summary = apply_chronic_ingredient_review_decisions(
            expected_dir=expected_dir,
            decisions_path=decisions_path,
            output_dir=output_dir,
            fixture_prefix=args.fixture_prefix,
            snapshot_version=args.snapshot_version,
            allow_unmatched_decisions=args.allow_unmatched_decisions,
        )
        _reject_unsafe_payload({"outputs": outputs, "summary": summary})
        _write_outputs(
            output_dir=output_dir,
            summary_path=summary_path,
            outputs=outputs,
            summary=summary,
            overwrite_output=args.overwrite_output,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            expected_dir=expected_dir,
            decisions_path=decisions_path,
            output_dir=output_dir,
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


def apply_chronic_ingredient_review_decisions(
    *,
    expected_dir: Path,
    decisions_path: Path,
    output_dir: Path,
    fixture_prefix: str = DEFAULT_FIXTURE_PREFIX,
    snapshot_version: str = DEFAULT_SNAPSHOT_VERSION,
    allow_unmatched_decisions: bool = False,
) -> tuple[dict[str, dict[str, Any]], dict[str, object]]:
    """Return V3 snapshots with human-reviewed ingredient decisions applied.

    Args:
        expected_dir: Source directory containing ``*.snapshot_v3.json`` files.
        decisions_path: JSONL file containing structured human-review decisions.
        output_dir: Planned output directory used only for redacted summary
            metadata; the pure function does not write files.
        fixture_prefix: Fixture id prefix to include.
        snapshot_version: Snapshot suffix to include, usually ``"v3"``.
        allow_unmatched_decisions: Whether decisions without a matching snapshot
            are ignored.

    Returns:
        Mapping of output snapshot file name to validated snapshot payload, and
        a redacted apply summary.

    Raises:
        ValueError: If decisions are malformed, unsafe, unmatched, or if output
            snapshots fail V3 schema validation.
    """
    if expected_dir.resolve() == output_dir.resolve():
        raise ValueError("Output directory must differ from source expected directory.")
    snapshot_paths = _snapshot_paths(
        expected_dir=expected_dir,
        fixture_prefix=fixture_prefix,
        snapshot_version=snapshot_version,
    )
    decisions = _read_decision_rows(decisions_path)
    fixture_ids = {_fixture_id_from_snapshot_name(path.name) for path in snapshot_paths}
    unmatched = sorted(set(decisions) - fixture_ids)
    if unmatched and not allow_unmatched_decisions:
        raise ValueError(f"Decision fixture_id is not in expected snapshots: {unmatched[0]}")

    status_counts: Counter[str] = Counter()
    outputs: dict[str, dict[str, Any]] = {}
    matched_count = 0
    pending_count = 0
    for path in snapshot_paths:
        fixture_id = _fixture_id_from_snapshot_name(path.name)
        snapshot = _read_snapshot(path)
        decision = decisions.get(fixture_id)
        if decision is None:
            pending_count += 1
            status_counts["pending"] += 1
            updated = snapshot
        else:
            matched_count += 1
            status = _required_status(decision)
            status_counts[status] += 1
            updated = _apply_decision(snapshot=snapshot, decision=decision, status=status)
            if _snapshot_requires_human_review(updated):
                pending_count += 1
        _validate_snapshot(updated)
        _reject_unsafe_payload(updated)
        outputs[path.name] = updated

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "expected_dir_name": expected_dir.name,
        "expected_dir_path_hash": _sha256_text(str(expected_dir.expanduser())),
        "decisions_name": decisions_path.name,
        "decisions_path_hash": _sha256_text(str(decisions_path.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_path_hash": _sha256_text(str(output_dir.expanduser())),
        "snapshot_version": snapshot_version,
        "fixture_prefix": fixture_prefix,
        "decision_row_count": len(decisions),
        "matched_decision_count": matched_count,
        "unmatched_decision_count": len(unmatched),
        "verified_count": status_counts.get("verified", 0),
        "needs_changes_count": status_counts.get("needs_changes", 0),
        "not_scoreable_count": status_counts.get("not_scoreable", 0),
        "pending_count": pending_count,
        "decision_status_counts": dict(sorted(status_counts.items())),
        "output_snapshot_count": len(outputs),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "free_text_review_notes_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload({"outputs": outputs, "summary": summary})
    return outputs, summary


def _write_outputs(
    *,
    output_dir: Path,
    summary_path: Path,
    outputs: dict[str, dict[str, Any]],
    summary: dict[str, object],
    overwrite_output: bool,
) -> None:
    """Write validated snapshots and a summary.

    Args:
        output_dir: Destination directory for snapshot copies.
        summary_path: Destination summary JSON path.
        outputs: Snapshot payloads keyed by file name.
        summary: Redacted apply summary.
        overwrite_output: Whether existing snapshot files may be replaced.

    Raises:
        FileExistsError: If an output file exists and overwrite is disabled.
        OSError: If filesystem operations fail.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        path = output_dir / name
        if path.exists() and not overwrite_output:
            raise FileExistsError("Output snapshot already exists.")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _apply_decision(
    *,
    snapshot: dict[str, Any],
    decision: dict[str, object],
    status: str,
) -> dict[str, Any]:
    """Apply one decision to a V3 snapshot copy.

    Args:
        snapshot: Source V3 snapshot payload.
        decision: Validated decision row.
        status: Decision verification status.

    Returns:
        Updated V3 snapshot payload.
    """
    updated = dict(snapshot)
    if status == "verified":
        _validate_verified_decision(decision)
        updated["ingredients"] = _verified_ingredients(decision["verified_ingredients"])
        updated["warnings"] = _verified_warnings(snapshot.get("warnings"))
        return updated

    _validate_non_verified_decision(decision)
    updated["warnings"] = _non_verified_warnings(snapshot.get("warnings"), status=status)
    return updated


def _verified_ingredients(value: object) -> list[dict[str, object]]:
    """Return V3 ingredient candidates projected from a verified decision.

    Args:
        value: ``verified_ingredients`` decision payload.

    Returns:
        V3 ingredient candidate payloads with ``source="manual"``.

    Raises:
        ValueError: If ingredients are missing or malformed.
    """
    if not isinstance(value, list) or not value:
        raise ValueError("Verified decisions require verified_ingredients.")
    if len(value) > MAX_INGREDIENTS:
        raise ValueError("Verified decision has too many ingredients.")
    ingredients: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Verified ingredients must be objects.")
        display_name = _required_text(item, "display_name")
        ingredient = {
            "display_name": display_name,
            "normalized_name": _optional_text(item.get("normalized_name")),
            "amount": _optional_non_negative_number(item.get("amount")),
            "unit": _optional_text(item.get("unit"), max_length=40),
            "amount_text": _optional_text(item.get("amount_text"), max_length=120),
            "daily_amount": _optional_non_negative_number(item.get("daily_amount")),
            "daily_unit": _optional_text(item.get("daily_unit"), max_length=40),
            "nutrient_code_candidates": [],
            "confidence": 1.0,
            "source": "manual",
            "evidence_refs": [],
        }
        ingredients.append({key: val for key, val in ingredient.items() if val is not None})
    return ingredients


def _validate_verified_decision(decision: dict[str, object]) -> None:
    """Validate safety attestations for a verified decision.

    Args:
        decision: Decision row.

    Raises:
        ValueError: If reviewer, attestations, or ingredients are invalid.
    """
    _required_reviewer_id(decision)
    _required_reviewed_at(decision)
    attestations = decision.get("attestations")
    if not isinstance(attestations, dict):
        raise ValueError("Verified decisions require attestations.")
    missing = [key for key in sorted(REQUIRED_ATTESTATIONS) if attestations.get(key) is not True]
    if missing:
        raise ValueError(f"Verified decision missing required attestation: {missing[0]}")
    _verified_ingredients(decision.get("verified_ingredients"))


def _validate_non_verified_decision(decision: dict[str, object]) -> None:
    """Validate a non-importable decision state.

    Args:
        decision: Decision row.

    Raises:
        ValueError: If reviewer metadata is invalid or ingredients are present.
    """
    _required_reviewer_id(decision)
    _required_reviewed_at(decision)
    ingredients = decision.get("verified_ingredients")
    if ingredients not in (None, []):
        raise ValueError("Non-verified decisions cannot include verified_ingredients.")


def _read_decision_rows(path: Path) -> dict[str, dict[str, object]]:
    """Read and validate decision JSONL rows keyed by fixture id.

    Args:
        path: Decision JSONL path.

    Returns:
        Mapping of fixture id to decision row.

    Raises:
        ValueError: If rows are malformed, duplicate, or unsafe.
    """
    decisions: dict[str, dict[str, object]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Decision line {line_number} must be an object.")
        _reject_unsafe_payload(row)
        if row.get("schema_version") != DECISION_SCHEMA_VERSION:
            raise ValueError("Decision rows must use chronic decision schema.")
        fixture_id = _required_safe_token(row, "fixture_id")
        if fixture_id in decisions:
            raise ValueError(f"Duplicate decision fixture_id: {fixture_id}")
        _required_status(row)
        _required_reviewer_id(row)
        _reject_unsafe_payload(row)
        decisions[fixture_id] = dict(row)
    return decisions


def _snapshot_paths(
    *,
    expected_dir: Path,
    fixture_prefix: str,
    snapshot_version: str,
) -> list[Path]:
    """Return expected V3 snapshot paths for a fixture subset.

    Args:
        expected_dir: Source expected snapshot directory.
        fixture_prefix: Fixture id prefix.
        snapshot_version: Snapshot version suffix.

    Returns:
        Sorted snapshot paths.

    Raises:
        ValueError: If the directory or tokens are invalid.
    """
    if not expected_dir.exists():
        raise ValueError("Expected directory does not exist.")
    if not SAFE_TOKEN_PATTERN.fullmatch(fixture_prefix.rstrip("-")):
        raise ValueError("Fixture prefix must be a bounded token.")
    if not SAFE_TOKEN_PATTERN.fullmatch(snapshot_version):
        raise ValueError("Snapshot version must be a bounded token.")
    pattern = f"{fixture_prefix}*.snapshot_{snapshot_version}.json"
    return sorted(path for path in expected_dir.glob(pattern) if path.is_file())


def _read_snapshot(path: Path) -> dict[str, Any]:
    """Read and validate one V3 snapshot.

    Args:
        path: Snapshot JSON path.

    Returns:
        Snapshot payload.

    Raises:
        ValueError: If the payload is not a safe V3 snapshot object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Snapshot JSON must be an object.")
    _reject_unsafe_payload(payload)
    _validate_snapshot(payload)
    return payload


def _validate_snapshot(payload: dict[str, Any]) -> None:
    """Validate a payload against the V3 Pydantic snapshot schema.

    Args:
        payload: Snapshot payload.
    """
    SupplementParsedSnapshotV3.model_validate(payload)


def _verified_warnings(value: object) -> list[str]:
    """Return warnings after a successful human verification.

    Args:
        value: Existing warnings value.

    Returns:
        Existing warnings without pending-review markers.
    """
    return [
        item
        for item in _string_list(value)
        if item not in PENDING_REVIEW_WARNINGS and _is_safe_text(item, max_length=160)
    ]


def _non_verified_warnings(value: object, *, status: str) -> list[str]:
    """Return warnings for a non-verified decision.

    Args:
        value: Existing warnings value.
        status: Non-verified status.

    Returns:
        Existing warnings plus a bounded human-review status code.
    """
    warnings = _string_list(value)
    if "ground_truth_pending_human_review" not in warnings:
        warnings.append("ground_truth_pending_human_review")
    warning = NON_VERIFIED_WARNING_CODES[status]
    if warning not in warnings:
        warnings.append(warning)
    return [item for item in warnings if _is_safe_text(item, max_length=160)]


def _snapshot_requires_human_review(snapshot: dict[str, Any]) -> bool:
    """Return whether a snapshot still carries pending human-review warnings.

    Args:
        snapshot: V3 snapshot payload.

    Returns:
        ``True`` if pending review warnings remain.
    """
    return bool(PENDING_REVIEW_WARNINGS.intersection(_string_list(snapshot.get("warnings"))))


def _fixture_id_from_snapshot_name(name: str) -> str:
    """Return fixture id from a snapshot file name.

    Args:
        name: Snapshot file name.

    Returns:
        Fixture id.

    Raises:
        ValueError: If the name is not a bounded snapshot name.
    """
    if ".snapshot_" not in name:
        raise ValueError("Snapshot file name must include .snapshot_.")
    fixture_id = name.split(".snapshot_", 1)[0]
    if not SAFE_TOKEN_PATTERN.fullmatch(fixture_id):
        raise ValueError("Snapshot fixture id must be a bounded token.")
    return fixture_id


def _required_status(row: dict[str, object]) -> str:
    """Return a decision verification status.

    Args:
        row: Decision row.

    Returns:
        Decision status.

    Raises:
        ValueError: If status is missing or unsupported.
    """
    status = row.get("verification_status")
    if not isinstance(status, str) or status not in ALLOWED_VERIFICATION_STATUSES:
        raise ValueError("Decision verification_status is invalid.")
    return status


def _required_reviewer_id(row: dict[str, object]) -> str:
    """Return a human operator reviewer id.

    Args:
        row: Decision row.

    Returns:
        Reviewer id.

    Raises:
        ValueError: If the id is missing or model-like.
    """
    reviewer_id = row.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not REVIEWER_PATTERN.fullmatch(reviewer_id):
        raise ValueError("Decision reviewer_id must be an operator-prefixed id.")
    return reviewer_id


def _required_reviewed_at(row: dict[str, object]) -> str:
    """Return a bounded review timestamp.

    Args:
        row: Decision row.

    Returns:
        Reviewed-at timestamp string.

    Raises:
        ValueError: If the value is missing or unsafe.
    """
    reviewed_at = _required_safe_token(row, "reviewed_at")
    if "T" not in reviewed_at:
        raise ValueError("Decision reviewed_at must be ISO-like.")
    return reviewed_at


def _required_safe_token(row: dict[str, object], key: str) -> str:
    """Return a required bounded token field.

    Args:
        row: Decision row.
        key: Field name.

    Returns:
        Token value.

    Raises:
        ValueError: If the value is missing or unsafe.
    """
    value = row.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Decision requires string field: {key}")
    token = value.strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(token) or _contains_local_path(token):
        raise ValueError(f"Decision field is not a safe token: {key}")
    return token


def _required_text(row: dict[str, object], key: str) -> str:
    """Return a required bounded text field.

    Args:
        row: Decision ingredient row.
        key: Field name.

    Returns:
        Normalized text.

    Raises:
        ValueError: If the text is missing or unsafe.
    """
    value = _optional_text(row.get(key))
    if value is None:
        raise ValueError(f"Ingredient requires bounded text field: {key}")
    return value


def _optional_text(value: object, *, max_length: int = MAX_TEXT_LENGTH) -> str | None:
    """Return bounded non-path text.

    Args:
        value: Candidate text value.
        max_length: Maximum allowed string length.

    Returns:
        Normalized text, or ``None``.
    """
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not _is_safe_text(text, max_length=max_length):
        return None
    return text


def _is_safe_text(value: str, *, max_length: int) -> bool:
    """Return whether text is bounded and free of local paths.

    Args:
        value: Candidate text.
        max_length: Maximum allowed string length.

    Returns:
        ``True`` if the text is safe to persist.
    """
    return bool(value) and len(value) <= max_length and not _contains_local_path(value)


def _optional_non_negative_number(value: object) -> int | float | None:
    """Return a non-negative numeric value.

    Args:
        value: Candidate numeric value.

    Returns:
        Numeric value, or ``None``.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float) and value >= 0:
        return value
    return None


def _string_list(value: object) -> list[str]:
    """Return safe strings from a list-like value.

    Args:
        value: Candidate list.

    Returns:
        Safe string values.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and not _contains_local_path(item)]


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys, sensitive literal keys, and local path literals.

    Args:
        value: Arbitrary JSON-like payload.

    Raises:
        ValueError: If unsafe keys or strings are present.
    """
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
    elif isinstance(value, str) and _contains_local_path(value):
        raise ValueError("Payload contains local path literal.")


def _contains_local_path(value: str) -> bool:
    """Return whether a string contains local path markers.

    Args:
        value: Candidate string.

    Returns:
        ``True`` if the string looks like a local path.
    """
    return any(marker in value for marker in LOCAL_PATH_MARKERS)


def _failure_summary(
    *,
    expected_dir: Path,
    decisions_path: Path,
    output_dir: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary.

    Args:
        expected_dir: Source expected snapshot directory.
        decisions_path: Decision JSONL path.
        output_dir: Planned output directory.
        error: Failure exception.

    Returns:
        Redacted summary without local paths or raw payloads.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "expected_dir_name": expected_dir.name,
        "expected_dir_path_hash": _sha256_text(str(expected_dir.expanduser())),
        "decisions_name": decisions_path.name,
        "decisions_path_hash": _sha256_text(str(decisions_path.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_path_hash": _sha256_text(str(output_dir.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "decision_row_count": 0,
        "matched_decision_count": 0,
        "unmatched_decision_count": 0,
        "verified_count": 0,
        "needs_changes_count": 0,
        "not_scoreable_count": 0,
        "pending_count": 0,
        "output_snapshot_count": 0,
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


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded non-sensitive error code.

    Args:
        exc: Failure exception.

    Returns:
        Public error code.
    """
    if isinstance(exc, OSError):
        return "local_file_operation_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded error message without filesystem details.

    Args:
        exc: Failure exception.

    Returns:
        Public-safe error message.
    """
    if isinstance(exc, OSError):
        message = "Local file operation failed."
    elif isinstance(exc, json.JSONDecodeError):
        message = "JSON decode failed."
    else:
        message = str(exc).strip()
    if not message or _contains_local_path(message) or "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for a UTF-8 text value.

    Args:
        value: Text value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
