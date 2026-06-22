"""Tests for supplement taxonomy persistence contract audit."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

audit = importlib.import_module("scripts.audit_supplement_taxonomy_persistence_contract")


def test_taxonomy_persistence_contract_is_ready_for_reviewed_import_dry_run() -> None:
    """Verify current ORM/script/migration contracts support reviewed import dry-run."""
    summary = audit.build_taxonomy_persistence_contract_audit(repo_root=BACKEND_ROOT.parent)

    assert summary["schema_version"] == "supplement-taxonomy-persistence-contract-audit-v1"
    assert summary["status"] == "ready_for_reviewed_import_dry_run"
    assert summary["reviewed_import_dry_run_allowed"] is True
    assert summary["db_import_apply_allowed_now"] is False
    assert summary["database_connection_opened"] is False
    assert summary["source_rows_read"] is False
    assert summary["source_image_read_performed"] is False
    assert summary["blocked_reasons"] == []
    assert summary["relationship_contract"]["valid"] is True
    assert summary["script_contract"]["valid"] is True
    assert summary["migration_contract"]["valid"] is True
    assert summary["test_contract"]["valid"] is True
    assert summary["unsafe_storage_contract"]["valid"] is True
    product_columns = summary["column_contracts"]["supplement_products"]
    assert product_columns["all_required_columns_present"] is True
    assert product_columns["missing_column_count"] == 0
    assert "source_doc_urls" in summary


def test_column_contract_detects_missing_required_columns() -> None:
    """Verify missing DB columns are reported as contract gaps."""
    table_map = {
        name: model.__table__
        for name, model in {
            "supplement_categories": audit.SupplementCategory,
            "supplement_products": audit.SupplementProduct,
            "supplement_product_categories": audit.SupplementProductCategory,
        }.items()
    }
    required = audit.REQUIRED_TABLE_COLUMNS["supplement_products"]
    original = audit.REQUIRED_TABLE_COLUMNS["supplement_products"]
    audit.REQUIRED_TABLE_COLUMNS["supplement_products"] = frozenset(
        {*required, "missing_contract_column"}
    )
    try:
        contracts = audit._column_contracts(table_map=table_map)
    finally:
        audit.REQUIRED_TABLE_COLUMNS["supplement_products"] = original

    assert contracts["supplement_products"]["all_required_columns_present"] is False
    assert contracts["supplement_products"]["missing_column_count"] == 1
    assert contracts["supplement_products"]["missing_columns"] == ["missing_contract_column"]


def test_taxonomy_persistence_contract_rejects_unsafe_payload() -> None:
    """Verify raw OCR/provider keys fail closed before report output."""
    with pytest.raises(audit.TaxonomyPersistenceAuditError, match="raw key"):
        audit._reject_unsafe_payload({"raw_ocr_text": "unsafe"})


def test_taxonomy_persistence_contract_cli_writes_json_and_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes redacted JSON and Markdown audit outputs."""
    output_path = tmp_path / "audit.json"
    markdown_path = tmp_path / "audit.md"

    audit.main(
        [
            "--repo-root",
            str(BACKEND_ROOT.parent),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert summary["status"] == "ready_for_reviewed_import_dry_run"
    assert "ready_for_reviewed_import_dry_run" in stdout
    assert "Supplement Taxonomy Persistence Contract Audit" in markdown
    assert str(tmp_path) not in stdout
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
