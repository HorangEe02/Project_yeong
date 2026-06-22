"""Gate supplement category seed DB apply after category-only dry-run.

The gate consumes redacted summaries from taxonomy staging and the approved
taxonomy importer dry-run. It allows only category seed DB apply readiness and
keeps brand/product/product-category writes blocked until reviewed product rows
exist and pass their own strict dry-run.

It does not read source images, JSONL row payloads, OCR text, provider payloads,
LLM outputs, or database records.

References:
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
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

from scripts import build_supplement_taxonomy_db_staging as staging  # noqa: E402
from scripts import import_supplement_taxonomy_approved_manifest as importer  # noqa: E402

SCHEMA_VERSION = "supplement-category-seed-db-apply-gate-v1"
READY_STATUS = "ready_for_category_seed_db_apply"
BLOCKED_STATUS = "blocked_by_category_seed_preflight"
ERROR_STATUS = "error"
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/json.html",
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
)
READY_NEXT_STEPS = (
    "run_taxonomy_category_seed_apply_with_no_product_manifest",
    "run_taxonomy_category_seed_db_verifier",
    "continue_brand_product_operator_review",
)
BLOCKED_NEXT_STEPS = (
    "rerun_taxonomy_staging_export",
    "rerun_category_only_import_dry_run",
    "rerun_category_seed_db_apply_gate",
)
RAW_FORBIDDEN_KEYS = staging.RAW_FORBIDDEN_KEYS.union(
    {
        "object_uri",
        "owner_hash",
        "owner_subject",
        "owner_subject_hash",
        "provider_response",
    }
)
LOCAL_PATH_MARKERS = staging.LOCAL_PATH_MARKERS


class CategorySeedApplyGateError(ValueError):
    """Raised when category seed apply gate inputs cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy-staging-summary", type=Path, required=True)
    parser.add_argument("--category-only-import-dry-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a category seed DB apply gate report.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "taxonomy_staging_summary": args.taxonomy_staging_summary.expanduser().resolve(),
        "category_only_import_dry_run": args.category_only_import_dry_run.expanduser().resolve(),
    }
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = build_category_seed_apply_gate(input_paths=input_paths)
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, CategorySeedApplyGateError, ValueError) as exc:
        failure = _failure_summary(output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_category_seed_apply_gate(*, input_paths: Mapping[str, Path]) -> dict[str, Any]:
    """Build a category seed apply gate from redacted summary artifacts.

    Args:
        input_paths: Required summary artifact paths.

    Returns:
        Redacted gate summary.

    Raises:
        CategorySeedApplyGateError: If an input is missing, unsafe, or unsupported.
    """
    staging_summary_path = _required_input(input_paths, "taxonomy_staging_summary")
    dry_run_path = _required_input(input_paths, "category_only_import_dry_run")
    staging_summary = _load_json_object(staging_summary_path)
    dry_run = _load_json_object(dry_run_path)
    _require_schema(staging_summary, staging.SCHEMA_VERSION)
    _require_schema(dry_run, importer.SCHEMA_VERSION)
    _reject_unsafe_payload(staging_summary)
    _reject_unsafe_payload(dry_run)

    category_count = _positive_int(staging_summary.get("category_seed_row_count"))
    brand_candidate_count = _non_negative_int(staging_summary.get("brand_candidate_row_count"))
    approved_for_db_write_count = _non_negative_int(
        staging_summary.get("approved_for_db_write_row_count")
    )
    dry_run_category_count = _non_negative_int(dry_run.get("category_seed_row_count"))
    dry_run_product_count = _non_negative_int(dry_run.get("approved_product_import_row_count"))
    planned_category_upsert_count = _non_negative_int(dry_run.get("planned_category_upsert_count"))
    planned_product_upsert_count = _non_negative_int(dry_run.get("planned_product_upsert_count"))
    planned_product_category_upsert_count = _non_negative_int(
        dry_run.get("planned_product_category_upsert_count")
    )
    db_write_contract = _mapping(staging_summary.get("db_write_contract"))
    conditions = {
        "category_rows_seedable": db_write_contract.get("category_rows_seedable") is True,
        "brand_rows_review_gated": db_write_contract.get(
            "brand_candidate_rows_seedable_without_review"
        )
        is False,
        "approved_count_matches_category_count": approved_for_db_write_count == category_count,
        "dry_run_category_count_matches": dry_run_category_count == category_count,
        "dry_run_has_no_product_manifest": dry_run.get("product_import_manifest_name") is None,
        "dry_run_has_no_product_rows": dry_run_product_count == 0,
        "dry_run_plans_only_category_upserts": planned_category_upsert_count == category_count
        and planned_product_upsert_count == 0
        and planned_product_category_upsert_count == 0,
        "dry_run_is_preflight_only": dry_run.get("preflight_only") is True,
        "dry_run_performed_no_db_write": dry_run.get("db_write_performed") is False,
        "dry_run_ready_for_db_write": dry_run.get("ready_for_db_write") is True,
        "dry_run_apply_not_requested": dry_run.get("apply_requested") is False,
        "dry_run_did_not_require_approved_products": dry_run.get("require_approved_products")
        is False,
    }
    failed_conditions = sorted(key for key, value in conditions.items() if not value)
    allowed = not failed_conditions
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": READY_STATUS if allowed else BLOCKED_STATUS,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _sha256_text(str(path.expanduser())) for key, path in sorted(input_paths.items())
        },
        "category_seed_row_count": category_count,
        "brand_candidate_row_count": brand_candidate_count,
        "approved_for_db_write_row_count": approved_for_db_write_count,
        "planned_category_upsert_count": planned_category_upsert_count,
        "planned_product_upsert_count": planned_product_upsert_count,
        "planned_product_category_upsert_count": planned_product_category_upsert_count,
        "conditions": conditions,
        "failed_conditions": failed_conditions,
        "category_seed_db_apply_allowed": allowed,
        "product_db_apply_allowed": False,
        "product_category_db_apply_allowed": False,
        "db_write_performed": False,
        "database_connection_opened": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
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
        summary: Gate summary.

    Returns:
        Markdown text.
    """
    _reject_unsafe_payload(summary)
    conditions = _mapping(summary["conditions"])
    condition_lines = "\n".join(
        f"- `{_safe_token(str(key))}`: `{_bool_text(value)}`"
        for key, value in sorted(conditions.items())
    )
    next_steps = "\n".join(f"- `{_safe_token(str(step))}`" for step in summary["next_steps"])
    failed_conditions = _markdown_token_list(summary.get("failed_conditions"))
    markdown = "\n".join(
        [
            "# Supplement Category Seed DB Apply Gate",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "이 문서는 category seed DB apply 가능 여부만 판단합니다. 제품/브랜드/product-category DB write는 계속 차단합니다.",
            "",
            f"- Status: `{_safe_token(str(summary.get('status') or 'unknown'))}`",
            f"- Category seed apply allowed: `{_bool_text(summary.get('category_seed_db_apply_allowed'))}`",
            f"- Product apply allowed: `{_bool_text(summary.get('product_db_apply_allowed'))}`",
            f"- Product-category apply allowed: `{_bool_text(summary.get('product_category_db_apply_allowed'))}`",
            "",
            "## Counts",
            "",
            f"- Category seed rows: `{_non_negative_int(summary.get('category_seed_row_count'))}`",
            f"- Brand candidate rows: `{_non_negative_int(summary.get('brand_candidate_row_count'))}`",
            f"- Planned category upserts: `{_non_negative_int(summary.get('planned_category_upsert_count'))}`",
            f"- Planned product upserts: `{_non_negative_int(summary.get('planned_product_upsert_count'))}`",
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
            "Category seed apply가 허용되어도 제품/브랜드 DB 저장은 별도 strict brand review와 approved product dry-run이 통과하기 전까지 진행하지 않습니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load one JSON object.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CategorySeedApplyGateError("Gate input must be a JSON object.")
    return payload


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return an existing input path.

    Args:
        input_paths: Input path mapping.
        key: Required key.

    Returns:
        Existing input path.
    """
    path = input_paths.get(key)
    if path is None or not path.is_file():
        raise CategorySeedApplyGateError("Required gate input is missing.")
    return path


