"""KDRIs 2025 dataset transition tests."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from src.config import Settings
from src.nutrition.kdris import (
    DEFAULT_KDRIS_2025_CSV,
    get_kdris_dataset_context,
    load_kdris_references,
    resolve_kdris_data_path,
)

BACKEND_ROOT = Path(__file__).resolve().parents[4]
PROJECT_ROOT = BACKEND_ROOT.parent
VALIDATOR = BACKEND_ROOT / "scripts" / "validate_kdris_dataset.py"
REQUIRED_2025_COLUMNS = (
    "nutrient_code",
    "nutrient_name_ko",
    "nutrient_name_en",
    "nutrient_group",
    "sex",
    "age_min_months",
    "age_max_months",
    "pregnancy_status",
    "condition_detail",
    "source_variant",
    "reference_type",
    "reference_amount",
    "reference_amount_min",
    "reference_amount_max",
    "reference_unit",
    "ul_amount",
    "ul_unit",
    "ul_amount_secondary",
    "ul_unit_secondary",
    "source_id",
    "source_artifact",
    "source_page",
    "source_table",
    "source_cell",
    "errata_version",
    "review_status",
    "reviewer_1",
    "reviewer_2",
    "reviewed_at",
)


def test_2025_candidate_header_has_operational_columns() -> None:
    """Verify the 2025 candidate CSV exposes source and review columns."""
    with DEFAULT_KDRIS_2025_CSV.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames

    assert fieldnames is not None
    assert set(REQUIRED_2025_COLUMNS).issubset(set(fieldnames))


def test_2025_dataset_contains_only_approved_official_rows() -> None:
    """Verify the promoted 2025 KDRIs dataset contains approved official rows."""
    references = load_kdris_references(DEFAULT_KDRIS_2025_CSV)

    assert len(references) == 1795
    assert {reference.review_status for reference in references} == {"approved"}
    assert any(reference.source_variant == "total_water" for reference in references)
    assert any(reference.ul_amount_secondary is not None for reference in references)


def test_2025_settings_resolve_candidate_dataset_context() -> None:
    """Verify Settings can point runtime lookup at the 2025 candidate dataset."""
    settings = Settings(
        kdris_data_version="2025",
        kdris_data_path="data/nutrition_reference/kdris/kdris_2025.csv",
    )

    context = get_kdris_dataset_context(settings=settings)

    assert resolve_kdris_data_path("2025") == DEFAULT_KDRIS_2025_CSV
    assert context["dataset_status"] == "official_2025_approved"
    assert context["dataset_version"] == "2025"
    assert context["source_manifest_version"] == "2.0"


def test_load_2025_schema_supports_month_ranges_and_source_provenance(
    tmp_path: Path,
) -> None:
    """Verify the 2025 parser supports month ranges using synthetic non-official data."""
    csv_path = tmp_path / "kdris_2025_parser_test.csv"
    header = ",".join(REQUIRED_2025_COLUMNS)
    row = ",".join(
        (
            "parser_test_mg",
            "파서테스트",
            "Parser test",
            "parser_test_group",
            "all",
            "228",
            "779",
            "none",
            "",
            "test_variant",
            "RNI",
            "1.5",
            "",
            "",
            "mg",
            "3",
            "mg",
            "",
            "",
            "kns_2025_kdris_publication",
            "synthetic_parser_test_not_official_source.pdf",
            "p.1",
            "table parser-test",
            "row parser-test",
            "2026-03-16",
            "draft",
            "",
            "",
            "",
        )
    )
    csv_path.write_text(f"{header}\n{row}\n", encoding="utf-8")

    references = load_kdris_references(csv_path)

    assert len(references) == 1
    reference = references[0]
    assert reference.age_min_months == 228
    assert reference.age_max_months == 779
    assert reference.age_min == 19
    assert reference.age_max == 64
    assert reference.reference_type == "RNI"
    assert reference.source_variant == "test_variant"
    assert reference.source_id == "kns_2025_kdris_publication"
    assert reference.errata_version == "2026-03-16"


def test_kdris_validator_accepts_promoted_official_dataset() -> None:
    """Verify draft validation passes for the promoted official dataset."""
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "Validated 1795 KDRIs rows" in result.stdout


def test_kdris_validator_accepts_production_approved_rows() -> None:
    """Verify production validation passes after reviewed official rows exist."""
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--require-approved"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "Validated 1795 KDRIs rows" in result.stdout
