"""Build approved supplement product import rows from brand review decisions.

This script joins taxonomy DB-staging rows with operator brand/product review
decisions. Only explicit approved decisions with required attestations become
``supplement_product_import`` rows. The output is an import manifest, not a DB
writer, so category/product rows can still be reviewed or loaded by a separate
controlled migration/import step.

It does not write to the database and never emits local absolute paths, product
directory literals, raw OCR text, provider payloads, or image bytes.

References:
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
    https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import build_supplement_taxonomy_db_staging as staging  # noqa: E402
from scripts import export_supplement_brand_review_template as template  # noqa: E402

SCHEMA_VERSION = "supplement-brand-review-apply-v1"
OUTPUT_ROW_SCHEMA_VERSION = "supplement-product-import-manifest-row-v1"
DECISION_SCHEMA_VERSION = template.DECISION_SCHEMA_VERSION
EXPECTED_STAGING_SCHEMA_VERSION = staging.SCHEMA_VERSION
SOURCE_PROVIDER = "crawling_image"
SAFE_TOKEN_PATTERN = re.compile(r"^[0-9A-Za-z가-힣_.:+-]{1,160}$")
OPERATOR_REVIEWER_ID_PATTERN = re.compile(r"^operator_[A-Za-z0-9_.:-]{1,71}$")
SHA256_HEX_LENGTH = 64
MIN_REVIEW_TEXT_LENGTH = 2
ALLOWED_DECISIONS = frozenset({"approve", "reject", "needs_review", "not_a_brand"})
REQUIRED_APPROVAL_ATTESTATIONS = (
    "attest_brand_product_review_completed",
    "attest_not_using_product_folder_literal_as_manufacturer",
    "attest_product_name_reviewed_from_label_or_safe_catalog",
    "attest_no_raw_ocr_or_provider_payload_copied",
    "attest_db_import_allowed",
)
ALLOWED_DECISION_KEYS = frozenset(
    {
        "decision",
        "reviewer_id",
        "reviewed_at",
        "reviewed_manufacturer",
        "reviewed_product_name",
        "reason_codes",
        *REQUIRED_APPROVAL_ATTESTATIONS,
    }
)
ALLOWED_REASON_CODES = frozenset(
    {
        "reviewed_label_or_catalog",
        "not_brand",
        "unclear_brand",
        "duplicate_product",
        "needs_catalog_lookup",
        "unsafe_text",
        "category_mismatch",
        "low_confidence_folder_name",
    }
)
LOCAL_PATH_OR_URL_MARKERS = template.LOCAL_PATH_OR_URL_MARKERS
LOCAL_PATH_MARKERS = template.LOCAL_PATH_MARKERS
FREE_TEXT_KEYS = frozenset({"comment", "comments", "note", "notes", "review_note"})
SOURCE_DOC_URLS = template.SOURCE_DOC_URLS


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy-staging", type=Path, required=True)
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Apply brand review decisions and write import manifest rows.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = apply_brand_review_decisions(
            taxonomy_staging=args.taxonomy_staging,
            decisions_path=args.decisions,
            allow_unmatched_decisions=args.allow_unmatched_decisions,
            require_all_reviewed=args.require_all_reviewed,
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
            taxonomy_staging=args.taxonomy_staging,
            decisions_path=args.decisions,
            output_path=output_path,
            require_all_reviewed=args.require_all_reviewed,
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


def apply_brand_review_decisions(
    *,
    taxonomy_staging: Path,
    decisions_path: Path,
    allow_unmatched_decisions: bool = False,
    require_all_reviewed: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return approved import manifest rows from operator decisions.

    Args:
        taxonomy_staging: JSONL generated by taxonomy DB staging.
        decisions_path: Operator decision JSONL.
        allow_unmatched_decisions: Whether stale decision rows can be ignored.
        require_all_reviewed: Whether every brand candidate requires a decision.

    Returns:
        Approved import rows and redacted summary.

    Raises:
        ValueError: If rows are unsafe, duplicated, stale, or malformed.
    """
    candidates = _brand_candidates_by_fixture_id(_read_jsonl_objects(taxonomy_staging))
    decisions = _read_decision_rows(decisions_path)
    unmatched_ids = sorted(set(decisions) - set(candidates))
    if unmatched_ids and not allow_unmatched_decisions:
        raise ValueError(f"Brand review fixture_id is not in taxonomy staging: {unmatched_ids[0]}")

    output_rows: list[dict[str, Any]] = []
    decision_counts: Counter[str] = Counter()
    skip_counts: Counter[str] = Counter()
    pending_count = 0

    for fixture_id, candidate in candidates.items():
        decision = decisions.get(fixture_id)
        if decision is None:
            pending_count += 1
            decision_counts["pending"] += 1
            continue

        decision_value = _required_safe_token(decision.get("decision"), field_name="decision")
        decision_counts[decision_value] += 1
        if decision_value != "approve":
            skip_counts[f"{decision_value}_blocked"] += 1
            continue
        output_rows.append(_approved_import_row(candidate, decision=decision))

    if require_all_reviewed and pending_count:
        raise ValueError("Brand review requires every supplement brand candidate to be reviewed.")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "taxonomy_staging_name": taxonomy_staging.name,
        "taxonomy_staging_hash": staging.audit._sha256_text(str(taxonomy_staging.expanduser())),
        "decisions_name": decisions_path.name,
        "decisions_hash": staging.audit._sha256_text(str(decisions_path.expanduser())),
        "brand_candidate_count": len(candidates),
        "decision_row_count": len(decisions),
        "unmatched_decision_count": len(unmatched_ids),
        "pending_count": pending_count,
        "decision_counts": dict(sorted(decision_counts.items())),
        "skip_reason_counts": dict(sorted(skip_counts.items())),
        "approved_import_row_count": len(output_rows),
        "db_write_performed": False,
        "approved_for_db_write_rows": len(output_rows),
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload({"rows": output_rows, "summary": summary})
    return output_rows, summary


