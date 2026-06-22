"""Tests for the taxo59 food DB verifier."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_food_taxo59_db_import as verifier


def test_food_taxo59_status_requires_catalog_and_typed_table() -> None:
    """Verify catalog-only and full verification statuses are distinct."""
    assert verifier._status(catalog_verified=True, typed_verified=True) == "verified"
    assert (
        verifier._status(catalog_verified=True, typed_verified=False)
        == "catalog_verified_typed_table_missing"
    )
    assert verifier._status(catalog_verified=False, typed_verified=True) == "not_verified"


def test_food_taxo59_summary_rejects_local_paths(tmp_path: Path) -> None:
    """Verify the verifier fails closed before writing unsafe local paths."""
    summary_path = tmp_path / "summary.json"

    with pytest.raises(ValueError, match="unsafe local path"):
        verifier._write_summary(summary_path, {"unsafe": "/Users/example/raw.jpg"})


def test_food_taxo59_failure_summary_is_redacted() -> None:
    """Verify failure summaries never include DB URLs or raw provider payloads."""
    summary = verifier._failure_summary(RuntimeError("database_url_missing"))

    assert summary["status"] == "error"
    assert summary["database_url_printed"] is False
    assert summary["db_write_performed"] is False
    serialized = json.dumps(summary)
    assert "postgresql://" not in serialized
    assert "postgresql+asyncpg://" not in serialized
