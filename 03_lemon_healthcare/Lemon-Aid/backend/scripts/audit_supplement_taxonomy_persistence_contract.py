"""Audit supplement taxonomy persistence contracts without touching source data.

This read-only audit verifies that the supplement taxonomy persistence path has
the expected category, product, and product-category mapping tables plus the
staging/import/verification scripts required before a reviewed DB import. It
does not open a database connection, read crawling-image rows, inspect source
images, run OCR, call external providers, or write taxonomy records.

References:
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
    https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Table

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.models.db.supplement import (  # noqa: E402
    SupplementCategory,
    SupplementProduct,
    SupplementProductCategory,
)

from scripts import build_supplement_taxonomy_db_staging as staging  # noqa: E402
from scripts import import_supplement_taxonomy_approved_manifest as importer  # noqa: E402
from scripts import verify_supplement_taxonomy_db_import as verifier  # noqa: E402

SCHEMA_VERSION = "supplement-taxonomy-persistence-contract-audit-v1"
READY_STATUS = "ready_for_reviewed_import_dry_run"
BLOCKED_STATUS = "blocked_by_contract_gap"
ERROR_STATUS = "error"
SOURCE_DOC_URLS = (
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
    "https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html",
)
LOCAL_PATH_MARKERS = staging.LOCAL_PATH_MARKERS
RAW_FORBIDDEN_KEYS = staging.RAW_FORBIDDEN_KEYS.union(
    {
        "object_uri",
        "owner_hash",
        "owner_subject",
        "owner_subject_hash",
        "provider_response",
        "source_image_path",
    }
)
SUPPLEMENT_TABLES = (
    "supplement_categories",
    "supplement_products",
    "supplement_product_categories",
)
REQUIRED_TABLE_COLUMNS = {
    "supplement_categories": frozenset(
        {
            "id",
            "category_key",
            "display_name",
            "source_folder_name",
            "source_payload",
            "source_manifest_version",
            "sort_order",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "supplement_products": frozenset(
        {
            "id",
            "source_provider",
            "source_product_id",
            "product_name",
            "normalized_product_name",
            "manufacturer",
            "category",
            "source_payload",
            "source_manifest_version",
            "imported_at",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "supplement_product_categories": frozenset(
        {
            "id",
            "product_id",
            "category_id",
            "source",
            "confidence",
            "is_primary",
            "source_payload",
            "sort_order",
            "created_at",
            "updated_at",
        }
    ),
}
REQUIRED_UNIQUE_CONSTRAINTS = {
    "supplement_categories": frozenset({"uq_supplement_categories_category_key"}),
    "supplement_products": frozenset({"uq_supplement_products_source_provider_product_id"}),
    "supplement_product_categories": frozenset(
        {"uq_supplement_product_categories_product_category"}
    ),
}
REQUIRED_INDEXES = {
    "supplement_categories": frozenset({"ix_supplement_categories_active_sort"}),
    "supplement_products": frozenset({"ix_supplement_products_normalized_name"}),
    "supplement_product_categories": frozenset(
        {
            "ix_supplement_product_categories_category_id",
            "ix_supplement_product_categories_product_id",
        }
    ),
}
UNSAFE_STORAGE_COLUMN_NAMES = frozenset(
    {
        "image_bytes",
        "image_path",
        "local_path",
        "object_uri",
        "owner_hash",
        "owner_subject",
        "owner_subject_hash",
        "provider_payload",
        "raw_image",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
    }
)
NEXT_STEPS_READY = (
    "run_taxonomy_db_staging_export",
    "complete_brand_product_operator_review",
    "run_taxonomy_approved_manifest_import_dry_run",
    "run_taxonomy_db_import_verifier_after_apply",
)
NEXT_STEPS_BLOCKED = (
    "fix_missing_model_or_migration_contract",
    "rerun_taxonomy_persistence_contract_audit",
)


class TaxonomyPersistenceAuditError(ValueError):
    """Raised when taxonomy persistence contract evidence cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write taxonomy persistence contract audit artifacts.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    repo_root = args.repo_root.expanduser().resolve()
    try:
        summary = build_taxonomy_persistence_contract_audit(repo_root=repo_root)
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, TaxonomyPersistenceAuditError, ValueError) as exc:
        failure = _failure_summary(output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_taxonomy_persistence_contract_audit(*, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build a read-only audit of taxonomy DB persistence contracts.

    Args:
        repo_root: Lemon-Aid repository root.

    Returns:
        Redacted audit summary.
    """
    table_map = {
        "supplement_categories": SupplementCategory.__table__,
        "supplement_products": SupplementProduct.__table__,
        "supplement_product_categories": SupplementProductCategory.__table__,
    }
    column_contracts = _column_contracts(table_map=table_map)
    constraint_contracts = _constraint_contracts(table_map=table_map)
    index_contracts = _index_contracts(table_map=table_map)
    relationship_contract = _relationship_contract(table_map=table_map)
    script_contract = _script_contract()
    migration_contract = _migration_contract(repo_root=repo_root)
    test_contract = _test_contract(repo_root=repo_root)
    unsafe_storage_contract = _unsafe_storage_contract(
        table_map=table_map,
        migration_contract=migration_contract,
    )

    blocked_reasons = _blocked_reasons(
        column_contracts=column_contracts,
        constraint_contracts=constraint_contracts,
        index_contracts=index_contracts,
        relationship_contract=relationship_contract,
        script_contract=script_contract,
        migration_contract=migration_contract,
        test_contract=test_contract,
        unsafe_storage_contract=unsafe_storage_contract,
    )
    status = READY_STATUS if not blocked_reasons else BLOCKED_STATUS
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "model_tables": list(SUPPLEMENT_TABLES),
        "column_contracts": column_contracts,
        "constraint_contracts": constraint_contracts,
        "index_contracts": index_contracts,
        "relationship_contract": relationship_contract,
        "script_contract": script_contract,
        "migration_contract": migration_contract,
        "test_contract": test_contract,
        "unsafe_storage_contract": unsafe_storage_contract,
        "blocked_reasons": blocked_reasons,
        "reviewed_import_dry_run_allowed": status == READY_STATUS,
        "db_import_apply_allowed_now": False,
        "db_import_apply_requires_operator_brand_review": True,
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
        "next_steps": list(NEXT_STEPS_READY if status == READY_STATUS else NEXT_STEPS_BLOCKED),
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown audit report.

    Args:
        summary: Audit summary.

    Returns:
        Markdown report.
    """
    _reject_unsafe_payload(summary)
    table_lines = []
    for table_name in SUPPLEMENT_TABLES:
        contract = _mapping(summary["column_contracts"])[table_name]
        table_lines.append(
            "| {table} | {required} | {missing} |".format(
                table=_safe_token(table_name),
                required=_bool_text(_mapping(contract)["all_required_columns_present"]),
                missing=_non_negative_int(_mapping(contract)["missing_column_count"]),
            )
        )
    next_steps = "\n".join(f"- `{_safe_token(str(step))}`" for step in summary["next_steps"])
    blocked = _markdown_token_list(summary.get("blocked_reasons"))
    markdown = "\n".join(
        [
            "# Supplement Taxonomy Persistence Contract Audit",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "이 문서는 영양제 category, product, product-category mapping 저장 계약을 aggregate 수준에서 확인합니다. DB 접속, 원본 이미지 스캔, OCR 호출, 제품명 출력은 수행하지 않습니다.",
            "",
            f"- Status: `{_safe_token(str(summary.get('status') or 'unknown'))}`",
            f"- Reviewed import dry-run allowed: `{_bool_text(summary.get('reviewed_import_dry_run_allowed'))}`",
            f"- DB apply allowed now: `{_bool_text(summary.get('db_import_apply_allowed_now'))}`",
            "",
            "## Required Tables",
            "",
            "| Table | Required columns present | Missing column count |",
            "| --- | --- | --- |",
            *table_lines,
            "",
            "## Contracts",
            "",
            f"- Relationship contract valid: `{_bool_text(_mapping(summary['relationship_contract'])['valid'])}`",
            f"- Script contract valid: `{_bool_text(_mapping(summary['script_contract'])['valid'])}`",
            f"- Migration contract valid: `{_bool_text(_mapping(summary['migration_contract'])['valid'])}`",
            f"- Test contract valid: `{_bool_text(_mapping(summary['test_contract'])['valid'])}`",
            f"- Unsafe storage absent: `{_bool_text(_mapping(summary['unsafe_storage_contract'])['valid'])}`",
            "",
            "## Blocked Reasons",
            "",
            blocked,
            "",
            "## Next Steps",
            "",
            next_steps,
            "",
            "## Rule",
            "",
            "현재 스크립트는 reviewed import dry-run 가능 여부만 판정합니다. 실제 DB apply는 brand/product operator review와 dry-run이 통과한 뒤 별도 명령으로만 실행합니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _column_contracts(*, table_map: Mapping[str, Table]) -> dict[str, dict[str, Any]]:
    """Return required-column status for each taxonomy table.

    Args:
        table_map: SQLAlchemy table mapping.

    Returns:
        Column contract summaries keyed by table name.
    """
    contracts: dict[str, dict[str, Any]] = {}
    for table_name, required_columns in REQUIRED_TABLE_COLUMNS.items():
        actual_columns = set(table_map[table_name].c.keys())
        missing_columns = sorted(required_columns - actual_columns)
        extra_contract_columns = sorted(actual_columns.intersection(UNSAFE_STORAGE_COLUMN_NAMES))
        contracts[table_name] = {
            "required_column_count": len(required_columns),
            "present_required_column_count": len(required_columns) - len(missing_columns),
            "missing_column_count": len(missing_columns),
            "missing_columns": [_safe_token(name) for name in missing_columns],
            "unsafe_column_count": len(extra_contract_columns),
            "unsafe_columns": [_safe_token(name) for name in extra_contract_columns],
            "all_required_columns_present": not missing_columns,
        }
    return contracts


def _constraint_contracts(*, table_map: Mapping[str, Table]) -> dict[str, dict[str, Any]]:
    """Return required unique-constraint status.

    Args:
        table_map: SQLAlchemy table mapping.

    Returns:
        Constraint contract summaries keyed by table name.
    """
    contracts: dict[str, dict[str, Any]] = {}
    for table_name, required_names in REQUIRED_UNIQUE_CONSTRAINTS.items():
        actual_names = {
            str(constraint.name)
            for constraint in table_map[table_name].constraints
            if constraint.name
        }
        missing_names = sorted(required_names - actual_names)
        contracts[table_name] = {
            "required_constraint_count": len(required_names),
            "missing_constraint_count": len(missing_names),
            "missing_constraints": [_safe_token(name) for name in missing_names],
            "all_required_constraints_present": not missing_names,
        }
    return contracts


def _index_contracts(*, table_map: Mapping[str, Table]) -> dict[str, dict[str, Any]]:
    """Return required-index status.

    Args:
        table_map: SQLAlchemy table mapping.

    Returns:
        Index contract summaries keyed by table name.
    """
    contracts: dict[str, dict[str, Any]] = {}
    for table_name, required_names in REQUIRED_INDEXES.items():
        actual_names = {str(index.name) for index in table_map[table_name].indexes if index.name}
        missing_names = sorted(required_names - actual_names)
        contracts[table_name] = {
            "required_index_count": len(required_names),
            "missing_index_count": len(missing_names),
            "missing_indexes": [_safe_token(name) for name in missing_names],
            "all_required_indexes_present": not missing_names,
        }
    return contracts


def _relationship_contract(*, table_map: Mapping[str, Table]) -> dict[str, Any]:
    """Return product/category foreign-key contract status.

    Args:
        table_map: SQLAlchemy table mapping.

    Returns:
        Relationship contract summary.
    """
    mapping_table = table_map["supplement_product_categories"]
    product_targets = _foreign_key_targets(mapping_table, "product_id")
    category_targets = _foreign_key_targets(mapping_table, "category_id")
    product_fk_present = "supplement_products.id" in product_targets
    category_fk_present = "supplement_categories.id" in category_targets
    return {
        "valid": product_fk_present and category_fk_present,
        "product_fk_present": product_fk_present,
        "category_fk_present": category_fk_present,
        "product_delete_policy": _safe_token(_foreign_key_ondelete(mapping_table, "product_id")),
        "category_delete_policy": _safe_token(_foreign_key_ondelete(mapping_table, "category_id")),
    }


def _foreign_key_targets(table: Table, column_name: str) -> set[str]:
    """Return foreign-key target tokens for one column.

    Args:
        table: SQLAlchemy table.
        column_name: Source column name.

    Returns:
        Target tokens in ``table.column`` form.
    """
    column = table.c[column_name]
    return {f"{fk.column.table.name}.{fk.column.name}" for fk in column.foreign_keys}


def _foreign_key_ondelete(table: Table, column_name: str) -> str:
    """Return the on-delete policy for one foreign key column.

    Args:
        table: SQLAlchemy table.
        column_name: Source column name.

    Returns:
        On-delete policy, or ``missing``.
    """
    column = table.c[column_name]
    for foreign_key in column.foreign_keys:
        return str(foreign_key.ondelete or "unspecified")
    return "missing"


def _script_contract() -> dict[str, Any]:
    """Return staging/import/verifier script contract status.

    Returns:
        Script contract summary.
    """
    staging_valid = all(
        hasattr(staging, attr)
        for attr in ("build_taxonomy_staging_rows", "build_summary", "ROW_TYPE_CATEGORY")
    )
    importer_repo = getattr(importer, "_SqlAlchemyTaxonomyImportRepository", None)
    importer_valid = hasattr(importer, "import_approved_taxonomy_manifest") and all(
        hasattr(importer_repo, attr)
        for attr in ("upsert_category", "upsert_product", "upsert_product_category")
    )
    verifier_repo = getattr(verifier, "_SqlAlchemyTaxonomyVerificationRepository", None)
    verifier_valid = hasattr(verifier, "verify_supplement_taxonomy_db_import") and all(
        hasattr(verifier_repo, attr)
        for attr in (
            "present_category_keys",
            "present_product_source_keys",
            "present_product_category_keys",
        )
    )
    return {
        "valid": staging_valid and importer_valid and verifier_valid,
        "staging_contract_present": staging_valid,
        "importer_contract_present": importer_valid,
        "verifier_contract_present": verifier_valid,
        "importer_dry_run_default_expected": True,
        "verifier_read_only_expected": True,
    }


def _migration_contract(*, repo_root: Path) -> dict[str, Any]:
    """Return taxonomy migration contract status.

    Args:
        repo_root: Lemon-Aid repository root.

    Returns:
        Migration contract summary.
    """
    migration = (
        repo_root
        / "backend"
        / "alembic"
        / "versions"
        / "0025_create_supplement_food_taxonomy_tables.py"
    )
    if not migration.is_file():
        return {
            "valid": False,
            "migration_file_present": False,
            "required_table_names_present": False,
            "catalog_rls_read_policy_present": False,
            "unsafe_raw_literals_absent": False,
        }
    source = migration.read_text(encoding="utf-8")
    required_table_names_present = all(table_name in source for table_name in SUPPLEMENT_TABLES)
    catalog_rls_read_policy_present = all(
        needle in source
        for needle in (
            "ENABLE ROW LEVEL SECURITY",
            "FORCE ROW LEVEL SECURITY",
            "GRANT SELECT",
        )
    )
    unsafe_raw_literals_absent = not any(
        needle in source for needle in ("raw_ocr_text", "provider_payload", "image_bytes")
    )
    valid = (
        required_table_names_present
        and catalog_rls_read_policy_present
        and unsafe_raw_literals_absent
    )
    return {
        "valid": valid,
        "migration_file_present": True,
        "migration_file_name": _safe_filename(migration.name),
        "required_table_names_present": required_table_names_present,
        "catalog_rls_read_policy_present": catalog_rls_read_policy_present,
        "unsafe_raw_literals_absent": unsafe_raw_literals_absent,
    }


def _test_contract(*, repo_root: Path) -> dict[str, Any]:
    """Return focused test coverage contract status.

    Args:
        repo_root: Lemon-Aid repository root.

    Returns:
        Test contract summary.
    """
    expected_files = (
        "backend/Nutrition-backend/tests/unit/db/test_models.py",
        "backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py",
        "backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_taxonomy_db_staging.py",
        "backend/Nutrition-backend/tests/unit/scripts/test_import_supplement_taxonomy_approved_manifest.py",
        "backend/Nutrition-backend/tests/unit/scripts/test_verify_supplement_taxonomy_db_import.py",
    )
    present = [path for path in expected_files if (repo_root / path).is_file()]
    missing = sorted(set(expected_files) - set(present))
    return {
        "valid": not missing,
        "expected_test_file_count": len(expected_files),
        "present_test_file_count": len(present),
        "missing_test_file_count": len(missing),
        "missing_test_files": [_safe_filename(Path(path).name) for path in missing],
    }


def _unsafe_storage_contract(
    *,
    table_map: Mapping[str, Table],
    migration_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Return unsafe column/storage contract status.

    Args:
        table_map: SQLAlchemy table mapping.
        migration_contract: Migration contract summary.

    Returns:
        Unsafe storage contract summary.
    """
    unsafe_columns_by_table: dict[str, list[str]] = {}
    for table_name, table in table_map.items():
        unsafe_columns = sorted(set(table.c.keys()).intersection(UNSAFE_STORAGE_COLUMN_NAMES))
        if unsafe_columns:
            unsafe_columns_by_table[table_name] = [_safe_token(name) for name in unsafe_columns]
    valid = (
        not unsafe_columns_by_table and migration_contract.get("unsafe_raw_literals_absent") is True
    )
    return {
        "valid": valid,
        "unsafe_table_column_count": sum(
            len(values) for values in unsafe_columns_by_table.values()
        ),
        "unsafe_columns_by_table": unsafe_columns_by_table,
        "raw_migration_literals_absent": migration_contract.get("unsafe_raw_literals_absent")
        is True,
    }


def _blocked_reasons(
    *,
    column_contracts: Mapping[str, Mapping[str, Any]],
    constraint_contracts: Mapping[str, Mapping[str, Any]],
    index_contracts: Mapping[str, Mapping[str, Any]],
    relationship_contract: Mapping[str, Any],
    script_contract: Mapping[str, Any],
    migration_contract: Mapping[str, Any],
    test_contract: Mapping[str, Any],
    unsafe_storage_contract: Mapping[str, Any],
) -> list[str]:
    """Return contract gap reason tokens.

    Args:
        column_contracts: Column summaries.
        constraint_contracts: Constraint summaries.
        index_contracts: Index summaries.
        relationship_contract: Relationship summary.
        script_contract: Script summary.
        migration_contract: Migration summary.
        test_contract: Test summary.
        unsafe_storage_contract: Unsafe storage summary.

    Returns:
        Reason tokens.
    """
    reasons: list[str] = []
    if any(
        row.get("all_required_columns_present") is not True for row in column_contracts.values()
    ):
        reasons.append("missing_required_model_columns")
    if any(
        row.get("all_required_constraints_present") is not True
        for row in constraint_contracts.values()
    ):
        reasons.append("missing_required_unique_constraints")
    if any(row.get("all_required_indexes_present") is not True for row in index_contracts.values()):
        reasons.append("missing_required_indexes")
    if relationship_contract.get("valid") is not True:
        reasons.append("invalid_product_category_relationship")
    if script_contract.get("valid") is not True:
        reasons.append("missing_staging_import_or_verify_script_contract")
    if migration_contract.get("valid") is not True:
        reasons.append("missing_or_unsafe_taxonomy_migration")
    if test_contract.get("valid") is not True:
        reasons.append("missing_focused_taxonomy_tests")
    if unsafe_storage_contract.get("valid") is not True:
        reasons.append("unsafe_taxonomy_storage_contract")
    return [_safe_token(reason) for reason in reasons]


def _mapping(value: Any) -> Mapping[str, Any]:
    """Return a mapping or fail closed.

    Args:
        value: Candidate value.

    Returns:
        Mapping value.
    """
    if not isinstance(value, Mapping):
        raise TaxonomyPersistenceAuditError("Expected a mapping.")
    return value


def _safe_token(value: str) -> str:
    """Return a conservative token for reports.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789가-힣_:-.")
    if not value or any(char not in allowed for char in value):
        raise TaxonomyPersistenceAuditError("Unsafe token.")
    return value


def _safe_filename(value: str) -> str:
    """Return a conservative filename for reports.

    Args:
        value: Candidate filename.

    Returns:
        Safe filename.
    """
    token = _safe_token(value)
    if "/" in token or "\\" in token:
        raise TaxonomyPersistenceAuditError("Unsafe filename.")
    return token


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate integer.

    Returns:
        Non-negative integer.
    """
    if not isinstance(value, int) or value < 0:
        raise TaxonomyPersistenceAuditError("Expected a non-negative integer.")
    return value


def _bool_text(value: object) -> str:
    """Return lowercase boolean text.

    Args:
        value: Candidate boolean.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value is True else "false"


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
        raise TaxonomyPersistenceAuditError("Expected a token sequence.")
    if not value:
        return "- none"
    return "\n".join(f"- `{_safe_token(str(item))}`" for item in value)


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw OCR/provider payloads and local path literals.

    Args:
        value: Candidate JSON-like payload.

    Raises:
        TaxonomyPersistenceAuditError: If unsafe content is present.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_PATH_MARKERS:
        if marker in serialized:
            raise TaxonomyPersistenceAuditError("Audit payload contains a local path literal.")
    _reject_raw_keys(value)


def _reject_raw_keys(value: Any) -> None:
    """Recursively reject raw or sensitive keys.

    Args:
        value: Candidate JSON-like value.
    """
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in RAW_FORBIDDEN_KEYS:
                raise TaxonomyPersistenceAuditError("Audit payload contains a raw key.")
            _reject_raw_keys(child)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for child in value:
            _reject_raw_keys(child)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI-safe summary.

    Args:
        summary: Full audit summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": summary["status"],
        "reviewed_import_dry_run_allowed": summary["reviewed_import_dry_run_allowed"],
        "db_import_apply_allowed_now": False,
        "blocked_reason_count": len(summary["blocked_reasons"]),
        "model_table_count": len(summary["model_tables"]),
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
        "reviewed_import_dry_run_allowed": False,
        "db_import_apply_allowed_now": False,
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