def _approved_import_row(
    candidate: dict[str, Any],
    *,
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Return one approved product import manifest row.

    Args:
        candidate: Brand candidate staging row.
        decision: Validated operator approval decision.

    Returns:
        JSON-safe import row.

    Raises:
        ValueError: If required approval attestations are missing.
    """
    for key in REQUIRED_APPROVAL_ATTESTATIONS:
        if decision.get(key) is not True:
            raise ValueError(f"Approved brand decision requires attestation: {key}")

    product_dir_hash = _required_sha256(
        candidate.get("product_dir_hash"), field_name="product_dir_hash"
    )
    source_product_id = _safe_source_product_id(
        candidate.get("source_product_id"), product_dir_hash
    )
    manufacturer = _required_review_text(
        decision.get("reviewed_manufacturer"),
        field_name="reviewed_manufacturer",
        max_length=180,
    )
    product_name = _required_review_text(
        decision.get("reviewed_product_name"),
        field_name="reviewed_product_name",
        max_length=240,
    )
    category_key = _required_safe_token(candidate.get("category_key"), field_name="category_key")
    reviewer_id = _required_operator_reviewer_id(decision)
    row = {
        "schema_version": OUTPUT_ROW_SCHEMA_VERSION,
        "row_type": "supplement_product_import",
        "db_target_table": "supplement_products",
        "source_provider": SOURCE_PROVIDER,
        "source_product_id": source_product_id,
        "product_name": product_name,
        "normalized_product_name": _normalize_product_name(product_name),
        "manufacturer": manufacturer,
        "category_key": category_key,
        "category_display_name": _safe_display_text(candidate.get("category_display_name")),
        "category_mapping": {
            "db_target_table": "supplement_product_categories",
            "source": "folder_import_reviewed",
            "confidence": 1.0,
            "is_primary": True,
            "category_key": category_key,
        },
        "source_manifest_version": EXPECTED_STAGING_SCHEMA_VERSION,
        "source_payload": {
            "source_provider": SOURCE_PROVIDER,
            "product_dir_hash": product_dir_hash,
            "source_folder_hash": _required_sha256(
                candidate.get("source_folder_hash"),
                field_name="source_folder_hash",
            ),
            "reviewed_by_hash": staging.audit._sha256_text(reviewer_id),
            "reviewed_at": _required_safe_token(
                decision.get("reviewed_at"), field_name="reviewed_at"
            ),
            "review_decision": "approve",
            "review_reason_codes": _safe_reason_codes(decision.get("reason_codes")),
            "image_count": _safe_nonnegative_int(candidate.get("image_count")),
            "source_kind_counts": _safe_counter(candidate.get("source_kind_counts")),
            "issue_counts": _safe_counter(candidate.get("issue_counts")),
            "source_payload_policy": "hashes_counts_and_review_metadata_only",
        },
        "requires_human_review": False,
        "approved_for_db_write": True,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }
    _reject_unsafe_payload(row)
    return row


def _brand_candidates_by_fixture_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index brand candidate staging rows by review fixture id.

    Args:
        rows: Taxonomy staging rows.

    Returns:
        Brand candidate rows keyed by fixture id.

    Raises:
        ValueError: If rows are unsupported or duplicated.
    """
    candidates: dict[str, dict[str, Any]] = {}
    for row in rows:
        _reject_unsafe_payload(row)
        if row.get("schema_version") != EXPECTED_STAGING_SCHEMA_VERSION:
            raise ValueError("Supplement taxonomy staging row uses an unsupported schema.")
        if row.get("row_type") != staging.ROW_TYPE_BRAND_CANDIDATE:
            continue
        if row.get("approved_for_db_write") is True:
            raise ValueError("Brand candidate staging rows must not be pre-approved.")
        fixture_id = template._fixture_id(
            _required_sha256(row.get("product_dir_hash"), field_name="product_dir_hash")
        )
        if fixture_id in candidates:
            raise ValueError(f"Duplicate supplement brand candidate fixture_id: {fixture_id}")
        candidates[fixture_id] = dict(row)
    return candidates


def _read_decision_rows(path: Path) -> dict[str, dict[str, Any]]:
    """Read operator brand review decision rows keyed by fixture id.

    Args:
        path: Decision JSONL path.

    Returns:
        Decision mapping.

    Raises:
        ValueError: If decisions are unsafe, malformed, or duplicated.
    """
    decisions: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl_objects(path):
        _reject_unsafe_payload(row)
        if row.get("schema_version") not in {None, DECISION_SCHEMA_VERSION}:
            raise ValueError("Supplement brand review decision row uses an unsupported schema.")
        fixture_id = _required_safe_token(row.get("fixture_id"), field_name="fixture_id")
        if fixture_id in decisions:
            raise ValueError(f"Duplicate supplement brand decision fixture_id: {fixture_id}")
        decision = row.get("brand_review_decision")
        if not isinstance(decision, dict):
            raise ValueError("Brand review rows require brand_review_decision object.")
        _validate_decision(decision)
        decisions[fixture_id] = dict(decision)
    return decisions


def _validate_decision(decision: dict[str, Any]) -> None:
    """Validate one operator brand/product review decision.

    Args:
        decision: Decision payload.

    Raises:
        ValueError: If the decision is unsafe or incomplete.
    """
    _reject_unsafe_payload(decision)
    keys = {str(key).lower() for key in decision}
    if FREE_TEXT_KEYS.intersection(keys):
        raise ValueError("Supplement brand decision cannot include free-text notes.")
    unexpected = sorted(keys - ALLOWED_DECISION_KEYS)
    if unexpected:
        raise ValueError(f"Supplement brand decision contains unsupported field: {unexpected[0]}")
    decision_value = _required_safe_token(decision.get("decision"), field_name="decision")
    if decision_value not in ALLOWED_DECISIONS:
        raise ValueError(f"Unsupported supplement brand decision: {decision_value}")
    _required_operator_reviewer_id(decision)
    _required_safe_token(decision.get("reviewed_at"), field_name="reviewed_at")
    if decision_value == "approve":
        for key in REQUIRED_APPROVAL_ATTESTATIONS:
            if decision.get(key) is not True:
                raise ValueError(f"Approved brand decision requires attestation: {key}")
        _required_review_text(
            decision.get("reviewed_manufacturer"),
            field_name="reviewed_manufacturer",
            max_length=180,
        )
        _required_review_text(
            decision.get("reviewed_product_name"),
            field_name="reviewed_product_name",
            max_length=240,
        )
    elif not _safe_reason_codes(decision.get("reason_codes")):
        raise ValueError(f"{decision_value} brand decisions require reason_codes.")


def _read_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows.

    Args:
        path: JSONL path.

    Returns:
        JSON object rows.

    Raises:
        ValueError: If any row is not an object or contains unsafe content.
    """
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL rows must be objects.")
        _reject_unsafe_payload(row)
        rows.append(row)
    return rows


def _required_operator_reviewer_id(row: dict[str, Any]) -> str:
    """Return a safe operator reviewer id.

    Args:
        row: Decision object.

    Returns:
        Reviewer id.

    Raises:
        ValueError: If the reviewer id is missing or not operator-scoped.
    """
    reviewer_id = _required_safe_token(row.get("reviewer_id"), field_name="reviewer_id")
    if not OPERATOR_REVIEWER_ID_PATTERN.fullmatch(reviewer_id):
        raise ValueError("Supplement brand reviewer_id must use the operator_ prefix.")
    return reviewer_id


def _required_safe_token(value: Any, *, field_name: str) -> str:
    """Return a required bounded token.

    Args:
        value: Raw value.
        field_name: Field name used in validation errors.

    Returns:
        Safe token string.

    Raises:
        ValueError: If the value is missing or unsafe.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Row requires safe token field: {field_name}")
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_OR_URL_MARKERS):
        raise ValueError("Payload contains local path or URL literal.")
    if not SAFE_TOKEN_PATTERN.fullmatch(stripped):
        raise ValueError(f"Unsafe token field: {field_name}")
    return stripped


