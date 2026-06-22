"""Run the approved Naver Tampermonkey DB import behind safety evidence gates.

The script imports only ``naver-tampermonkey-approved-db-import-v1`` rows that
already passed the review decision, approved export, dry-run ORM boundary check,
artifact privacy check, and reviewer DB-write approval log. Without
``--execute-db-write`` it performs preflight validation only and never opens a
database session.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.models.db.supplement import (  # noqa: E402
    SupplementProduct,
    SupplementProductIngredient,
)

from scripts import check_ocr_artifact_privacy as privacy_check  # noqa: E402
from scripts import dry_run_naver_tampermonkey_approved_db_import as dry_run  # noqa: E402

SCHEMA_VERSION = "naver-tampermonkey-approved-db-import-write-v1"
APPROVAL_LOG_SCHEMA_VERSION = "naver-tampermonkey-db-write-approval-v1"
APPROVAL_REVIEWER_ID_PREFIX = "operator_"
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
LOCAL_PATH_MARKERS = dry_run.LOCAL_PATH_MARKERS
RAW_FORBIDDEN_KEYS = dry_run.RAW_FORBIDDEN_KEYS
LITERAL_FORBIDDEN_KEYS = dry_run.LITERAL_FORBIDDEN_KEYS
APPROVAL_REQUIRED_TRUE_FIELDS = (
    "approved_for_db_write",
    "attest_dry_run_reviewed",
    "attest_privacy_scan_passed",
    "attest_reviewer_approved",
    "attest_not_clinical_recommendation",
)
APPROVAL_LOG_ALLOWED_KEYS = frozenset(
    {
        "schema_version",
        "approved_for_db_write",
        "reviewer_id",
        "approved_at",
        "approved_input_sha256",
        "dry_run_plan_sha256",
        "dry_run_summary_sha256",
        "privacy_summary_sha256",
        "planned_product_upsert_count",
        "planned_ingredient_row_count",
        "attest_dry_run_reviewed",
        "attest_privacy_scan_passed",
        "attest_reviewer_approved",
        "attest_not_clinical_recommendation",
    }
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the DB import runner."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-input", type=Path, required=True)
    parser.add_argument("--dry-run-plan", type=Path, required=True)
    parser.add_argument("--dry-run-summary", type=Path, required=True)
    parser.add_argument("--privacy-summary", type=Path, required=True)
    parser.add_argument("--approval-log", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument(
        "--execute-db-write",
        action="store_true",
        help="Required to open a database session and write rows.",
    )
    return parser.parse_args()


def main() -> None:
    """Run preflight and optionally execute the DB import."""
    args = parse_args()
    try:
        summary = asyncio.run(
            run_import(
                approved_input_path=args.approved_input.expanduser().resolve(),
                dry_run_plan_path=args.dry_run_plan.expanduser().resolve(),
                dry_run_summary_path=args.dry_run_summary.expanduser().resolve(),
                privacy_summary_path=args.privacy_summary.expanduser().resolve(),
                approval_log_path=args.approval_log.expanduser().resolve(),
                execute_db_write=bool(args.execute_db_write),
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = _failure_summary(
            approved_input_path=args.approved_input,
            dry_run_plan_path=args.dry_run_plan,
            dry_run_summary_path=args.dry_run_summary,
            privacy_summary_path=args.privacy_summary,
            approval_log_path=args.approval_log,
            error=exc,
        )
        _write_json(args.summary.expanduser().resolve(), summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None

    _write_json(args.summary.expanduser().resolve(), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


async def run_import(
    *,
    approved_input_path: Path,
    dry_run_plan_path: Path,
    dry_run_summary_path: Path,
    privacy_summary_path: Path,
    approval_log_path: Path,
    execute_db_write: bool = False,
) -> dict[str, object]:
    """Run import preflight and optionally write approved products to the DB.

    Args:
        approved_input_path: Approved DB import JSONL.
        dry_run_plan_path: Matching dry-run plan JSONL.
        dry_run_summary_path: Matching dry-run summary JSON.
        privacy_summary_path: Matching artifact privacy check summary JSON.
        approval_log_path: Reviewer approval log JSON.
        execute_db_write: Whether to execute the database write.

    Returns:
        Redacted import summary.
    """
    approved_rows, preflight_summary = build_import_preflight(
        approved_input_path=approved_input_path,
        dry_run_plan_path=dry_run_plan_path,
        dry_run_summary_path=dry_run_summary_path,
        privacy_summary_path=privacy_summary_path,
        approval_log_path=approval_log_path,
    )
    if not execute_db_write or not approved_rows:
        preflight_summary["execute_db_write_requested"] = execute_db_write
        preflight_summary["preflight_only"] = not execute_db_write
        preflight_summary["db_write_performed"] = False
        preflight_summary["imported_product_count"] = 0
        preflight_summary["imported_ingredient_count"] = 0
        return preflight_summary

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        import_summary = await import_approved_rows(session=session, approved_rows=approved_rows)

    summary = dict(preflight_summary)
    summary.update(import_summary)
    summary["execute_db_write_requested"] = True
    summary["preflight_only"] = False
    summary["db_write_performed"] = True
    _reject_unsafe_payload(summary)
    return summary


def build_import_preflight(
    *,
    approved_input_path: Path,
    dry_run_plan_path: Path,
    dry_run_summary_path: Path,
    privacy_summary_path: Path,
    approval_log_path: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Validate all evidence required before DB write.

    Args:
        approved_input_path: Approved DB import JSONL.
        dry_run_plan_path: Matching dry-run plan JSONL.
        dry_run_summary_path: Matching dry-run summary JSON.
        privacy_summary_path: Matching artifact privacy check summary JSON.
        approval_log_path: Reviewer approval log JSON.

    Returns:
        Approved rows and redacted preflight summary.

    Raises:
        ValueError: If any evidence is missing, mismatched, or unsafe.
    """
    approved_rows = dry_run._read_input_rows(approved_input_path)
    expected_plan_rows, expected_dry_run_summary = dry_run.build_dry_run_import_plan(
        input_path=approved_input_path,
    )
    actual_plan_rows = _read_jsonl_objects(dry_run_plan_path)
    dry_run_summary = _read_json_object(dry_run_summary_path)
    privacy_summary = _read_json_object(privacy_summary_path)
    approval_log = _read_json_object(approval_log_path)
    _reject_unsafe_payload(
        {
            "approved_rows": approved_rows,
            "actual_plan_rows": actual_plan_rows,
            "dry_run_summary": dry_run_summary,
            "privacy_summary": privacy_summary,
            "approval_log": approval_log,
        }
    )
    if actual_plan_rows != expected_plan_rows:
        raise ValueError("Dry-run plan does not match approved input rows.")
    _validate_dry_run_summary(
        dry_run_summary=dry_run_summary,
        expected_summary=expected_dry_run_summary,
    )
    _validate_privacy_summary(privacy_summary)
    _validate_approval_log(
        approval_log=approval_log,
        approved_input_path=approved_input_path,
        dry_run_plan_path=dry_run_plan_path,
        dry_run_summary_path=dry_run_summary_path,
        privacy_summary_path=privacy_summary_path,
        planned_product_count=int(expected_dry_run_summary["planned_product_upsert_count"]),
        planned_ingredient_count=int(expected_dry_run_summary["planned_ingredient_row_count"]),
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "approved_input_name": approved_input_path.name,
        "dry_run_plan_name": dry_run_plan_path.name,
        "dry_run_summary_name": dry_run_summary_path.name,
        "privacy_summary_name": privacy_summary_path.name,
        "approval_log_name": approval_log_path.name,
        "approved_input_sha256": _sha256_file(approved_input_path),
        "dry_run_plan_sha256": _sha256_file(dry_run_plan_path),
        "dry_run_summary_sha256": _sha256_file(dry_run_summary_path),
        "privacy_summary_sha256": _sha256_file(privacy_summary_path),
        "approval_log_sha256": _sha256_file(approval_log_path),
        "approved_row_count": len(approved_rows),
        "planned_product_upsert_count": expected_dry_run_summary["planned_product_upsert_count"],
        "planned_ingredient_row_count": expected_dry_run_summary["planned_ingredient_row_count"],
        "privacy_check_passed": True,
        "reviewer_approved_for_db_write": True,
        "ready_for_db_write": True,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
        "external_transfer_performed": False,
        "db_write_performed": False,
    }
    _reject_unsafe_payload(summary)
    return approved_rows, summary


