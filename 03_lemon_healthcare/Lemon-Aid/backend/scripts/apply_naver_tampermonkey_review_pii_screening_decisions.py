"""Apply review-image PII screening decisions before OCR handoff.

The script reads a local-only review PII screening manifest and a separate
operator decision JSONL. Only rows explicitly marked ``cleared`` with required
attestations are exported to a collector-compatible local-only OCR manifest.
Rows with personal data, redaction needs, or no decision are skipped. No OCR,
LLM, database write, or external transfer is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import (  # noqa: E402
    build_naver_tampermonkey_review_pii_screening_manifest as pii_manifest,
)

SCHEMA_VERSION = "naver-tampermonkey-review-pii-screening-apply-v1"
OUTPUT_SCHEMA_VERSION = "naver-tampermonkey-review-pii-cleared-ocr-manifest-v1"
EXPECTED_MANIFEST_SCHEMA_VERSION = pii_manifest.SCHEMA_VERSION
ALLOWED_STATUSES = frozenset({"cleared", "contains_personal_data", "needs_redaction"})
REQUIRED_CLEARED_ATTESTATIONS = (
    "attest_local_screening_completed",
    "attest_no_personal_data_visible",
    "attest_no_raw_text_copied",
)
ALLOWED_DECISION_KEYS = frozenset(
    {
        "status",
        "reviewer_id",
        "reviewed_at",
        "reason_codes",
        *REQUIRED_CLEARED_ATTESTATIONS,
    }
)
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
OPERATOR_REVIEWER_ID_PATTERN = re.compile(r"^operator_[A-Za-z0-9_.:-]{1,71}$")
ENV_IMAGE_PATH_PATTERN = re.compile(r"^\$(?P<name>[A-Z][A-Z0-9_]*)(?:/(?P<path>.*))?$")
ALLOWED_IMAGE_PATH_ENV_VARS = frozenset({"NAVER_TAMPERMONKEY_SOURCE_ROOT"})
RAW_FORBIDDEN_KEYS = pii_manifest.RAW_FORBIDDEN_KEYS
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
FREE_TEXT_KEYS = frozenset({"comment", "comments", "note", "notes", "review_note"})


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for PII screening decision application."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
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
    return parser.parse_args()


def main() -> None:
    """Apply screening decisions and write cleared OCR manifest rows."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = apply_pii_screening_decisions(
            manifest_path=args.manifest.expanduser().resolve(),
            decisions_path=args.decisions.expanduser().resolve(),
            allow_unmatched_decisions=args.allow_unmatched_decisions,
            require_all_reviewed=args.require_all_reviewed,
        )
    except (OSError, ValueError) as exc:
        failure = _failure_summary(
            manifest_path=args.manifest,
            decisions_path=args.decisions,
            require_all_reviewed=args.require_all_reviewed,
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


def apply_pii_screening_decisions(
    *,
    manifest_path: Path,
    decisions_path: Path,
    allow_unmatched_decisions: bool = False,
    require_all_reviewed: bool = False,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return cleared local-only OCR manifest rows from screening decisions."""
    manifest_rows = _read_manifest_rows(manifest_path)
    decisions = _read_decision_rows(decisions_path)
    manifest_ids = {_required_str(row, "fixture_id") for row in manifest_rows}
    unmatched_ids = sorted(set(decisions) - manifest_ids)
    if unmatched_ids and not allow_unmatched_decisions:
        raise ValueError(f"PII decision fixture_id is not in manifest: {unmatched_ids[0]}")

    cleared_rows: list[dict[str, object]] = []
    status_counts: dict[str, int] = {}
    pending_count = 0
    for row in manifest_rows:
        fixture_id = _required_str(row, "fixture_id")
        decision = decisions.get(fixture_id)
        if decision is None:
            pending_count += 1
            status_counts["pending"] = status_counts.get("pending", 0) + 1
            continue
        status = _required_safe_token(decision, "status")
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "cleared":
            cleared_rows.append(_cleared_ocr_row(row, decision=decision))

    if require_all_reviewed and pending_count:
        raise ValueError("PII screening requires every row to be reviewed.")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_name": manifest_path.name,
        "decisions_name": decisions_path.name,
        "manifest_row_count": len(manifest_rows),
        "decision_row_count": len(decisions),
        "unmatched_decision_count": len(unmatched_ids),
        "pending_count": pending_count,
        "status_counts": dict(sorted(status_counts.items())),
        "cleared_row_count": len(cleared_rows),
        "external_transfer_allowed_rows": 0,
        "db_write_performed": False,
        "external_transfer_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload({"rows": cleared_rows, "summary": summary})
    return cleared_rows, summary


def _failure_summary(
    *,
    manifest_path: Path,
    decisions_path: Path,
    require_all_reviewed: bool,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted apply failure summary for CLI errors."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "manifest_name": manifest_path.name,
        "decisions_name": decisions_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "require_all_reviewed": require_all_reviewed,
        "manifest_row_count": 0,
        "decision_row_count": 0,
        "unmatched_decision_count": 0,
        "pending_count": 0,
        "status_counts": {},
        "cleared_row_count": 0,
        "external_transfer_allowed_rows": 0,
        "db_write_performed": False,
        "external_transfer_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _cleared_ocr_row(
    row: dict[str, object],
    *,
    decision: dict[str, object],
) -> dict[str, object]:
    """Return one collector-compatible local-only review OCR row."""
    for key in REQUIRED_CLEARED_ATTESTATIONS:
        if decision.get(key) is not True:
            raise ValueError(f"Cleared PII decision requires attestation: {key}")
    image_path = _required_str(row, "image_path")
    resolved_image = _resolve_token_image_path(image_path)
    image_sha256 = _sha256_file(resolved_image)
    cleared = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "fixture_id": _required_str(row, "fixture_id"),
        "source": "naver_tampermonkey",
        "section": "review",
        "image_path": image_path,
        "image_sha256": image_sha256,
        "license_status": "team_approved",
        "consent_status": "team_approved",
        "contains_personal_data": False,
        "pii_screening_status": "operator_cleared_review_local_only",
        "external_transfer_allowed": False,
        "local_processing_allowed": True,
        "expected": {},
        "category_key": _required_safe_token(row, "category_key"),
        "category_display": (
            row.get("category_display") if isinstance(row.get("category_display"), dict) else {}
        ),
        "product": row.get("product") if isinstance(row.get("product"), dict) else {},
        "pii_screening": {
            "status": "cleared",
            "reviewer_id": _required_operator_reviewer_id(decision),
            "reviewed_at": _required_str(decision, "reviewed_at"),
        },
    }
    _reject_unsafe_payload(cleared)
    return cleared


def _read_manifest_rows(path: Path) -> list[dict[str, object]]:
    """Read local-only review PII screening rows."""
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


def _read_decision_rows(path: Path) -> dict[str, dict[str, object]]:
    """Read screening decision rows keyed by fixture id."""
    decisions: dict[str, dict[str, object]] = {}
    for row in _read_jsonl_objects(path):
        fixture_id = _required_str(row, "fixture_id")
        if fixture_id in decisions:
            raise ValueError(f"Duplicate PII decision fixture_id: {fixture_id}")
        decision = row.get("pii_screening_decision")
        if not isinstance(decision, dict):
            raise ValueError("PII decision rows require object field: pii_screening_decision")
        _validate_decision(decision)
        decisions[fixture_id] = dict(decision)
    return decisions


def _validate_decision(decision: dict[str, object]) -> None:
    """Validate one screening decision object."""
    _reject_unsafe_payload(decision)
    keys = {str(key).lower() for key in decision}
    if FREE_TEXT_KEYS.intersection(keys):
        raise ValueError("PII screening decision cannot include free-text notes.")
    unexpected_keys = sorted(keys - ALLOWED_DECISION_KEYS)
    if unexpected_keys:
        raise ValueError(f"PII screening decision contains unsupported field: {unexpected_keys[0]}")
    status = _required_safe_token(decision, "status")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported PII screening status: {status}")
    _required_operator_reviewer_id(decision)
    _required_str(decision, "reviewed_at")
    if status == "cleared":
        for key in REQUIRED_CLEARED_ATTESTATIONS:
            if decision.get(key) is not True:
                raise ValueError(f"Cleared PII decision requires attestation: {key}")
    elif not _safe_token_list(decision.get("reason_codes")):
        raise ValueError(f"{status} PII decisions require reason_codes.")


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


def _resolve_token_image_path(image_path: str) -> Path:
    """Resolve an allowlisted env-token image path under its source root."""
    match = ENV_IMAGE_PATH_PATTERN.fullmatch(image_path)
    if not match or match.group("name") not in ALLOWED_IMAGE_PATH_ENV_VARS:
        raise ValueError("Cleared review image_path must use an allowlisted env token.")
    env_root = os.environ.get(match.group("name"))
    if not env_root:
        raise ValueError("Cleared review image root env is not set.")
    relative_path = PurePosixPath(match.group("path") or "")
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("Cleared review image path must stay under token root.")
    root = Path(env_root).expanduser().resolve()
    resolved = (root / Path(*relative_path.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Cleared review image path resolves outside token root.") from exc
    if not resolved.is_file():
        raise ValueError("Cleared review image file is missing.")
    return resolved


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required bounded string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Row requires string field: {key}")
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    return stripped


def _required_safe_token(row: dict[str, object], key: str) -> str:
    """Return a required safe token field."""
    token = _safe_token(row.get(key))
    if token is None:
        raise ValueError(f"Row requires safe token field: {key}")
    return token


def _required_operator_reviewer_id(row: dict[str, object]) -> str:
    """Return a reviewer id that represents a human/operator approval."""
    reviewer_id = _required_safe_token(row, "reviewer_id")
    if not OPERATOR_REVIEWER_ID_PATTERN.fullmatch(reviewer_id):
        raise ValueError("PII screening reviewer_id must use the operator_ prefix.")
    return reviewer_id


def _safe_token(value: object) -> str | None:
    """Return a bounded token or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(stripped):
        raise ValueError(f"Unsafe token value: {stripped[:80]}")
    return stripped


def _safe_token_list(value: object) -> list[str]:
    """Return safe token list."""
    if not isinstance(value, list):
        return []
    tokens: list[str] = []
    for item in value:
        token = _safe_token(item)
        if token is None:
            raise ValueError("Token lists require non-empty safe string values.")
        tokens.append(token)
    return tokens


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


def _sha256_file(path: Path) -> str:
    """Return file SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
