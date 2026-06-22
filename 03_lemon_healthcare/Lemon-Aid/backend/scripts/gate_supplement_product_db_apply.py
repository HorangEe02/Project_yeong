"""Gate reviewed supplement product/category-map DB apply.

This gate is intentionally downstream from operator brand review. It consumes
only redacted summaries:

* brand DB import gate
* approved taxonomy import dry-run
* category DB verifier
* local DB target preflight

It never reads source images, product folders, raw OCR, provider payloads, or
approved product manifest row payloads. A product DB apply is allowed only after
strict brand review, a non-empty approved-product dry-run, verified category
seeds, and a local development DB target check all pass.

References:
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
    https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import gate_supplement_brand_db_import as brand_gate  # noqa: E402
from scripts import import_supplement_taxonomy_approved_manifest as importer  # noqa: E402
from scripts import preflight_supplement_category_seed_db_target as target_preflight  # noqa: E402
from scripts import verify_supplement_taxonomy_db_import as verifier  # noqa: E402

SCHEMA_VERSION = "supplement-product-db-apply-gate-v1"
READY_STATUS = "ready_for_reviewed_product_db_apply"
BLOCKED_STATUS = "blocked_by_product_db_apply_preflight"
ERROR_STATUS = "error"
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/json.html",
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
    "https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html",
)
READY_NEXT_STEPS = (
    "run_taxonomy_approved_manifest_db_apply_with_product_manifest",
    "run_taxonomy_db_import_verifier_require_approved_products",
    "rerun_learning_dependency_audit",
)
BLOCKED_NEXT_STEPS = (
    "complete_operator_brand_review",
    "build_approved_product_import_manifest",
    "run_taxonomy_approved_manifest_import_dry_run_require_approved_products",
    "rerun_category_seed_db_target_preflight",
    "rerun_product_db_apply_gate",
)


class ProductDbApplyGateError(ValueError):
    """Raised when product DB apply gate inputs cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand-db-import-gate", type=Path, required=True)
    parser.add_argument("--approved-import-dry-run", type=Path, required=True)
    parser.add_argument("--category-db-verify", type=Path, required=True)
    parser.add_argument("--db-target-preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a reviewed product DB apply gate report.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "brand_db_import_gate": args.brand_db_import_gate.expanduser().resolve(),
        "approved_import_dry_run": args.approved_import_dry_run.expanduser().resolve(),
        "category_db_verify": args.category_db_verify.expanduser().resolve(),
        "db_target_preflight": args.db_target_preflight.expanduser().resolve(),
    }
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = build_product_db_apply_gate(input_paths=input_paths)
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, ProductDbApplyGateError, ValueError) as exc:
        failure = _failure_summary(output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_product_db_apply_gate(*, input_paths: Mapping[str, Path]) -> dict[str, Any]:
    """Build a reviewed product DB apply gate from redacted summaries.

    Args:
        input_paths: Required summary artifact paths.

    Returns:
        Redacted product DB apply gate summary.

    Raises:
        ProductDbApplyGateError: If an input is missing, unsafe, or unsupported.
    """
    paths = {key: _required_input(input_paths, key) for key in _required_input_keys()}
    brand_payload = _load_json_object(paths["brand_db_import_gate"])
    dry_run_payload = _load_json_object(paths["approved_import_dry_run"])
    verify_payload = _load_json_object(paths["category_db_verify"])
    target_payload = _load_json_object(paths["db_target_preflight"])
    for payload in (brand_payload, dry_run_payload, verify_payload, target_payload):
        _reject_unsafe_payload(payload)

    _require_schema(brand_payload, brand_gate.SCHEMA_VERSION)
    _require_schema(dry_run_payload, importer.SCHEMA_VERSION)
    _require_schema(verify_payload, verifier.SCHEMA_VERSION)
    _require_schema(target_payload, target_preflight.SCHEMA_VERSION)

    category_count = _positive_int(dry_run_payload.get("category_seed_row_count"))
    approved_product_count = _non_negative_int(
        dry_run_payload.get("approved_product_import_row_count")
    )
    planned_product_count = _non_negative_int(dry_run_payload.get("planned_product_upsert_count"))
    planned_product_category_count = _non_negative_int(
        dry_run_payload.get("planned_product_category_upsert_count")
    )
    expected_category_count = _positive_int(verify_payload.get("expected_category_count"))
    matched_category_count = _non_negative_int(verify_payload.get("matched_category_count"))

    conditions = {
        "brand_gate_ready_for_manifest": brand_payload.get("status") == brand_gate.READY_STATUS,
        "brand_gate_allows_manifest": brand_payload.get("product_import_manifest_allowed") is True,
        "brand_gate_does_not_allow_direct_db_apply": brand_payload.get(
            "db_import_apply_allowed_now"
        )
        is False,
        "brand_gate_allows_db_apply_after_dry_run": brand_payload.get(
            "db_import_apply_allowed_after_dry_run"
        )
        is True,
        "dry_run_ready_for_db_write": dry_run_payload.get("ready_for_db_write") is True,
        "dry_run_is_preflight_only": dry_run_payload.get("preflight_only") is True,
        "dry_run_apply_not_requested": dry_run_payload.get("apply_requested") is False,
        "dry_run_performed_no_db_write": dry_run_payload.get("db_write_performed") is False,
        "dry_run_required_approved_products": dry_run_payload.get("require_approved_products")
        is True,
        "dry_run_has_product_manifest": dry_run_payload.get("product_import_manifest_name")
        is not None,
        "dry_run_has_approved_products": approved_product_count > 0,
        "dry_run_plans_product_rows": planned_product_count == approved_product_count,
        "dry_run_plans_product_category_rows": planned_product_category_count
        == approved_product_count,
        "category_verify_performed_no_db_write": verify_payload.get("db_write_performed") is False,
        "category_verify_required_categories_present": matched_category_count == category_count
        and verify_payload.get("missing_category_count") == 0,
        "category_verify_counts_match_dry_run": expected_category_count == category_count
        and matched_category_count == category_count,
        "category_verify_has_no_missing_categories": verify_payload.get("missing_category_count")
        == 0,
        "db_target_preflight_ready": target_payload.get("status") == target_preflight.READY_STATUS,
        "db_target_allows_category_seed_apply": target_payload.get(
            "category_seed_db_apply_target_allowed"
        )
        is True,
        "db_target_is_local": target_payload.get("database_host_class") == "local",
        "db_target_performed_no_db_write": target_payload.get("db_write_performed") is False,
        "db_target_opened_no_connection": target_payload.get("db_connection_opened") is False,
    }
    failed_conditions = sorted(key for key, value in conditions.items() if not value)
    allowed = not failed_conditions
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": READY_STATUS if allowed else BLOCKED_STATUS,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: paths[key].name for key in sorted(paths)},
        "input_path_hashes": {key: _sha256_text(str(paths[key])) for key in sorted(paths)},
        "brand_candidate_count": _non_negative_int(brand_payload.get("brand_candidate_count")),
        "approved_decision_count": _non_negative_int(brand_payload.get("approved_decision_count")),
        "category_seed_row_count": category_count,
        "approved_product_import_row_count": approved_product_count,
        "planned_product_upsert_count": planned_product_count,
        "planned_product_category_upsert_count": planned_product_category_count,
        "matched_category_count": matched_category_count,
        "missing_category_count": _non_negative_int(verify_payload.get("missing_category_count")),
        "conditions": conditions,
        "failed_conditions": failed_conditions,
        "product_db_apply_allowed": allowed,
        "product_category_db_apply_allowed": allowed,
        "category_upsert_allowed_during_product_apply": allowed,
        "db_write_performed": False,
        "database_connection_opened": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "next_steps": list(READY_NEXT_STEPS if allowed else BLOCKED_NEXT_STEPS),
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown gate report.

    Args:
        summary: Product DB apply gate summary.

    Returns:
        Markdown report text.
    """
    _reject_unsafe_payload(summary)
    conditions = _mapping(summary["conditions"])
    condition_lines = "\n".join(
        f"- `{_safe_token(str(key))}`: `{_bool_text(value)}`"
        for key, value in sorted(conditions.items())
    )
    failed_conditions = _markdown_token_list(summary.get("failed_conditions"))
    next_steps = "\n".join(f"- `{_safe_token(str(step))}`" for step in summary["next_steps"])
    markdown = "\n".join(
        [
            "# Supplement Product DB Apply Gate",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "이 문서는 reviewed product/product-category DB apply 직전 조건만 확인합니다. DB write는 수행하지 않습니다.",
            "",
            f"- Status: `{_safe_token(str(summary.get('status') or 'unknown'))}`",
            f"- Product DB apply allowed: `{_bool_text(summary.get('product_db_apply_allowed'))}`",
            f"- Product-category DB apply allowed: `{_bool_text(summary.get('product_category_db_apply_allowed'))}`",
            "",
            "## Counts",
            "",
            f"- Brand candidates: `{_non_negative_int(summary.get('brand_candidate_count'))}`",
            f"- Approved decisions: `{_non_negative_int(summary.get('approved_decision_count'))}`",
            f"- Category seed rows: `{_non_negative_int(summary.get('category_seed_row_count'))}`",
            f"- Approved product import rows: `{_non_negative_int(summary.get('approved_product_import_row_count'))}`",
            f"- Planned product upserts: `{_non_negative_int(summary.get('planned_product_upsert_count'))}`",
            f"- Planned product-category upserts: `{_non_negative_int(summary.get('planned_product_category_upsert_count'))}`",
            f"- Matched categories: `{_non_negative_int(summary.get('matched_category_count'))}`",
            f"- Missing categories: `{_non_negative_int(summary.get('missing_category_count'))}`",
            "",
            "## Conditions",
            "",
            condition_lines,
            "",
            "## Failed Conditions",
            "",
            failed_conditions,
            "",
            "## Next Steps",
            "",
            next_steps,
            "",
            "## Rule",
            "",
            "제품/브랜드 DB 저장은 strict brand review, approved product manifest dry-run, category verifier, local DB target preflight가 모두 통과할 때만 허용합니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _required_input_keys() -> tuple[str, ...]:
    """Return required input mapping keys.

    Returns:
        Required key names.
    """
    return (
        "brand_db_import_gate",
        "approved_import_dry_run",
        "category_db_verify",
        "db_target_preflight",
    )


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return one existing input artifact path.

    Args:
        input_paths: Input artifact mapping.
        key: Required key.

    Returns:
        Existing artifact path.
    """
    path = input_paths.get(key)
    if path is None or not path.is_file():
        raise ProductDbApplyGateError("Required gate input is missing.")
    return path


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load one JSON object.

    Args:
        path: JSON path.

    Returns:
        Parsed JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProductDbApplyGateError("Gate input must be a JSON object.")
    return payload


def _require_schema(payload: Mapping[str, Any], expected_schema: str) -> None:
    """Validate schema version.

    Args:
        payload: Parsed payload.
        expected_schema: Required schema version.
    """
    if payload.get("schema_version") != expected_schema:
        raise ProductDbApplyGateError("Gate input schema does not match.")


def _mapping(value: Any) -> Mapping[str, Any]:
    """Return a mapping or fail closed.

    Args:
        value: Candidate mapping.

    Returns:
        Mapping value.
    """
    if not isinstance(value, Mapping):
        raise ProductDbApplyGateError("Expected a mapping.")
    return value


def _positive_int(value: Any) -> int:
    """Return a positive integer.

    Args:
        value: Candidate integer.

    Returns:
        Positive integer.
    """
    number = _non_negative_int(value)
    if number == 0:
        raise ProductDbApplyGateError("Expected a positive integer.")
    return number


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate integer.

    Returns:
        Non-negative integer.
    """
    if not isinstance(value, int) or value < 0:
        raise ProductDbApplyGateError("Expected a non-negative integer.")
    return value


def _safe_token(value: str) -> str:
    """Return a conservative token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789가-힣_:-.")
    if not value or any(char not in allowed for char in value):
        raise ProductDbApplyGateError("Unsafe token.")
    return value


def _markdown_token_list(value: Any) -> str:
    """Return Markdown bullets for safe tokens.

    Args:
        value: Candidate token list.

    Returns:
        Markdown bullet list.
    """
    if value is None:
        return "- none"
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ProductDbApplyGateError("Expected a token sequence.")
    if not value:
        return "- none"
    return "\n".join(f"- `{_safe_token(str(item))}`" for item in value)


def _bool_text(value: object) -> str:
    """Return lowercase boolean text.

    Args:
        value: Candidate boolean.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value is True else "false"


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw OCR/provider payloads, local paths, and DB URL literals.

    Args:
        value: Candidate JSON-like value.
    """
    try:
        brand_gate._reject_unsafe_payload(value)
    except ValueError as exc:
        raise ProductDbApplyGateError("Gate payload contains unsafe content.") from exc
    _reject_unsafe_keys(value)
    _reject_unsafe_strings(value)


def _reject_unsafe_keys(value: Any) -> None:
    """Reject exact raw/sensitive keys without blocking safe boolean flags.

    Args:
        value: Candidate JSON-like value.
    """
    forbidden_keys = {
        "database_url",
        "db_url",
        "image_bytes",
        "object_uri",
        "owner_hash",
        "owner_subject",
        "password",
        "provider_payload",
        "provider_response",
        "raw_ocr_text",
        "secret",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in forbidden_keys:
                raise ProductDbApplyGateError("Gate payload contains unsafe content.")
            _reject_unsafe_keys(child)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for child in value:
            _reject_unsafe_keys(child)


def _reject_unsafe_strings(value: Any) -> None:
    """Reject raw URL/path literals from string values.

    Args:
        value: Candidate JSON-like value.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    forbidden = (
        "/Volumes/",
        "/Users/",
        "/private/",
        "postgresql+asyncpg://",
        "postgresql://",
    )
    if any(marker in serialized for marker in forbidden):
        raise ProductDbApplyGateError("Gate payload contains unsafe content.")


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for a local artifact identifier.

    Args:
        value: Text to hash.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    _reject_unsafe_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI-safe summary.

    Args:
        summary: Full gate summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": summary["status"],
        "approved_product_import_row_count": summary["approved_product_import_row_count"],
        "product_db_apply_allowed": summary["product_db_apply_allowed"],
        "product_category_db_apply_allowed": summary["product_category_db_apply_allowed"],
        "db_write_performed": False,
    }


def _failure_summary(*, output_path: Path, error: Exception) -> dict[str, Any]:
    """Return a redacted failure payload.

    Args:
        output_path: Planned output path.
        error: Raised exception.

    Returns:
        Failure summary.
    """
    _ = error
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": ERROR_STATUS,
        "generated_at": datetime.now(UTC).isoformat(),
        "output_name": output_path.name,
        "product_db_apply_allowed": False,
        "product_category_db_apply_allowed": False,
        "db_write_performed": False,
        "database_connection_opened": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


if __name__ == "__main__":
    main()