async def import_approved_rows(
    *,
    session: AsyncSession,
    approved_rows: list[dict[str, object]],
) -> dict[str, object]:
    """Upsert approved product rows and replace their ingredient children.

    Args:
        session: Async SQLAlchemy session.
        approved_rows: Validated approved import rows.

    Returns:
        Redacted write summary.

    Raises:
        ValueError: If an approved row is unsafe or malformed.
    """
    product_count = 0
    ingredient_count = 0
    try:
        for row in approved_rows:
            dry_run._validate_approved_import_row(row)
            product = await _upsert_product(session=session, row=row)
            await session.execute(
                delete(SupplementProductIngredient).where(
                    SupplementProductIngredient.product_id == product.id,
                )
            )
            for item in _required_ingredients(row):
                session.add(_ingredient_from_row(item, product_id=product.id))
                ingredient_count += 1
            product_count += 1
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {
        "imported_product_count": product_count,
        "imported_ingredient_count": ingredient_count,
    }


async def _upsert_product(
    *,
    session: AsyncSession,
    row: dict[str, object],
) -> SupplementProduct:
    """Insert or update one reference product by source identity."""
    source_provider = _required_string(row, "source_provider")
    source_product_id = _required_string(row, "source_product_id")
    product = await session.scalar(
        select(SupplementProduct).where(
            SupplementProduct.source_provider == source_provider,
            SupplementProduct.source_product_id == source_product_id,
        )
    )
    if product is None:
        product = SupplementProduct(
            source_provider=source_provider,
            source_product_id=source_product_id,
            product_name=_required_string(row, "product_name"),
            normalized_product_name=_required_string(row, "normalized_product_name"),
            manufacturer=_optional_string(row, "manufacturer"),
            category=_optional_string(row, "category"),
            source_payload=_required_dict(row, "source_payload"),
            source_manifest_version=_optional_string(row, "source_manifest_version"),
            is_active=row.get("is_active") is True,
        )
        session.add(product)
    else:
        product.product_name = _required_string(row, "product_name")
        product.normalized_product_name = _required_string(row, "normalized_product_name")
        product.manufacturer = _optional_string(row, "manufacturer")
        product.category = _optional_string(row, "category")
        product.source_payload = _required_dict(row, "source_payload")
        product.source_manifest_version = _optional_string(row, "source_manifest_version")
        product.is_active = row.get("is_active") is True
    await session.flush()
    return product


