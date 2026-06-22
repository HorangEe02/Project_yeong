"""Dry-run approved Naver Tampermonkey product imports against ORM constraints.

The script validates ``naver-tampermonkey-approved-db-import-v1`` rows against
the reference product ORM model boundaries, then writes an operation plan. It
does not open a database connection and never writes product rows. The dry-run
artifact stores only bounded reviewed values, count metadata, and hashes of safe
source payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import String

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.models.db.supplement import (  # noqa: E402
    SupplementProduct,
    SupplementProductIngredient,
)

from scripts import validate_naver_tampermonkey_review_decisions as validator  # noqa: E402

SCHEMA_VERSION = "naver-tampermonkey-approved-db-import-dry-run-v1"
EXPECTED_INPUT_SCHEMA_VERSION = "naver-tampermonkey-approved-db-import-v1"
MAX_TOKEN_LENGTH = 80
INGREDIENT_AMOUNT_SCALE = 6
INGREDIENT_AMOUNT_INTEGER_DIGITS = 8
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
PRODUCT_CONFLICT_TARGET = ("source_provider", "source_product_id")
SAFE_OPERATION_FIELDS = (
    "source_provider",
    "source_product_id",
    "product_name",
    "normalized_product_name",
    "manufacturer",
    "category",
    "source_manifest_version",
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the dry-run importer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    return parser.parse_args()


def main() -> None:
    """Write a dry-run DB import plan and redacted summary."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        plan_rows, summary = build_dry_run_import_plan(
            input_path=args.input.expanduser().resolve(),
        )
    except (OSError, ValueError) as exc:
        failure = _failure_summary(input_path=args.input, error=exc)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None
    _reject_unsafe_payload({"plan_rows": plan_rows, "summary": summary})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in plan_rows),
        encoding="utf-8",
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_dry_run_import_plan(
    *,
    input_path: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return a dry-run DB import plan from approved import rows.

    Args:
        input_path: Approved DB import JSONL path.

    Returns:
        Operation plan rows and a redacted summary.

    Raises:
        ValueError: If raw fields, local path literals, duplicate source keys, or
            ORM boundary violations are found.
    """
    input_rows = _read_input_rows(input_path)
    seen_keys: set[tuple[str, str]] = set()
    plan_rows: list[dict[str, object]] = []
    ingredient_row_count = 0
    for row in input_rows:
        product_plan = _product_plan(row)
        conflict_key = (
            str(product_plan["source_provider"]),
            str(product_plan["source_product_id"]),
        )
        if conflict_key in seen_keys:
            raise ValueError(
                "Duplicate source_provider/source_product_id in approved DB import rows."
            )
        seen_keys.add(conflict_key)
        ingredient_plan = _ingredient_plan(row, conflict_key=conflict_key)
        ingredient_row_count += len(ingredient_plan["ingredients"])  # type: ignore[arg-type]
        plan_rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "operation": "upsert_reference_product_with_ingredients",
                "dry_run_only": True,
                "db_write_performed": False,
                "product": product_plan,
                "ingredient_replace_plan": ingredient_plan,
            }
        )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_name": input_path.name,
        "input_row_count": len(input_rows),
        "planned_product_upsert_count": len(plan_rows),
        "planned_ingredient_replace_count": len(plan_rows),
        "planned_ingredient_row_count": ingredient_row_count,
        "product_table": SupplementProduct.__tablename__,
        "ingredient_table": SupplementProductIngredient.__tablename__,
        "product_conflict_target": list(PRODUCT_CONFLICT_TARGET),
        "dry_run_only": True,
        "db_write_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload({"plan_rows": plan_rows, "summary": summary})
    return plan_rows, summary


def _failure_summary(*, input_path: Path, error: BaseException) -> dict[str, object]:
    """Return a redacted failure summary for CLI errors."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "input_name": input_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "planned_product_upsert_count": 0,
        "planned_ingredient_replace_count": 0,
        "planned_ingredient_row_count": 0,
        "dry_run_only": True,
        "db_write_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "clinical_recommendations_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _product_plan(row: dict[str, object]) -> dict[str, object]:
    """Return a validated product upsert plan for one approved row."""
    _validate_approved_import_row(row)
    product = {
        "table": SupplementProduct.__tablename__,
        "operation": "upsert",
        "conflict_target": list(PRODUCT_CONFLICT_TARGET),
    }
    for key in SAFE_OPERATION_FIELDS:
        value = row.get(key)
        if value is None:
            product[key] = None
            continue
        product[key] = _bounded_string_for_column(
            SupplementProduct,
            key,
            value,
            required=key
            in {
                "source_provider",
                "source_product_id",
                "product_name",
                "normalized_product_name",
            },
        )
    source_payload = _required_dict(row, "source_payload")
    product["source_payload_hash"] = _hash_json(source_payload)
    product["is_active"] = row.get("is_active") is True
    return product


def _ingredient_plan(
    row: dict[str, object],
    *,
    conflict_key: tuple[str, str],
) -> dict[str, object]:
    """Return a validated child ingredient replacement plan."""
    raw_ingredients = row.get("ingredients")
    if not isinstance(raw_ingredients, list) or not raw_ingredients:
        raise ValueError("Approved import row requires at least one ingredient.")
    ingredients: list[dict[str, object]] = []
    seen_sort_orders: set[int] = set()
    seen_ingredient_keys: set[tuple[str, str]] = set()
    for item in raw_ingredients:
        if not isinstance(item, dict):
            raise ValueError("Ingredient rows must be objects.")
        sort_order = _non_negative_int(item.get("sort_order"), field_name="sort_order")
        if sort_order in seen_sort_orders:
            raise ValueError("Ingredient sort_order values must be unique per product.")
        seen_sort_orders.add(sort_order)
        source_payload = _required_dict(item, "source_payload")
        amount = _decimal_or_none(item.get("amount"))
        standard_name = _bounded_string_for_column(
            SupplementProductIngredient,
            "standard_name",
            item.get("standard_name"),
            required=True,
        )
        validator.reject_packaging_quantity_ingredient_name(str(standard_name))
        nutrient_code = _bounded_string_for_column(
            SupplementProductIngredient,
            "nutrient_code",
            item.get("nutrient_code"),
        )
        dedupe_key = (_normalize_text(str(standard_name)), nutrient_code or "")
        if dedupe_key in seen_ingredient_keys:
            raise ValueError("Ingredient identities must be unique per product.")
        seen_ingredient_keys.add(dedupe_key)
        ingredient = {
            "standard_name": standard_name,
            "nutrient_code": nutrient_code,
            "amount": str(amount) if amount is not None else None,
            "unit": _bounded_string_for_column(
                SupplementProductIngredient,
                "unit",
                item.get("unit"),
            ),
            "sort_order": sort_order,
            "source_payload_hash": _hash_json(source_payload),
        }
        ingredients.append(ingredient)

    return {
        "table": SupplementProductIngredient.__tablename__,
        "operation": "replace_children_after_product_upsert",
        "parent_conflict_key": {
            "source_provider": conflict_key[0],
            "source_product_id": conflict_key[1],
        },
        "ingredient_count": len(ingredients),
        "ingredients": sorted(ingredients, key=lambda item: int(item["sort_order"])),
    }


def _validate_approved_import_row(row: dict[str, object]) -> None:
    """Validate schema, import gate, privacy, and clinical safety flags."""
    _reject_unsafe_payload(row)
    if row.get("schema_version") != EXPECTED_INPUT_SCHEMA_VERSION:
        raise ValueError("Dry-run input rows must use approved DB import schema.")
    if row.get("is_clinical_recommendation") is not False:
        raise ValueError("Approved DB import rows must not be clinical recommendations.")
    if row.get("clinical_recommendation_forbidden") is not True:
        raise ValueError("Approved DB import rows must keep clinical recommendation forbidden.")
    import_gate = _required_dict(row, "import_gate")
    required_gate = {
        "ready_for_db_import": True,
        "human_review_approved": True,
        "pii_screening_completed": True,
    }
    for key, expected_value in required_gate.items():
        if import_gate.get(key) is not expected_value:
            raise ValueError(f"Approved DB import row failed import gate: {key}")


def _read_input_rows(path: Path) -> list[dict[str, object]]:
    """Read approved DB import JSONL rows and reject unsafe payloads."""
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


def _bounded_string_for_column(
    model: type[Any],
    column_name: str,
    value: object,
    *,
    required: bool = False,
) -> str | None:
    """Return a string bounded by a SQLAlchemy String column length.

    Args:
        model: ORM model containing the target column.
        column_name: Column name to inspect.
        value: Candidate value.
        required: Whether missing/empty values should fail.

    Returns:
        Bounded string or None when optional and absent.

    Raises:
        ValueError: If the value is missing while required, not a string, leaks a
            local path literal, or exceeds the ORM String length.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError(f"Required column value is missing: {column_name}")
        return None
    if not isinstance(value, str):
        raise ValueError(f"Column value must be a string: {column_name}")
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    validator.reject_executable_text_value(stripped)
    max_length = _string_column_length(model, column_name)
    if max_length is not None and len(stripped) > max_length:
        raise ValueError(f"Column value exceeds {model.__name__}.{column_name} length.")
    return stripped


def _string_column_length(model: type[Any], column_name: str) -> int | None:
    """Return a SQLAlchemy String column length from ORM metadata."""
    column = model.__table__.columns[column_name]
    column_type = column.type
    if isinstance(column_type, String):
        return column_type.length
    return None


def _required_dict(row: dict[str, object], key: str) -> dict[str, object]:
    """Return a required object field."""
    value = row.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Row requires object field: {key}")
    _reject_unsafe_payload(value)
    return value


def _non_negative_int(value: object, *, field_name: str) -> int:
    """Return a non-negative integer value."""
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"Row requires non-negative integer field: {field_name}")
    return value


def _decimal_or_none(value: object) -> Decimal | None:
    """Return a Decimal compatible with the ORM numeric amount column."""
    if value is None:
        return None
    if not isinstance(value, int | float | str):
        raise ValueError("Ingredient amount must be numeric.")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Ingredient amount must be numeric.") from exc
    if amount < 0:
        raise ValueError("Ingredient amount must be non-negative.")
    if amount.as_tuple().exponent < -INGREDIENT_AMOUNT_SCALE:
        raise ValueError("Ingredient amount exceeds Numeric(14, 6) scale.")
    if len(amount.quantize(Decimal("1")).as_tuple().digits) > INGREDIENT_AMOUNT_INTEGER_DIGITS:
        raise ValueError("Ingredient amount exceeds Numeric(14, 6) precision.")
    return amount


def _hash_json(value: object) -> str:
    """Return a deterministic SHA-256 hash for a JSON-safe value."""
    _reject_unsafe_payload(value)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _normalize_text(value: str) -> str:
    """Return a conservative de-duplication key."""
    return " ".join(value.casefold().split())[:MAX_TOKEN_LENGTH]


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