def _required_sha256(value: Any, *, field_name: str) -> str:
    """Return a required SHA-256 hex value.

    Args:
        value: Raw value.
        field_name: Field name used in validation errors.

    Returns:
        SHA-256 hex string.

    Raises:
        ValueError: If the value is not a SHA-256 hex digest.
    """
    token = _required_safe_token(value, field_name=field_name)
    if len(token) != SHA256_HEX_LENGTH or any(char not in "0123456789abcdef" for char in token):
        raise ValueError(f"Row requires sha256 field: {field_name}")
    return token


def _safe_source_product_id(value: Any, product_dir_hash: str) -> str:
    """Return a safe source product id.

    Args:
        value: Optional source product id from the audited folder suffix.
        product_dir_hash: Product folder hash for deterministic fallback.

    Returns:
        Safe provider product id.
    """
    if isinstance(value, str) and value.strip():
        return _required_safe_token(value, field_name="source_product_id")
    return f"folder_{product_dir_hash[:32]}"


def _required_review_text(value: Any, *, field_name: str, max_length: int) -> str:
    """Return required operator-reviewed product/manufacturer text.

    Args:
        value: Raw review value.
        field_name: Field name used in validation errors.
        max_length: Maximum output length.

    Returns:
        Sanitized review text.

    Raises:
        ValueError: If the text is missing, unsafe, or path-like.
    """
    text = _safe_display_text(value, max_length=max_length)
    if not text:
        raise ValueError(f"Approved brand decision requires field: {field_name}")
    if len(text) < MIN_REVIEW_TEXT_LENGTH:
        raise ValueError(f"Approved brand decision field is too short: {field_name}")
    return text


