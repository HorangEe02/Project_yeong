"""Validate project-owned KDRIs CSV datasets before production use."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
KDRIS_REFERENCE_ROOT = REPO_ROOT / "data" / "nutrition_reference" / "kdris"
DEFAULT_DATASET = KDRIS_REFERENCE_ROOT / "kdris_2025.csv"
DEFAULT_MANIFEST = KDRIS_REFERENCE_ROOT / "kdris_source_manifest.json"
CURRENT_ERRATA_VERSION = "2026-03-16"

REQUIRED_COLUMNS = (
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
ALLOWED_SEX_VALUES = {"all", "female", "male"}
ALLOWED_PREGNANCY_STATUSES = {"none", "pregnant", "lactating"}
ALLOWED_REVIEW_STATUSES = {"draft", "needs_review", "approved", "rejected"}
FORBIDDEN_SOURCE_TOKENS = ("sample_fixture", "not_verified")


class DatasetArtifact(TypedDict, total=False):
    """Dataset artifact entry loaded from the source manifest."""

    path: str
    checksum_sha256: str | None
    status: str


class ValidationResult(TypedDict):
    """KDRIs dataset validation result."""

    row_count: int
    errors: list[str]


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest for a file.

    Args:
        path: File to hash.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_manifest(path: Path) -> dict[str, object]:
    """Load a KDRIs source manifest JSON object.

    Args:
        path: Manifest JSON path.

    Returns:
        Parsed manifest.

    Raises:
        ValueError: If the manifest is not a JSON object.
    """
    with path.open(encoding="utf-8") as manifest_file:
        loaded: object = json.load(manifest_file)
    if not isinstance(loaded, dict):
        raise ValueError("KDRIs source manifest must be a JSON object.")
    return loaded


def _dataset_artifacts(manifest: dict[str, object]) -> list[DatasetArtifact]:
    """Return dataset artifact entries from a manifest.

    Args:
        manifest: Parsed manifest JSON object.

    Returns:
        Dataset artifact entries. Empty when manifest does not define them.
    """
    artifacts = manifest.get("dataset_artifacts", [])
    if not isinstance(artifacts, list):
        return []
    return [
        cast(DatasetArtifact, artifact)
        for artifact in artifacts
        if isinstance(artifact, dict) and isinstance(artifact.get("path"), str)
    ]


def _manifest_checksum_for(dataset_path: Path, manifest: dict[str, object]) -> str | None:
    """Find the manifest checksum recorded for a dataset path.

    Args:
        dataset_path: Dataset path being validated.
        manifest: Parsed manifest JSON object.

    Returns:
        Recorded checksum or None.
    """
    try:
        relative_path = dataset_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        relative_path = dataset_path.as_posix()

    for artifact in _dataset_artifacts(manifest):
        if artifact.get("path") == relative_path:
            return artifact.get("checksum_sha256")
    return None


def _has_forbidden_source_token(row: dict[str, str]) -> bool:
    """Check whether a row still points to sample fixture provenance.

    Args:
        row: CSV row.

    Returns:
        True if a forbidden token is present in source-related fields.
    """
    source_text = " ".join(
        row.get(field, "")
        for field in (
            "source_id",
            "source_artifact",
            "source_page",
            "source_table",
            "source_cell",
        )
    )
    return any(token in source_text for token in FORBIDDEN_SOURCE_TOKENS)


def _parse_optional_float(value: str) -> float | None:
    """Parse an optional numeric CSV value.

    Args:
        value: CSV cell value.

    Returns:
        Parsed float, or None for an empty value.

    Raises:
        ValueError: If the value is present but not numeric.
    """
    if value == "":
        return None
    return float(value)


def _validate_header(fieldnames: Sequence[str] | None) -> list[str]:
    """Validate that a CSV header contains the required KDRIs columns.

    Args:
        fieldnames: CSV field names reported by DictReader.

    Returns:
        Header validation errors.
    """
    if fieldnames is None:
        return ["dataset CSV is missing a header row."]
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        return [f"dataset CSV is missing required columns: {', '.join(missing)}"]
    return []


def _validate_required_text_fields(row: dict[str, str], row_number: int) -> list[str]:
    """Validate required non-empty text fields in one row.

    Args:
        row: CSV row.
        row_number: One-based source row number including header.

    Returns:
        Validation errors for missing text fields.
    """
    required_text_fields = (
        "nutrient_code",
        "nutrient_name_ko",
        "nutrient_name_en",
        "nutrient_group",
        "sex",
        "age_min_months",
        "age_max_months",
        "pregnancy_status",
        "reference_type",
        "reference_unit",
        "source_id",
        "source_artifact",
        "source_page",
        "source_table",
        "source_cell",
        "errata_version",
        "review_status",
    )
    return [
        f"row {row_number}: {field} is required."
        for field in required_text_fields
        if row.get(field, "") == ""
    ]


def _validate_category_fields(
    row: dict[str, str],
    row_number: int,
    require_approved: bool,
) -> list[str]:
    """Validate enumerated row fields.

    Args:
        row: CSV row.
        row_number: One-based source row number including header.
        require_approved: Whether all rows must be production-approved.

    Returns:
        Category validation errors.
    """
    errors: list[str] = []
    review_status = row.get("review_status")
    if row.get("sex") not in ALLOWED_SEX_VALUES:
        errors.append(f"row {row_number}: sex must be one of {sorted(ALLOWED_SEX_VALUES)}.")
    if row.get("pregnancy_status") not in ALLOWED_PREGNANCY_STATUSES:
        errors.append(
            f"row {row_number}: pregnancy_status must be one of "
            f"{sorted(ALLOWED_PREGNANCY_STATUSES)}."
        )
    if review_status not in ALLOWED_REVIEW_STATUSES:
        errors.append(
            f"row {row_number}: review_status must be one of {sorted(ALLOWED_REVIEW_STATUSES)}."
        )
    if require_approved and review_status != "approved":
        errors.append(f"row {row_number}: review_status must be approved for production.")
    return errors


def _validate_age_fields(row: dict[str, str], row_number: int) -> list[str]:
    """Validate age range fields in one row.

    Args:
        row: CSV row.
        row_number: One-based source row number including header.

    Returns:
        Age validation errors.
    """
    try:
        age_min = int(row.get("age_min_months", ""))
        age_max = int(row.get("age_max_months", ""))
    except ValueError:
        return [f"row {row_number}: age_min_months and age_max_months must be integers."]
    if age_min < 0 or age_max < age_min:
        return [f"row {row_number}: age range is invalid."]
    return []


def _validate_reference_amount_fields(row: dict[str, str], row_number: int) -> list[str]:
    """Validate scalar or range reference amount fields.

    Args:
        row: CSV row.
        row_number: One-based source row number including header.

    Returns:
        Reference amount validation errors.
    """
    try:
        reference_amount = _parse_optional_float(row.get("reference_amount", ""))
        reference_min = _parse_optional_float(row.get("reference_amount_min", ""))
        reference_max = _parse_optional_float(row.get("reference_amount_max", ""))
    except ValueError:
        return [f"row {row_number}: reference amounts must be numeric when present."]

    errors: list[str] = []
    if reference_amount is None and (reference_min is None or reference_max is None):
        errors.append(
            f"row {row_number}: reference_amount or reference_amount_min/max is required."
        )
    if reference_min is not None and reference_max is not None and reference_min > reference_max:
        errors.append(f"row {row_number}: reference_amount_min exceeds reference_amount_max.")
    return errors


def _validate_ul_fields(row: dict[str, str], row_number: int) -> list[str]:
    """Validate upper-limit amount fields.

    Args:
        row: CSV row.
        row_number: One-based source row number including header.

    Returns:
        UL validation errors.
    """
    errors: list[str] = []
    try:
        _parse_optional_float(row.get("ul_amount", ""))
        _parse_optional_float(row.get("ul_amount_secondary", ""))
    except ValueError:
        errors.append(f"row {row_number}: UL amounts must be numeric when present.")
    if row.get("ul_amount", "") != "" and row.get("ul_unit", "") == "":
        errors.append(f"row {row_number}: ul_unit is required when ul_amount is present.")
    if row.get("ul_amount_secondary", "") != "" and row.get("ul_unit_secondary", "") == "":
        errors.append(
            f"row {row_number}: ul_unit_secondary is required when ul_amount_secondary is present."
        )
    if row.get("ul_unit_secondary", "") != "" and row.get("ul_amount_secondary", "") == "":
        errors.append(
            f"row {row_number}: ul_amount_secondary is required when ul_unit_secondary is present."
        )
    return errors


def _validate_source_and_review_fields(row: dict[str, str], row_number: int) -> list[str]:
    """Validate source provenance and review fields.

    Args:
        row: CSV row.
        row_number: One-based source row number including header.

    Returns:
        Source and review validation errors.
    """
    errors: list[str] = []
    if row.get("errata_version") != CURRENT_ERRATA_VERSION:
        errors.append(f"row {row_number}: errata_version must match {CURRENT_ERRATA_VERSION}.")
    if _has_forbidden_source_token(row):
        errors.append(f"row {row_number}: source fields still reference sample fixture data.")
    if row.get("review_status") == "approved":
        for field in ("reviewer_1", "reviewer_2", "reviewed_at"):
            if row.get(field, "") == "":
                errors.append(f"row {row_number}: {field} is required for approved rows.")
    return errors


def _validate_row(
    row: dict[str, str],
    row_number: int,
    require_approved: bool,
) -> list[str]:
    """Validate one KDRIs CSV row.

    Args:
        row: CSV row.
        row_number: One-based source row number including header.
        require_approved: Whether all rows must be production-approved.

    Returns:
        Row validation errors.
    """
    errors: list[str] = []
    errors.extend(_validate_required_text_fields(row, row_number))
    errors.extend(_validate_category_fields(row, row_number, require_approved))
    errors.extend(_validate_age_fields(row, row_number))
    errors.extend(_validate_reference_amount_fields(row, row_number))
    errors.extend(_validate_ul_fields(row, row_number))
    errors.extend(_validate_source_and_review_fields(row, row_number))
    return errors


def _validate_age_overlaps(rows: list[dict[str, str]]) -> list[str]:
    """Validate that KDRIs rows do not define overlapping age ranges.

    Args:
        rows: Dataset rows.

    Returns:
        Age overlap validation errors.
    """
    errors: list[str] = []
    groups: dict[tuple[str, str, str, str, str, str], list[tuple[int, int, int]]] = {}
    for index, row in enumerate(rows, start=2):
        try:
            age_min = int(row["age_min_months"])
            age_max = int(row["age_max_months"])
        except ValueError:
            continue
        key = (
            row["nutrient_code"],
            row["sex"],
            row["pregnancy_status"],
            row.get("condition_detail", ""),
            row.get("source_variant", ""),
            row["reference_type"],
        )
        groups.setdefault(key, []).append((age_min, age_max, index))

    for key, ranges in groups.items():
        previous_max: int | None = None
        previous_row: int | None = None
        for age_min, age_max, row_number in sorted(ranges):
            if previous_max is not None and age_min <= previous_max:
                errors.append(f"row {row_number}: age range overlaps row {previous_row} for {key}.")
            previous_max = age_max
            previous_row = row_number
    return errors


def validate_dataset(
    dataset_path: Path,
    manifest_path: Path,
    require_approved: bool = False,
) -> ValidationResult:
    """Validate one KDRIs dataset CSV.

    Args:
        dataset_path: KDRIs CSV path.
        manifest_path: KDRIs source manifest path.
        require_approved: Require production-approved rows and a non-empty dataset.

    Returns:
        Validation result with row count and errors.
    """
    errors: list[str] = []
    manifest = _read_manifest(manifest_path)
    recorded_checksum = _manifest_checksum_for(dataset_path, manifest)
    if recorded_checksum is None:
        errors.append("dataset checksum is not recorded in the source manifest.")
    else:
        actual_checksum = _sha256(dataset_path)
        if recorded_checksum != actual_checksum:
            errors.append("dataset checksum does not match the source manifest.")

    with dataset_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        errors.extend(_validate_header(reader.fieldnames))
        rows = list(reader)

    for row_number, row in enumerate(rows, start=2):
        errors.extend(_validate_row(row, row_number, require_approved=require_approved))
    errors.extend(_validate_age_overlaps(rows))
    if require_approved and not rows:
        errors.append("production KDRIs dataset must contain approved rows.")

    return {"row_count": len(rows), "errors": errors}


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(description="Validate a project-owned KDRIs CSV dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--require-approved",
        action="store_true",
        help="Require approved rows and production-ready source provenance.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the KDRIs dataset validator.

    Args:
        argv: Optional CLI arguments.

    Returns:
        Process exit code. Zero means validation passed.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = validate_dataset(
        dataset_path=args.dataset,
        manifest_path=args.manifest,
        require_approved=args.require_approved,
    )
    if result["errors"]:
        for error in result["errors"]:
            print(f"ERROR: {error}")
        return 1
    print(f"Validated {result['row_count']} KDRIs rows from {args.dataset}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