def _ingredient_from_row(
    item: dict[str, object],
    *,
    product_id: object,
) -> SupplementProductIngredient:
    """Return one ORM ingredient row from approved import data."""
    return SupplementProductIngredient(
        product_id=product_id,
        standard_name=_required_string(item, "standard_name"),
        nutrient_code=_optional_string(item, "nutrient_code"),
        amount=_decimal_or_none(item.get("amount")),
        unit=_optional_string(item, "unit"),
        source_payload=_required_dict(item, "source_payload"),
        sort_order=_non_negative_int(item.get("sort_order"), field_name="sort_order"),
    )


def _validate_dry_run_summary(
    *,
    dry_run_summary: dict[str, object],
    expected_summary: dict[str, object],
) -> None:
    """Validate dry-run summary evidence for DB write."""
    required_false_fields = (
        "db_write_performed",
        "raw_artifacts_stored",
        "raw_ocr_text_stored",
        "raw_provider_payload_stored",
        "raw_model_response_stored",
        "local_path_literals_stored",
        "clinical_recommendations_stored",
    )
    if dry_run_summary.get("schema_version") != dry_run.SCHEMA_VERSION:
        raise ValueError("Dry-run summary schema is invalid.")
    if dry_run_summary.get("dry_run_only") is not True:
        raise ValueError("Dry-run summary must be dry-run only.")
    for key in required_false_fields:
        if dry_run_summary.get(key) is not False:
            raise ValueError(f"Dry-run summary failed safety field: {key}")
    for key in (
        "input_row_count",
        "planned_product_upsert_count",
        "planned_ingredient_replace_count",
        "planned_ingredient_row_count",
    ):
        if dry_run_summary.get(key) != expected_summary.get(key):
            raise ValueError(f"Dry-run summary count mismatch: {key}")


def _validate_privacy_summary(summary: dict[str, object]) -> None:
    """Validate artifact privacy check summary evidence."""
    if summary.get("schema_version") != privacy_check.SCHEMA_VERSION:
        raise ValueError("Privacy summary schema is invalid.")
    if summary.get("passed") is not True or summary.get("finding_count") != 0:
        raise ValueError("Privacy summary must pass with zero findings.")
    if summary.get("db_write_performed") is not False:
        raise ValueError("Privacy summary must be generated before DB write.")
    if summary.get("external_transfer_performed") is not False:
        raise ValueError("Privacy summary must not involve external transfer.")


