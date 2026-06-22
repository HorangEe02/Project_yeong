"""Validate review-stage KDRIs 2025 candidate row artifacts."""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.prepare_kdris_2025_digitization import (  # noqa: E402
    CANDIDATE_ROW_FIELDNAMES,
    CURRENT_ERRATA_VERSION,
    ISSUE_FIELDNAMES,
    REVIEWER_1,
    REVIEWER_2,
    SCHEMA_DECISION_ISSUES,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATE_ROWS = (
    PROJECT_ROOT / "data" / "kdris" / "review" / "2025" / "kdris_2025_candidate_rows.csv"
)
DEFAULT_CANDIDATE_ISSUES = (
    PROJECT_ROOT / "data" / "kdris" / "review" / "2025" / "kdris_2025_candidate_issues.csv"
)

ALLOWED_CANDIDATE_STATUSES = {"draft", "needs_review"}
ALLOWED_REFERENCE_TYPES = {
    "TBD",
    "EER",
    "EAR",
    "RNI",
    "AI",
    "AMDR",
    "CDRR",
    "UL",
    "policy_limit",
}
FORBIDDEN_SOURCE_TOKENS = ("sample_fixture", "not_verified")
EXPECTED_SCHEMA_DECISION_NUTRIENTS = {issue.nutrient_code for issue in SCHEMA_DECISION_ISSUES}
ALLOWED_SCHEMA_DECISION_ISSUE_TYPES = {
    "schema_decision_required",
    "schema_decision_resolved",
}


class CandidateValidationResult(TypedDict):
    """KDRIs candidate artifact validation result."""

    row_count: int
    issue_count: int
    schema_decision_count: int
    errors: list[str]


def _read_csv_rows(
    path: Path,
    expected_fieldnames: Sequence[str],
    artifact_label: str,
) -> tuple[list[dict[str, str]], list[str]]:
    """Read a CSV artifact and validate its exact header.

    Args:
        path: CSV artifact path.
        expected_fieldnames: Required field order.
        artifact_label: Human-readable artifact label for error messages.

    Returns:
        Tuple of parsed rows and validation errors.
    """
    errors: list[str] = []
    if not path.exists():
        return [], [f"{artifact_label} does not exist: {path}"]

    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames != tuple(expected_fieldnames):
            errors.append(
                f"{artifact_label} header must match expected schema: "
                f"{', '.join(expected_fieldnames)}"
            )
        rows = list(reader)
    return rows, errors


def _source_fields_text(row: dict[str, str]) -> str:
    """Join source provenance fields for forbidden-token checks.

    Args:
        row: Candidate CSV row.

    Returns:
        Combined source field text.
    """
    return " ".join(
        row.get(field, "")
        for field in (
            "source_id",
            "source_artifact",
            "source_page",
            "source_table",
            "source_cell",
        )
    )


def _validate_optional_float(
    row: dict[str, str],
    field: str,
    row_number: int,
) -> list[str]:
    """Validate that a candidate numeric cell is blank or parseable.

    Args:
        row: Candidate CSV row.
        field: Numeric field name.
        row_number: One-based CSV row number including the header.

    Returns:
        Numeric validation errors.
    """
    value = row.get(field, "")
    if value == "":
        return []
    try:
        float(value)
    except ValueError:
        return [f"row {row_number}: {field} must be numeric when present."]
    return []


def _validate_optional_int(
    row: dict[str, str],
    field: str,
    row_number: int,
) -> list[str]:
    """Validate that a candidate integer cell is blank or parseable.

    Args:
        row: Candidate CSV row.
        field: Integer field name.
        row_number: One-based CSV row number including the header.

    Returns:
        Integer validation errors.
    """
    value = row.get(field, "")
    if value == "":
        return []
    try:
        int(value)
    except ValueError:
        return [f"row {row_number}: {field} must be an integer when present."]
    return []


def _validate_candidate_required_fields(
    row: dict[str, str],
    row_number: int,
) -> list[str]:
    """Validate required text fields in one candidate row.

    Args:
        row: Candidate row.
        row_number: One-based CSV row number including the header.

    Returns:
        Required-field validation errors.
    """
    required_fields = (
        "nutrient_code",
        "nutrient_name_ko",
        "nutrient_name_en",
        "nutrient_group",
        "reference_type",
        "reference_unit",
        "source_id",
        "source_artifact",
        "source_page",
        "source_table",
        "source_cell",
        "errata_version",
        "review_status",
        "reviewer_1",
        "reviewer_2",
    )
    return [
        f"row {row_number}: {field} is required."
        for field in required_fields
        if row.get(field, "") == ""
    ]


def _validate_candidate_review_fields(
    row: dict[str, str],
    row_number: int,
) -> list[str]:
    """Validate review metadata for one candidate row.

    Args:
        row: Candidate row.
        row_number: One-based CSV row number including the header.

    Returns:
        Review-field validation errors.
    """
    errors: list[str] = []

    if row.get("review_status") == "approved":
        errors.append(f"row {row_number}: candidate rows must not be approved before promotion.")
    elif row.get("review_status") not in ALLOWED_CANDIDATE_STATUSES:
        errors.append(
            f"row {row_number}: review_status must be one of "
            f"{sorted(ALLOWED_CANDIDATE_STATUSES)}."
        )
    if row.get("reviewer_1") != REVIEWER_1:
        errors.append(f"row {row_number}: reviewer_1 must be {REVIEWER_1}.")
    if row.get("reviewer_2") != REVIEWER_2:
        errors.append(f"row {row_number}: reviewer_2 must be {REVIEWER_2}.")
    if row.get("reviewed_at", "") != "":
        errors.append(f"row {row_number}: reviewed_at must remain blank for candidates.")
    if row.get("errata_version") != CURRENT_ERRATA_VERSION:
        errors.append(f"row {row_number}: errata_version must match {CURRENT_ERRATA_VERSION}.")
    return errors


def _validate_candidate_reference_fields(
    row: dict[str, str],
    row_number: int,
) -> list[str]:
    """Validate reference and numeric fields for one candidate row.

    Args:
        row: Candidate row.
        row_number: One-based CSV row number including the header.

    Returns:
        Reference-field validation errors.
    """
    errors: list[str] = []
    if row.get("reference_type") not in ALLOWED_REFERENCE_TYPES:
        errors.append(
            f"row {row_number}: reference_type must be one of "
            f"{sorted(ALLOWED_REFERENCE_TYPES)}."
        )
    for field in (
        "reference_amount",
        "reference_amount_min",
        "reference_amount_max",
        "ul_amount",
        "ul_amount_secondary",
    ):
        errors.extend(_validate_optional_float(row, field, row_number))
    if row.get("ul_amount_secondary", "") != "" and row.get("ul_unit_secondary", "") == "":
        errors.append(f"row {row_number}: ul_unit_secondary is required when present.")
    for field in ("age_min_months", "age_max_months"):
        errors.extend(_validate_optional_int(row, field, row_number))
    return errors


def _validate_candidate_age_range(row: dict[str, str], row_number: int) -> list[str]:
    """Validate optional age range ordering for one candidate row.

    Args:
        row: Candidate row.
        row_number: One-based CSV row number including the header.

    Returns:
        Age range validation errors.
    """
    age_min_value = row.get("age_min_months", "")
    age_max_value = row.get("age_max_months", "")
    if age_min_value == "" or age_max_value == "":
        return []
    try:
        age_min = int(age_min_value)
        age_max = int(age_max_value)
    except ValueError:
        return []
    if age_min < 0 or age_max < age_min:
        return [f"row {row_number}: age range is invalid."]
    return []


def _validate_candidate_row(row: dict[str, str], row_number: int) -> list[str]:
    """Validate one review-stage candidate row.

    Args:
        row: Candidate row.
        row_number: One-based CSV row number including the header.

    Returns:
        Candidate row validation errors.
    """
    errors: list[str] = []
    errors.extend(_validate_candidate_required_fields(row, row_number))
    errors.extend(_validate_candidate_review_fields(row, row_number))
    errors.extend(_validate_candidate_reference_fields(row, row_number))
    errors.extend(_validate_candidate_age_range(row, row_number))
    if any(token in _source_fields_text(row) for token in FORBIDDEN_SOURCE_TOKENS):
        errors.append(f"row {row_number}: source fields contain forbidden fixture tokens.")
    return errors


def _validate_candidate_issue(row: dict[str, str], row_number: int) -> list[str]:
    """Validate one candidate blocking issue row.

    Args:
        row: Candidate issue row.
        row_number: One-based CSV row number including the header.

    Returns:
        Candidate issue validation errors.
    """
    required_fields = ISSUE_FIELDNAMES
    return [
        f"issue row {row_number}: {field} is required."
        for field in required_fields
        if row.get(field, "") == ""
    ]


def validate_candidate_artifacts(
    candidate_rows_path: Path,
    candidate_issues_path: Path,
) -> CandidateValidationResult:
    """Validate generated KDRIs 2025 candidate review artifacts.

    Args:
        candidate_rows_path: Candidate row skeleton CSV path.
        candidate_issues_path: Candidate issue CSV path.

    Returns:
        Validation result with row, issue, and error counts.
    """
    errors: list[str] = []
    candidate_rows, row_errors = _read_csv_rows(
        candidate_rows_path,
        CANDIDATE_ROW_FIELDNAMES,
        "candidate rows",
    )
    candidate_issues, issue_errors = _read_csv_rows(
        candidate_issues_path,
        ISSUE_FIELDNAMES,
        "candidate issues",
    )
    errors.extend(row_errors)
    errors.extend(issue_errors)

    for row_number, row in enumerate(candidate_rows, start=2):
        errors.extend(_validate_candidate_row(row, row_number))
    for row_number, row in enumerate(candidate_issues, start=2):
        errors.extend(_validate_candidate_issue(row, row_number))

    schema_decision_nutrients = {
        row.get("nutrient_code", "")
        for row in candidate_issues
        if row.get("issue_type") in ALLOWED_SCHEMA_DECISION_ISSUE_TYPES
    }
    missing_schema_decisions = sorted(
        EXPECTED_SCHEMA_DECISION_NUTRIENTS - schema_decision_nutrients
    )
    if missing_schema_decisions:
        errors.append(
            "candidate issues are missing schema decisions for: "
            f"{', '.join(missing_schema_decisions)}"
        )

    return {
        "row_count": len(candidate_rows),
        "issue_count": len(candidate_issues),
        "schema_decision_count": len(schema_decision_nutrients),
        "errors": errors,
    }


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Validate review-stage KDRIs 2025 candidate row artifacts."
    )
    parser.add_argument("--candidate-rows", type=Path, default=DEFAULT_CANDIDATE_ROWS)
    parser.add_argument("--candidate-issues", type=Path, default=DEFAULT_CANDIDATE_ISSUES)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the KDRIs 2025 candidate artifact validator.

    Args:
        argv: Optional CLI arguments.

    Returns:
        Process exit code. Zero means validation passed.
    """
    args = _build_parser().parse_args(argv)
    result = validate_candidate_artifacts(
        candidate_rows_path=args.candidate_rows,
        candidate_issues_path=args.candidate_issues,
    )
    if result["errors"]:
        for error in result["errors"]:
            print(f"ERROR: {error}")
        return 1
    print(
        "Validated "
        f"{result['row_count']} candidate rows and {result['issue_count']} candidate issues "
        f"from {args.candidate_rows}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
