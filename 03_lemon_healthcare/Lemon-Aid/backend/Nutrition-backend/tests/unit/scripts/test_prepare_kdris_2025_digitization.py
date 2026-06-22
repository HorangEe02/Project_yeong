"""Tests for KDRIs 2025 digitization artifact preparation."""

from __future__ import annotations

import csv
import hashlib
import unicodedata
from pathlib import Path

import pytest

from scripts import prepare_kdris_2025_digitization as prepare


def _sha256(text: str) -> str:
    """Return a SHA-256 digest for test text.

    Args:
        text: Text payload.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(text.encode()).hexdigest()


def test_target_nutrient_inventory_tracks_official_41_count() -> None:
    """Verify the review inventory starts from the official 41 target nutrients."""
    codes = {nutrient.target_nutrient_code for nutrient in prepare.TARGET_NUTRIENTS}

    assert len(prepare.TARGET_NUTRIENTS) == 41
    assert "choline_mg" in codes
    assert "fluoride_mg" in codes
    assert "amino_acids_g" in codes


def test_write_target_nutrient_inventory_adds_review_fields(tmp_path: Path) -> None:
    """Verify inventory rows include reviewer and errata fields."""
    inventory_path = tmp_path / "inventory.csv"

    prepare.write_target_nutrient_inventory(inventory_path)

    with inventory_path.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert len(rows) == 41
    assert rows[0]["review_status"] == "needs_review"
    assert rows[0]["reviewer_1"] == "source_check_1"
    assert rows[0]["reviewer_2"] == "source_check_2"
    assert rows[0]["errata_version"] == "2026-03-16"


def test_write_candidate_rows_adds_needs_review_skeletons(tmp_path: Path) -> None:
    """Verify candidate rows preserve provenance without inventing values."""
    candidate_path = tmp_path / "candidate_rows.csv"

    prepare.write_candidate_rows(candidate_path)

    with candidate_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    assert tuple(reader.fieldnames or ()) == prepare.CANDIDATE_ROW_FIELDNAMES
    assert len(rows) == 41
    assert {row["review_status"] for row in rows} == {"needs_review"}
    assert {row["reference_type"] for row in rows} == {"TBD"}
    assert {row["reviewer_1"] for row in rows} == {"source_check_1"}
    assert {row["reviewer_2"] for row in rows} == {"source_check_2"}
    assert all(row["source_artifact"] for row in rows)
    assert all(row["source_page"] for row in rows)
    assert all(row["source_table"] for row in rows)
    assert all(row["source_cell"] for row in rows)
    assert all(row["reviewed_at"] == "" for row in rows)


def test_write_candidate_issues_tracks_schema_decisions(tmp_path: Path) -> None:
    """Verify known schema decisions are captured as blocking issues."""
    issues_path = tmp_path / "candidate_issues.csv"

    prepare.write_candidate_issues(issues_path)

    with issues_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    issue_codes = {row["nutrient_code"] for row in rows}

    assert tuple(reader.fieldnames or ()) == prepare.ISSUE_FIELDNAMES
    assert {
        "amino_acids_g",
        "copper_ug",
        "folate_ug",
        "water_ml",
        "total_sugars_percent_energy",
        "cholesterol_mg",
    }.issubset(issue_codes)
    assert {row["issue_type"] for row in rows} == {"schema_decision_resolved"}


def test_verify_raw_artifacts_rejects_checksum_mismatch(tmp_path: Path) -> None:
    """Verify raw artifact verification fails before review artifacts are created."""
    artifact_path = tmp_path / "source.pdf"
    artifact_path.write_text("official", encoding="utf-8")
    artifact = prepare.SourceArtifact(
        id="source",
        relative_path="source.pdf",
        source_url="https://example.test/source",
        checksum_sha256=_sha256("different"),
        artifact_type="test_source",
    )

    with pytest.raises(ValueError, match="checksum mismatch"):
        prepare.verify_raw_artifacts(tmp_path, (artifact,))


def test_verify_raw_artifacts_records_project_relative_path(tmp_path: Path) -> None:
    """Verify valid raw artifact records keep review metadata."""
    artifact_path = tmp_path / "source.pdf"
    artifact_path.write_text("official", encoding="utf-8")
    artifact = prepare.SourceArtifact(
        id="source",
        relative_path="source.pdf",
        source_url="https://example.test/source",
        checksum_sha256=_sha256("official"),
        artifact_type="test_source",
    )

    records = prepare.verify_raw_artifacts(tmp_path, (artifact,))

    assert records[0]["id"] == "source"
    assert records[0]["checksum_sha256"] == _sha256("official")
    assert records[0]["retrieved_at"] == "2026-05-14"


def test_find_extracted_pdf_matches_normalized_korean_filename(tmp_path: Path) -> None:
    """Verify decomposed Korean filenames from macOS ZIP extraction still match."""
    decomposed_name = unicodedata.normalize("NFD", prepare.SUMMARY_ARTIFACT_NAME)
    pdf_path = tmp_path / decomposed_name
    pdf_path.write_text("pdf placeholder", encoding="utf-8")

    found = prepare.find_extracted_pdf(tmp_path, prepare.SUMMARY_ARTIFACT_NAME)

    assert found == pdf_path