def _validate_approval_log(
    *,
    approval_log: dict[str, object],
    approved_input_path: Path,
    dry_run_plan_path: Path,
    dry_run_summary_path: Path,
    privacy_summary_path: Path,
    planned_product_count: int,
    planned_ingredient_count: int,
) -> None:
    """Validate human DB-write approval log evidence."""
    unknown_keys = set(approval_log) - APPROVAL_LOG_ALLOWED_KEYS
    if unknown_keys:
        raise ValueError("Approval log contains unsupported field(s).")
    if approval_log.get("schema_version") != APPROVAL_LOG_SCHEMA_VERSION:
        raise ValueError("Approval log schema is invalid.")
    for key in APPROVAL_REQUIRED_TRUE_FIELDS:
        if approval_log.get(key) is not True:
            raise ValueError(f"Approval log failed required attestation: {key}")
    reviewer_id = approval_log.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not SAFE_TOKEN_PATTERN.fullmatch(reviewer_id):
        raise ValueError("Approval log requires safe token field: reviewer_id")
    if not reviewer_id.startswith(APPROVAL_REVIEWER_ID_PREFIX):
        raise ValueError(f"Approval log reviewer_id must start with {APPROVAL_REVIEWER_ID_PREFIX}")
    _validate_approved_at_utc(approval_log.get("approved_at"))
    expected_hashes = {
        "approved_input_sha256": _sha256_file(approved_input_path),
        "dry_run_plan_sha256": _sha256_file(dry_run_plan_path),
        "dry_run_summary_sha256": _sha256_file(dry_run_summary_path),
        "privacy_summary_sha256": _sha256_file(privacy_summary_path),
    }
    for key, expected_value in expected_hashes.items():
        if approval_log.get(key) != expected_value:
            raise ValueError(f"Approval log hash mismatch: {key}")
    if approval_log.get("planned_product_upsert_count") != planned_product_count:
        raise ValueError("Approval log product count mismatch.")
    if approval_log.get("planned_ingredient_row_count") != planned_ingredient_count:
        raise ValueError("Approval log ingredient count mismatch.")


def _validate_approved_at_utc(value: object) -> None:
    """Validate DB-write approval timestamp as an aware UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Approval log approved_at must be UTC ISO-8601.")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("Approval log approved_at must be UTC ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Approval log approved_at must be UTC ISO-8601.")


def _required_ingredients(row: dict[str, object]) -> list[dict[str, object]]:
    """Return required ingredient rows from an approved import row."""
    ingredients = row.get("ingredients")
    if not isinstance(ingredients, list) or not ingredients:
        raise ValueError("Approved import row requires at least one ingredient.")
    if not all(isinstance(item, dict) for item in ingredients):
        raise ValueError("Ingredient rows must be objects.")
    return ingredients


def _required_dict(row: dict[str, object], key: str) -> dict[str, object]:
    """Return a required object field after unsafe-payload rejection."""
    value = row.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Row requires object field: {key}")
    _reject_unsafe_payload(value)
    return value


def _required_string(row: dict[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Row requires string field: {key}")
    _reject_unsafe_payload(value)
    return value.strip()


def _optional_string(row: dict[str, object], key: str) -> str | None:
    """Return an optional non-empty string field."""
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Row field must be a string: {key}")
    stripped = value.strip()
    if not stripped:
        return None
    _reject_unsafe_payload(stripped)
    return stripped


def _non_negative_int(value: object, *, field_name: str) -> int:
    """Return a non-negative integer value."""
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"Row requires non-negative integer field: {field_name}")
    return value


def _decimal_or_none(value: object) -> Decimal | None:
    """Return an optional Decimal for ingredient amounts."""
    if value is None:
        return None
    return dry_run._decimal_or_none(value)


def _read_jsonl_objects(path: Path) -> list[dict[str, object]]:
    """Read JSONL object rows from a generated artifact."""
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


def _read_json_object(path: Path) -> dict[str, object]:
    """Read one JSON object from a generated artifact."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON artifact must be an object.")
    _reject_unsafe_payload(value)
    return value


def _write_json(path: Path, value: dict[str, object]) -> None:
    """Write a JSON summary after final unsafe-payload rejection."""
    _reject_unsafe_payload(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _failure_summary(
    *,
    approved_input_path: Path,
    dry_run_plan_path: Path,
    dry_run_summary_path: Path,
    privacy_summary_path: Path,
    approval_log_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "approved_input_name": approved_input_path.name,
        "dry_run_plan_name": dry_run_plan_path.name,
        "dry_run_summary_name": dry_run_summary_path.name,
        "privacy_summary_name": privacy_summary_path.name,
        "approval_log_name": approval_log_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "ready_for_db_write": False,
        "execute_db_write_requested": False,
        "db_write_performed": False,
        "imported_product_count": 0,
        "imported_ingredient_count": 0,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
        "external_transfer_performed": False,
    }
    _reject_unsafe_payload(summary)
    return summary


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


def _sha256_file(path: Path) -> str:
    """Return a SHA-256 digest for a local artifact file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