def _safe_display_text(value: Any, *, max_length: int = 180) -> str | None:
    """Return bounded display text with local paths and URLs rejected.

    Args:
        value: Raw value.
        max_length: Maximum output length.

    Returns:
        Sanitized display text or ``None``.

    Raises:
        ValueError: If the value is not text or contains path/URL markers.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Display text must be a string.")
    stripped = " ".join(value.strip().split())
    if not stripped:
        return None
    if any(marker in stripped for marker in LOCAL_PATH_OR_URL_MARKERS):
        raise ValueError("Payload contains local path or URL literal.")
    if "/" in stripped or "\\" in stripped:
        raise ValueError("Display text must not contain path separators.")
    return stripped[:max_length]


def _normalize_product_name(value: str) -> str:
    """Return a deterministic normalized product name.

    Args:
        value: Human-reviewed product display name.

    Returns:
        Search-normalized product name.
    """
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())[:240]


def _safe_reason_codes(value: Any) -> list[str]:
    """Return allowlisted reason codes.

    Args:
        value: Raw reason code list.

    Returns:
        Sanitized reason code list.

    Raises:
        ValueError: If a reason code is malformed or unsupported.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Supplement brand reason_codes must be a list.")
    codes: list[str] = []
    for item in value:
        code = _required_safe_token(item, field_name="reason_codes")
        if code not in ALLOWED_REASON_CODES:
            raise ValueError(f"Unsupported supplement brand reason_code: {code}")
        codes.append(code)
    return codes