def _require_schema(payload: Mapping[str, Any], expected_schema: str) -> None:
    """Validate an input schema version.

    Args:
        payload: Parsed input.
        expected_schema: Required schema version.
    """
    if payload.get("schema_version") != expected_schema:
        raise CategorySeedApplyGateError("Gate input schema does not match.")


def _mapping(value: Any) -> Mapping[str, Any]:
    """Return a mapping or fail closed.

    Args:
        value: Candidate mapping.

    Returns:
        Mapping value.
    """
    if not isinstance(value, Mapping):
        raise CategorySeedApplyGateError("Expected a mapping.")
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
        raise CategorySeedApplyGateError("Expected a positive integer.")
    return number


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate integer.

    Returns:
        Non-negative integer.
    """
    if not isinstance(value, int) or value < 0:
        raise CategorySeedApplyGateError("Expected a non-negative integer.")
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
        raise CategorySeedApplyGateError("Unsafe token.")
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
        raise CategorySeedApplyGateError("Expected a token sequence.")
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
    """Reject raw OCR/provider payloads and local path literals.

    Args:
        value: Candidate JSON-like payload.

    Raises:
        CategorySeedApplyGateError: If unsafe content is present.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_PATH_MARKERS:
        if marker in serialized:
            raise CategorySeedApplyGateError("Gate payload contains a local path literal.")
    _reject_raw_keys(value)


def _reject_raw_keys(value: Any) -> None:
    """Recursively reject raw or sensitive keys.

    Args:
        value: Candidate JSON-like value.
    """
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in RAW_FORBIDDEN_KEYS:
                raise CategorySeedApplyGateError("Gate payload contains a raw key.")
            _reject_raw_keys(child)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for child in value:
            _reject_raw_keys(child)


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for a non-secret local identifier.

    Args:
        value: Text value.

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
        summary: Gate summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": summary["status"],
        "category_seed_row_count": summary["category_seed_row_count"],
        "planned_category_upsert_count": summary["planned_category_upsert_count"],
        "category_seed_db_apply_allowed": summary["category_seed_db_apply_allowed"],
        "product_db_apply_allowed": False,
        "db_write_performed": False,
    }


def _failure_summary(*, output_path: Path, error: Exception) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        output_path: Planned output path.
        error: Raised exception.

    Returns:
        Redacted failure payload.
    """
    _ = error
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": ERROR_STATUS,
        "generated_at": datetime.now(UTC).isoformat(),
        "output_name": output_path.name,
        "category_seed_db_apply_allowed": False,
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
