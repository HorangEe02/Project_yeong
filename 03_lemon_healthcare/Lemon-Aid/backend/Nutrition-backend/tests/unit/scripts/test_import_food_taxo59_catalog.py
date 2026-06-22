"""Tests for taxo59 food catalog import staging."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import import_food_taxo59_catalog as importer


def test_build_food_catalog_rows_maps_csv_to_existing_catalog_schema(tmp_path: Path) -> None:
    """Verify taxo59 CSV rows map into FoodCatalogItem-compatible payloads."""
    csv_path = _write_taxo59_csv(tmp_path, list(importer.TAXO59_CLASS_TAXONOMY))

    rows = importer.build_food_catalog_rows(csv_path=csv_path)

    assert len(rows) == 59
    by_class = {row["class_en"]: row for row in rows}
    assert by_class["doenjang-jjigae"]["cuisine_code"] == "korean"
    assert by_class["doenjang-jjigae"]["course_code"] == "soup_stew"
    assert by_class["hamburger"]["cuisine_code"] == "other"
    assert by_class["hamburger"]["course_code"] == "fast_food"
    assert by_class["western-cream-soup"]["course_code"] == "soup"
    nutrition = by_class["doenjang-jjigae"]["nutrition_reference"]
    assert nutrition["basis"] == "per_100g_class_average"
    assert nutrition["per_100g"]["kcal"] == 100.0
    assert nutrition["per_serving_estimate"]["kcal"] == 300.0
    assert by_class["doenjang-jjigae"]["source_payload"]["model_class"] == "doenjang-jjigae"


@pytest.mark.asyncio
async def test_food_taxo59_import_dry_run_writes_manifest_without_db_write(tmp_path: Path) -> None:
    """Verify dry-run writes a manifest and never opens the DB repository."""
    csv_path = _write_taxo59_csv(tmp_path, list(importer.TAXO59_CLASS_TAXONOMY))
    manifest_path = tmp_path / "food-taxo59-manifest.jsonl"

    summary = await importer.import_food_taxo59_catalog(
        csv_path=csv_path,
        manifest_path=manifest_path,
        apply_changes=False,
    )

    assert summary["csv_row_count"] == 59
    assert summary["mapped_food_catalog_item_count"] == 59
    assert summary["db_write_performed"] is False
    assert summary["source_table_sql_executed"] is False
    assert summary["standalone_food_nutrition_table_created"] is False
    manifest_rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(manifest_rows) == 59


@pytest.mark.asyncio
async def test_food_taxo59_import_apply_uses_repository_boundary(tmp_path: Path) -> None:
    """Verify apply mode upserts through a repository and commits once."""
    csv_path = _write_taxo59_csv(tmp_path, list(importer.TAXO59_CLASS_TAXONOMY))
    repository = _FakeFoodTaxo59Repository()

    summary = await importer.import_food_taxo59_catalog(
        csv_path=csv_path,
        apply_changes=True,
        repository=repository,
    )

    assert summary["db_write_performed"] is True
    assert summary["inserted_food_catalog_item_count"] == 59
    assert summary["updated_food_catalog_item_count"] == 0
    assert repository.committed is True
    assert repository.rolled_back is False
    assert len(repository.rows) == 59


def test_food_taxo59_import_rejects_unmapped_class(tmp_path: Path) -> None:
    """Verify class taxonomy drift fails closed instead of guessing a bucket."""
    csv_path = _write_taxo59_csv(tmp_path, [*importer.TAXO59_CLASS_TAXONOMY, "unknown-class"])

    with pytest.raises(ValueError, match="no cuisine/course mapping"):
        importer.build_food_catalog_rows(csv_path=csv_path)


class _FakeFoodTaxo59Repository:
    """Repository double for food taxo59 import tests."""

    def __init__(self) -> None:
        """Initialize repository state."""
        self.rows: list[dict[str, Any]] = []
        self.committed = False
        self.rolled_back = False

    async def upsert_catalog_item(self, row: dict[str, Any]) -> str:
        """Record one row and report an insert action."""
        self.rows.append(row)
        return "inserted"

    async def commit(self) -> None:
        """Record commit execution."""
        self.committed = True

    async def rollback(self) -> None:
        """Record rollback execution."""
        self.rolled_back = True


def _write_taxo59_csv(tmp_path: Path, class_names: list[str]) -> Path:
    """Write a minimal taxo59 CSV fixture.

    Args:
        tmp_path: Pytest temporary directory.
        class_names: Class ids to include.

    Returns:
        CSV fixture path.
    """
    path = tmp_path / "food_nutrition_taxo59.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=importer.REQUIRED_COLUMNS)
        writer.writeheader()
        for index, class_en in enumerate(class_names):
            writer.writerow(
                {
                    "class_en": class_en,
                    "class_ko": _fixture_ko_name(class_en, index),
                    "n_source_codes": "2",
                    "serving_g": "300",
                    "kcal_100g": "100",
                    "carb_g": "10",
                    "sugar_g": "",
                    "fat_g": "5",
                    "protein_g": "7",
                    "sodium_mg": "400",
                    "chol_mg": "",
                    "sat_fat_g": "1",
                    "trans_fat_g": "0",
                }
            )
    return path


def _fixture_ko_name(class_en: str, index: int) -> str:
    """Return deterministic Korean fixture names for relevant assertions."""
    if class_en == "doenjang-jjigae":
        return "된장찌개"
    if class_en == "hamburger":
        return "햄버거"
    if class_en == "western-cream-soup":
        return "양식수프"
    return f"음식{index}"