def _safe_nonnegative_int(value: Any) -> int:
    """Return a nonnegative integer.

    Args:
        value: Raw value.

    Returns:
        Nonnegative integer.

    Raises:
        ValueError: If the value is not a nonnegative integer.
    """
    if not isinstance(value, int) or value < 0:
        raise ValueError("Expected a nonnegative integer.")
    return value


def _safe_counter(value: Any) -> dict[str, int]:
    """Return a sanitized counter mapping.

    Args:
        value: Raw mapping.

    Returns:
        Safe mapping from token to nonnegative integer.

    Raises:
        ValueError: If the mapping is malformed.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Counter field must be an object.")
    return {
        _required_safe_token(key, field_name="counter_key"): _safe_nonnegative_int(count)
        for key, count in sorted(value.items())
    }


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw fields, local paths, URLs, and product directory literals.

    Args:
        value: Candidate JSON-like payload.

    Raises:
        ValueError: If unsafe content is present.
    """
    staging._reject_unsafe_payload(value)
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if any(marker in serialized for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path or URL literal.")


def _failure_summary(
    *,
    taxonomy_staging: Path,
    decisions_path: Path,
    output_path: Path,
    require_all_reviewed: bool,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        taxonomy_staging: Staging JSONL path.
        decisions_path: Decision JSONL path.
        output_path: Planned output path.
        require_all_reviewed: CLI strict-review flag.
        error: Raised exception.

    Returns:
        JSON-safe failure payload.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "taxonomy_staging_name": taxonomy_staging.name,
        "taxonomy_staging_hash": staging.audit._sha256_text(str(taxonomy_staging.expanduser())),
        "decisions_name": decisions_path.name,
        "decisions_hash": staging.audit._sha256_text(str(decisions_path.expanduser())),
        "output_name": output_path.name,
        "output_hash": staging.audit._sha256_text(str(output_path.expanduser())),
        "error_code": type(error).__name__,
        "error_message": _safe_public_error_message(error),
        "require_all_reviewed": require_all_reviewed,
        "approved_import_row_count": 0,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_public_error_message(error: Exception) -> str:
    """Return a bounded public error message without filesystem details.

    Args:
        error: Raised exception.

    Returns:
        Redacted public error message.
    """
    if isinstance(error, OSError):
        return "Local file read failed."
    message = str(error).strip()
    if not message:
        return "Validation failed."
    if any(marker in message for marker in LOCAL_PATH_OR_URL_MARKERS):
        return "Validation failed."
    if "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


if __name__ == "__main__":
    main()
