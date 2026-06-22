"""Tests for KDRIs 2025 candidate artifact validation."""

from __future__ import annotations

import csv
from pathlib import Path

from scripts import prepare_kdris_2025_digitization as prepare
from scripts import validate_kdris_candidate_rows as validate


def _write_rows(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, str]],
) -> None:
    """Write CSV rows for validator mutation tests.

    Args:
        path: Destination CSV path.
        fieldnames: CSV field order.
        rows: Rows to write.
    """
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _generated_artifacts(tmp_path: Path) -> tuple[Path, Path]:
    """Generate candidate row and issue artifacts in a temporary directory.

    Args:
        tmp_path: Pytest temporary path.

    Returns:
        Candidate rows path and candidate issues path.
    """
    candidate_rows_path = tmp_path / "candidate_rows.csv"
    candidate_issues_path = tmp_path / "candidate_issues.csv"
    prepare.write_candidate_rows(candidate_rows_path)
    prepare.write_candidate_issues(candidate_issues_path)
    return candidate_rows_path, candidate_issues_path


def test_validate_candidate_artifacts_accepts_generated_skeletons(tmp_path: Path) -> None:
    """Verify generated candidate artifacts pass review-stage validation."""
    candidate_rows_path, candidate_issues_path = _generated_artifacts(tmp_path)

    result = validate.validate_candidate_artifacts(
        candidate_rows_path=candidate_rows_path,
        candidate_issues_path=candidate_issues_path,
    )

    assert result["errors"] == []
    assert result["row_count"] == 41
    assert result["issue_count"] == len(prepare.SCHEMA_DECISION_ISSUES)
    assert result["schema_decision_count"] == len(prepare.SCHEMA_DECISION_ISSUES)


def test_validate_candidate_artifacts_rejects_approved_candidate(
    tmp_path: Path,
) -> None:
    """Verify candidate rows cannot be marked approved before promotion."""
    candidate_rows_path, candidate_issues_path = _generated_artifacts(tmp_path)
    with candidate_rows_path.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    rows[0]["review_status"] = "approved"
    _write_rows(candidate_rows_path, prepare.CANDIDATE_ROW_FIELDNAMES, rows)

    result = validate.validate_candidate_artifacts(
        candidate_rows_path=candidate_rows_path,
        candidate_issues_path=candidate_issues_path,
    )

    assert any("must not be approved" in error for error in result["errors"])


def test_validate_candidate_artifacts_requires_source_cell(tmp_path: Path) -> None:
    """Verify candidate rows must keep source cell provenance."""
    candidate_rows_path, candidate_issues_path = _generated_artifacts(tmp_path)
    with candidate_rows_path.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    rows[0]["source_cell"] = ""
    _write_rows(candidate_rows_path, prepare.CANDIDATE_ROW_FIELDNAMES, rows)

    result = validate.validate_candidate_artifacts(
        candidate_rows_path=candidate_rows_path,
        candidate_issues_path=candidate_issues_path,
    )

    assert any("source_cell is required" in error for error in result["errors"])
