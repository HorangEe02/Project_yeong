"""Digitize approved KDRIs 2025 summary-table rows from the official KNS PDF."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.prepare_kdris_2025_digitization import (  # noqa: E402
    CANDIDATE_ROW_FIELDNAMES,
    CURRENT_ERRATA_VERSION,
    DEFAULT_EXTRACTED_DIR,
    REVIEWER_1,
    REVIEWER_2,
    SUMMARY_ARTIFACT_NAME,
    SUMMARY_TABLE_ARTIFACT,
    TARGET_NUTRIENTS,
    find_extracted_pdf,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "kdris" / "kdris_2025.csv"
SOURCE_ID = "kns_2025_kdris_publication"
REVIEWED_AT = "2026-05-14"
ROW_Y_DEDUP_TOLERANCE = 2.0
CELL_Y_TOLERANCE = 2.4
AGE_RE = re.compile(r"^(0-5|6-11|1-2|3-5|6-8|9-11|12-14|15-18|19-29|30-49|50-64|65-74|75)$")
SOURCE_UNSPECIFIED_AGE_MIN_MONTHS = 0
SOURCE_UNSPECIFIED_AGE_MAX_MONTHS = 1439


class PdfWord(TypedDict):
    """Positioned word emitted by pdfplumber."""

    text: str
    x0: float
    x1: float
    top: float


@dataclass(frozen=True)
class DemoRow:
    """Age, sex, and condition context for one official table row.

    Args:
        label: Stable row label for source provenance.
        sex: Row sex scope.
        age_min_months: Inclusive lower age bound in months.
        age_max_months: Inclusive upper age bound in months.
        pregnancy_status: Row pregnancy/lactation scope.
        condition_detail: Optional condition subtype preserved from source notes.
    """

    label: str
    sex: str
    age_min_months: int
    age_max_months: int
    pregnancy_status: str
    condition_detail: str = ""


@dataclass(frozen=True)
class NutrientMeta:
    """Digitization metadata for one nutrient code.

    Args:
        nutrient_name_ko: Korean display name.
        nutrient_name_en: English display name.
        nutrient_group: Project nutrient group.
        reference_unit: Default source unit.
    """

    nutrient_name_ko: str
    nutrient_name_en: str
    nutrient_group: str
    reference_unit: str


@dataclass(frozen=True)
class NutrientSpec:
    """Coordinate mapping for one nutrient within a summary-table section.

    Args:
        code: Project nutrient code.
        unit: Reference unit for extracted values.
        columns: Mapping from reference type to x-coordinate center.
        ul_unit: Unit for the primary UL column.
        source_variant: Official table variant encoded without changing nutrient code.
        ul_unit_secondary: Unit for a secondary UL value in dual-UL cells.
    """

    code: str
    unit: str
    columns: Mapping[str, float]
    ul_unit: str | None = None
    source_variant: str = ""
    ul_unit_secondary: str | None = None


@dataclass(frozen=True)
class ManualRow:
    """Manually encoded narrative or split-cell source row.

    Args:
        code: Project nutrient code.
        demo: Row demographic condition.
        reference_type: Reference type convention.
        reference_amount: Scalar amount when applicable.
        reference_amount_min: Range lower bound when applicable.
        reference_amount_max: Range upper bound when applicable.
        reference_unit: Official unit.
        source_page: Source page locator.
        source_table: Source table locator.
        source_cell: Source cell locator and raw value.
        source_variant: Variant needed to distinguish official semantics.
    """

    code: str
    demo: DemoRow
    reference_type: str
    reference_amount: str = ""
    reference_amount_min: str = ""
    reference_amount_max: str = ""
    reference_unit: str = ""
    source_page: str = ""
    source_table: str = ""
    source_cell: str = ""
    source_variant: str = ""


NORMAL_DEMOS: tuple[DemoRow, ...] = (
    DemoRow("0-5mo", "all", 0, 5, "none"),
    DemoRow("6-11mo", "all", 6, 11, "none"),
    DemoRow("1-2y", "all", 12, 35, "none"),
    DemoRow("3-5y", "all", 36, 71, "none"),
    DemoRow("male_6-8y", "male", 72, 107, "none"),
    DemoRow("male_9-11y", "male", 108, 143, "none"),
    DemoRow("male_12-14y", "male", 144, 179, "none"),
    DemoRow("male_15-18y", "male", 180, 227, "none"),
    DemoRow("male_19-29y", "male", 228, 359, "none"),
    DemoRow("male_30-49y", "male", 360, 599, "none"),
    DemoRow("male_50-64y", "male", 600, 779, "none"),
    DemoRow("male_65-74y", "male", 780, 899, "none"),
    DemoRow("male_75plus", "male", 900, 1439, "none"),
    DemoRow("female_6-8y", "female", 72, 107, "none"),
    DemoRow("female_9-11y", "female", 108, 143, "none"),
    DemoRow("female_12-14y", "female", 144, 179, "none"),
    DemoRow("female_15-18y", "female", 180, 227, "none"),
    DemoRow("female_19-29y", "female", 228, 359, "none"),
    DemoRow("female_30-49y", "female", 360, 599, "none"),
    DemoRow("female_50-64y", "female", 600, 779, "none"),
    DemoRow("female_65-74y", "female", 780, 899, "none"),
    DemoRow("female_75plus", "female", 900, 1439, "none"),
)
PREGNANCY_ADDITIONAL = DemoRow(
    "pregnant",
    "female",
    SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
    SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
    "pregnant",
    "pregnancy_additional",
)
LACTATION_ADDITIONAL = DemoRow(
    "lactating",
    "female",
    SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
    SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
    "lactating",
    "lactation_additional",
)
PREGNANCY_TOTAL = DemoRow(
    "pregnant_total",
    "female",
    SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
    SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
    "pregnant",
    "pregnancy_total",
)
LACTATION_TOTAL = DemoRow(
    "lactating_total",
    "female",
    SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
    SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
    "lactating",
    "lactation_total",
)

AMINO_ACID_META: Mapping[str, NutrientMeta] = {
    "methionine_cysteine_g": NutrientMeta(
        "메티오닌+시스테인", "Methionine + cysteine", "amino_acid", "g"
    ),
    "leucine_g": NutrientMeta("류신", "Leucine", "amino_acid", "g"),
    "isoleucine_g": NutrientMeta("이소류신", "Isoleucine", "amino_acid", "g"),
    "valine_g": NutrientMeta("발린", "Valine", "amino_acid", "g"),
    "lysine_g": NutrientMeta("라이신", "Lysine", "amino_acid", "g"),
    "phenylalanine_tyrosine_g": NutrientMeta(
        "페닐알라닌+티로신", "Phenylalanine + tyrosine", "amino_acid", "g"
    ),
    "threonine_g": NutrientMeta("트레오닌", "Threonine", "amino_acid", "g"),
    "tryptophan_g": NutrientMeta("트립토판", "Tryptophan", "amino_acid", "g"),
    "histidine_g": NutrientMeta("히스티딘", "Histidine", "amino_acid", "g"),
}


def _load_pdfplumber() -> Any:
    """Load pdfplumber only for the digitization CLI.

    Returns:
        Imported pdfplumber module.

    Raises:
        RuntimeError: If pdfplumber is not installed in the active Python runtime.
    """
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "pdfplumber is required for KDRIs PDF digitization. "
            "Use a runtime that provides pdfplumber, such as /opt/anaconda3/bin/python."
        ) from exc
    return pdfplumber


def _target_meta() -> dict[str, NutrientMeta]:
    """Build nutrient metadata from the official 41-target inventory plus amino-acid splits.

    Returns:
        Nutrient metadata keyed by nutrient code.
    """
    metadata = {
        nutrient.target_nutrient_code: NutrientMeta(
            nutrient_name_ko=nutrient.nutrient_name_ko,
            nutrient_name_en=nutrient.nutrient_name_en,
            nutrient_group=nutrient.nutrient_group,
            reference_unit=nutrient.default_unit,
        )
        for nutrient in TARGET_NUTRIENTS
    }
    metadata.update(AMINO_ACID_META)
    return metadata


def _clean_text(text: str) -> str:
    """Normalize extracted PDF cell text.

    Args:
        text: Raw extracted text.

    Returns:
        Cleaned text.
    """
    return text.replace("\u200b", "").strip()


def _parse_amount(text: str) -> str | None:
    """Parse an optional numeric value from one extracted table cell.

    Args:
        text: Raw cell text.

    Returns:
        Normalized numeric string, or None for blank/non-scalar cells.
    """
    cleaned = _clean_text(text)
    if cleaned in {"", "-"} or "미만" in cleaned:
        return None
    cleaned = re.sub(r"(?<=\d)\d\)$", "", cleaned)
    cleaned = cleaned.replace(",", "")
    if "/" in cleaned:
        cleaned = cleaned.split("/", 1)[0]
    if cleaned.startswith("±"):
        return None
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    try:
        float(cleaned)
    except ValueError:
        return None
    return cleaned


def _parse_dual_amount(text: str) -> tuple[str | None, str | None]:
    """Parse primary and secondary amounts from a slash-separated source cell.

    Args:
        text: Raw cell text.

    Returns:
        Primary and secondary numeric strings.
    """
    cleaned = _clean_text(text)
    if "/" not in cleaned:
        return _parse_amount(cleaned), None
    first, second = cleaned.split("/", 1)
    return _parse_amount(first), _parse_amount(second)


def _amount_pair_from_range(text: str) -> tuple[str | None, str | None]:
    """Parse a low-high range cell.

    Args:
        text: Raw range cell.

    Returns:
        Low and high amount strings.
    """
    cleaned = _clean_text(text)
    if cleaned in {"", "-"} or "-" not in cleaned:
        return None, None
    low, high = cleaned.split("-", 1)
    return _parse_amount(low), _parse_amount(high)


def _words(page: Any) -> list[PdfWord]:
    """Extract positioned words from a PDF page.

    Args:
        page: pdfplumber page object.

    Returns:
        List of positioned word dictionaries.
    """
    return [
        PdfWord(
            text=str(word["text"]),
            x0=float(word["x0"]),
            x1=float(word["x1"]),
            top=float(word["top"]),
        )
        for word in page.extract_words(
            x_tolerance=1,
            y_tolerance=2,
            keep_blank_chars=False,
        )
    ]


def _row_ys(page: Any, y_min: float, y_max: float, x_min: float, x_max: float) -> list[float]:
    """Find y-coordinates for the standard 22 non-pregnancy age/sex rows.

    Args:
        page: pdfplumber page object.
        y_min: Upper y-bound for the table section.
        y_max: Lower y-bound for the table section.
        x_min: Left x-bound for age labels.
        x_max: Right x-bound for age labels.

    Returns:
        Stable row y-coordinates in source order.
    """
    y_values = [
        word["top"]
        for word in _words(page)
        if y_min <= word["top"] <= y_max
        and x_min <= word["x0"] <= x_max
        and AGE_RE.match(word["text"])
    ]
    unique_values: list[float] = []
    for y_value in sorted(y_values):
        if not unique_values or abs(y_value - unique_values[-1]) > ROW_Y_DEDUP_TOLERANCE:
            unique_values.append(y_value)
    return unique_values[: len(NORMAL_DEMOS)]


def _text_at(page: Any, y_value: float, center: float, width: float = 13) -> str:
    """Extract text near a source cell coordinate.

    Args:
        page: pdfplumber page object.
        y_value: Row y-coordinate.
        center: Column x-coordinate center.
        width: Half-width tolerance around the column center.

    Returns:
        Cleaned cell text.
    """
    values = []
    for word in _words(page):
        center_x = (word["x0"] + word["x1"]) / 2
        if abs(word["top"] - y_value) <= CELL_Y_TOLERANCE and abs(center_x - center) <= width:
            values.append(word)
    return _clean_text(
        " ".join(word["text"] for word in sorted(values, key=lambda item: item["x0"]))
    )


def _make_row(
    metadata: Mapping[str, NutrientMeta],
    code: str,
    demo: DemoRow,
    reference_type: str,
    reference_unit: str,
    source_page: str,
    source_table: str,
    source_cell: str,
    reference_amount: str = "",
    reference_amount_min: str = "",
    reference_amount_max: str = "",
    ul_amount: str = "",
    ul_unit: str = "",
    ul_amount_secondary: str = "",
    ul_unit_secondary: str = "",
    source_variant: str = "",
) -> dict[str, str]:
    """Build one approved production CSV row.

    Args:
        metadata: Nutrient metadata keyed by code.
        code: Nutrient code.
        demo: Demographic row scope.
        reference_type: Reference type.
        reference_unit: Unit for reference amounts.
        source_page: Source page locator.
        source_table: Source table locator.
        source_cell: Source cell locator.
        reference_amount: Scalar reference amount.
        reference_amount_min: Range lower bound.
        reference_amount_max: Range upper bound.
        ul_amount: Primary UL amount.
        ul_unit: Primary UL unit.
        ul_amount_secondary: Secondary UL amount.
        ul_unit_secondary: Secondary UL unit.
        source_variant: Source variant label.

    Returns:
        CSV row mapping.
    """
    nutrient = metadata[code]
    return {
        "nutrient_code": code,
        "nutrient_name_ko": nutrient.nutrient_name_ko,
        "nutrient_name_en": nutrient.nutrient_name_en,
        "nutrient_group": nutrient.nutrient_group,
        "sex": demo.sex,
        "age_min_months": str(demo.age_min_months),
        "age_max_months": str(demo.age_max_months),
        "pregnancy_status": demo.pregnancy_status,
        "condition_detail": demo.condition_detail,
        "source_variant": source_variant,
        "reference_type": reference_type,
        "reference_amount": reference_amount,
        "reference_amount_min": reference_amount_min,
        "reference_amount_max": reference_amount_max,
        "reference_unit": reference_unit,
        "ul_amount": ul_amount,
        "ul_unit": ul_unit if ul_amount else "",
        "ul_amount_secondary": ul_amount_secondary,
        "ul_unit_secondary": ul_unit_secondary if ul_amount_secondary else "",
        "source_id": SOURCE_ID,
        "source_artifact": SUMMARY_TABLE_ARTIFACT,
        "source_page": source_page,
        "source_table": source_table,
        "source_cell": source_cell,
        "errata_version": CURRENT_ERRATA_VERSION,
        "review_status": "approved",
        "reviewer_1": REVIEWER_1,
        "reviewer_2": REVIEWER_2,
        "reviewed_at": REVIEWED_AT,
    }


def _append_scalar_row(
    rows: list[dict[str, str]],
    metadata: Mapping[str, NutrientMeta],
    spec: NutrientSpec,
    demo: DemoRow,
    reference_type: str,
    raw_value: str,
    source_page: str,
    source_table: str,
    ul_raw: str = "",
) -> None:
    """Append one scalar row when the source cell contains a parseable amount.

    Args:
        rows: Mutable output rows.
        metadata: Nutrient metadata keyed by code.
        spec: Nutrient coordinate specification.
        demo: Demographic row scope.
        reference_type: Reference type.
        raw_value: Raw source cell text.
        source_page: Source page locator.
        source_table: Source table locator.
        ul_raw: Raw UL source cell text.
    """
    amount = _parse_amount(raw_value)
    if amount is None:
        return
    ul_amount, ul_amount_secondary = _parse_dual_amount(ul_raw) if ul_raw else (None, None)
    source_cell = f"row={demo.label};column={reference_type};raw={raw_value}"
    if ul_raw:
        source_cell = f"{source_cell};ul_raw={ul_raw}"
    rows.append(
        _make_row(
            metadata=metadata,
            code=spec.code,
            demo=demo,
            reference_type=reference_type,
            reference_amount=amount,
            reference_unit=spec.unit,
            ul_amount=ul_amount or "",
            ul_unit=spec.ul_unit or spec.unit,
            ul_amount_secondary=ul_amount_secondary or "",
            ul_unit_secondary=spec.ul_unit_secondary or "",
            source_page=source_page,
            source_table=source_table,
            source_cell=source_cell,
            source_variant=spec.source_variant,
        )
    )


def _process_section(
    rows: list[dict[str, str]],
    metadata: Mapping[str, NutrientMeta],
    page: Any,
    y_min: float,
    y_max: float,
    source_page: str,
    source_table: str,
    specs: Sequence[NutrientSpec],
    age_x: tuple[float, float],
    condition_rows: Sequence[tuple[float, DemoRow]] = (),
) -> None:
    """Digitize one coordinate-stable summary-table section.

    Args:
        rows: Mutable output rows.
        metadata: Nutrient metadata keyed by code.
        page: pdfplumber page object.
        y_min: Upper y-bound for non-pregnancy rows.
        y_max: Lower y-bound for non-pregnancy rows.
        source_page: Source page locator.
        source_table: Source table locator.
        specs: Nutrient column coordinate mappings.
        age_x: X-coordinate bounds for age labels.
        condition_rows: Optional condition row coordinates.
    """
    row_contexts = list(zip(_row_ys(page, y_min, y_max, *age_x), NORMAL_DEMOS, strict=False))
    row_contexts.extend((y_value, demo) for y_value, demo in condition_rows)
    for y_value, demo in row_contexts:
        for spec in specs:
            ul_raw = ""
            if "UL" in spec.columns:
                ul_raw = _text_at(page, y_value, spec.columns["UL"])
            for reference_type in ("EER", "EAR", "RNI", "AI", "CDRR"):
                center = spec.columns.get(reference_type)
                if center is None:
                    continue
                _append_scalar_row(
                    rows=rows,
                    metadata=metadata,
                    spec=spec,
                    demo=demo,
                    reference_type=reference_type,
                    raw_value=_text_at(page, y_value, center),
                    source_page=source_page,
                    source_table=source_table,
                    ul_raw=ul_raw,
                )


def _process_amdr(
    rows: list[dict[str, str]], metadata: Mapping[str, NutrientMeta], page: Any
) -> None:
    """Digitize AMDR percent-energy rows.

    Args:
        rows: Mutable output rows.
        metadata: Nutrient metadata keyed by code.
        page: pdfplumber page object.
    """
    source_page = "PDF p.11 / printed p.xi"
    source_table = "2025 한국인 영양소 섭취기준 - 에너지적정비율"
    specs = (
        ("carbohydrate_g", 211.0),
        ("protein_g", 272.0),
        ("fat_g", 328.0),
    )
    for y_value, demo in zip(_row_ys(page, 190, 470, 130, 170), NORMAL_DEMOS, strict=False):
        for code, center in specs:
            raw = _text_at(page, y_value, center, 20)
            amount_min, amount_max = _amount_pair_from_range(raw)
            if amount_min is None or amount_max is None:
                continue
            rows.append(
                _make_row(
                    metadata=metadata,
                    code=code,
                    demo=demo,
                    reference_type="AMDR",
                    reference_amount_min=amount_min,
                    reference_amount_max=amount_max,
                    reference_unit="% energy",
                    source_page=source_page,
                    source_table=source_table,
                    source_cell=f"row={demo.label};column=AMDR;raw={raw}",
                    source_variant="amdr_percent_energy",
                )
            )


def _manual_rows(metadata: Mapping[str, NutrientMeta]) -> list[dict[str, str]]:
    """Build narrative and split-cell rows that are not reliable as single coordinates.

    Args:
        metadata: Nutrient metadata keyed by code.

    Returns:
        Approved manual rows with explicit source locators.
    """
    source_table_amdr = "2025 한국인 영양소 섭취기준 - 에너지적정비율"
    source_table_sugars = "2025 한국인 영양소 섭취기준 - 당류"
    source_table_macro = "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소"
    adult_demo = DemoRow("all_19plus", "all", 228, 1439, "none")
    all_demo = DemoRow("all_0plus", "all", 0, 1439, "none")
    pregnant_amdr = DemoRow(
        "pregnant_amdr",
        "female",
        SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
        SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
        "pregnant",
        "pregnancy_amdr",
    )
    lactating_amdr = DemoRow(
        "lactating_amdr",
        "female",
        SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
        SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
        "lactating",
        "lactation_amdr",
    )
    manual_specs = [
        ManualRow(
            code="total_sugars_percent_energy",
            demo=all_demo,
            reference_type="policy_limit",
            reference_amount_min="0",
            reference_amount_max="20",
            reference_unit="% energy",
            source_page="PDF p.11 / printed p.xi",
            source_table=source_table_sugars,
            source_cell="narrative_total_sugars_limit=20_percent_energy_or_less",
            source_variant="narrative_limit",
        ),
        ManualRow(
            code="cholesterol_mg",
            demo=adult_demo,
            reference_type="policy_limit",
            reference_amount_min="0",
            reference_amount_max="300",
            reference_unit="mg",
            source_page="PDF p.11 / printed p.xi",
            source_table=source_table_amdr,
            source_cell="footnote_1=age_19plus_less_than_300_mg_per_day",
            source_variant="adult_narrative_limit",
        ),
        ManualRow(
            code="epa_dha_mg",
            demo=PREGNANCY_TOTAL,
            reference_type="AI",
            reference_amount="300",
            reference_unit="mg",
            source_page="PDF p.12 / printed p.xii",
            source_table=source_table_macro,
            source_cell="row=pregnant_total;column=AI;raw=300(200_DHA)",
            source_variant="epa_dha_total_with_dha_parenthetical",
        ),
        ManualRow(
            code="epa_dha_mg",
            demo=LACTATION_TOTAL,
            reference_type="AI",
            reference_amount="300",
            reference_unit="mg",
            source_page="PDF p.12 / printed p.xii",
            source_table=source_table_macro,
            source_cell="row=lactating_total;column=AI;raw=300(200_DHA)",
            source_variant="epa_dha_total_with_dha_parenthetical",
        ),
    ]
    for demo in (pregnant_amdr, lactating_amdr):
        manual_specs.extend(
            (
                ManualRow(
                    "carbohydrate_g",
                    demo,
                    "AMDR",
                    reference_amount_min="50",
                    reference_amount_max="65",
                    reference_unit="% energy",
                    source_page="PDF p.11 / printed p.xi",
                    source_table=source_table_amdr,
                    source_cell=f"row={demo.label};column=AMDR;raw=50-65",
                    source_variant="amdr_percent_energy",
                ),
                ManualRow(
                    "protein_g",
                    demo,
                    "AMDR",
                    reference_amount_min="10",
                    reference_amount_max="20",
                    reference_unit="% energy",
                    source_page="PDF p.11 / printed p.xi",
                    source_table=source_table_amdr,
                    source_cell=f"row={demo.label};column=AMDR;raw=10-20",
                    source_variant="amdr_percent_energy",
                ),
                ManualRow(
                    "fat_g",
                    demo,
                    "AMDR",
                    reference_amount_min="15",
                    reference_amount_max="30",
                    reference_unit="% energy",
                    source_page="PDF p.11 / printed p.xi",
                    source_table=source_table_amdr,
                    source_cell=f"row={demo.label};column=AMDR;raw=15-30",
                    source_variant="amdr_percent_energy",
                ),
            )
        )
    return [
        _make_row(
            metadata=metadata,
            code=row.code,
            demo=row.demo,
            reference_type=row.reference_type,
            reference_amount=row.reference_amount,
            reference_amount_min=row.reference_amount_min,
            reference_amount_max=row.reference_amount_max,
            reference_unit=row.reference_unit,
            source_page=row.source_page,
            source_table=row.source_table,
            source_cell=row.source_cell,
            source_variant=row.source_variant,
        )
        for row in manual_specs
    ]


def _write_rows(rows: Sequence[dict[str, str]], output_path: Path) -> None:
    """Write approved production rows to CSV.

    Args:
        rows: Output rows.
        output_path: Destination CSV path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CANDIDATE_ROW_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _row_sort_key(row: dict[str, str]) -> tuple[float, str, int, str, str, int]:
    """Return a stable sorting key for deterministic CSV generation.

    Args:
        row: CSV row mapping.

    Returns:
        Sort key.
    """
    target_order = {
        nutrient.target_nutrient_code: float(nutrient.official_index)
        for nutrient in TARGET_NUTRIENTS
    }
    for offset, code in enumerate(AMINO_ACID_META, start=1):
        target_order[code] = target_order["amino_acids_g"] + offset / 100
    reference_order = {
        "RNI": 0,
        "AI": 1,
        "EER": 2,
        "EAR": 3,
        "AMDR": 4,
        "CDRR": 5,
        "policy_limit": 6,
    }
    return (
        target_order.get(row["nutrient_code"], 999.0),
        row["sex"],
        int(row["age_min_months"]),
        row["pregnancy_status"],
        row["condition_detail"],
        reference_order.get(row["reference_type"], 99),
    )


def digitize_summary_pdf(extracted_dir: Path, output_path: Path) -> int:
    """Digitize the official KDRIs 2025 summary table into the production CSV.

    Args:
        extracted_dir: Directory containing extracted official KNS PDFs.
        output_path: Destination CSV path.

    Returns:
        Number of rows written.
    """
    pdfplumber = _load_pdfplumber()
    pdf_path = find_extracted_pdf(extracted_dir, SUMMARY_ARTIFACT_NAME)
    metadata = _target_meta()
    rows: list[dict[str, str]] = _manual_rows(metadata)

    with pdfplumber.open(pdf_path) as pdf:
        _process_amdr(rows, metadata, pdf.pages[10])
        _process_section(
            rows,
            metadata,
            pdf.pages[11],
            145,
            375,
            "PDF p.12 / printed p.xii",
            "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
            (
                NutrientSpec("energy_kcal", "kcal", {"EER": 161.4}),
                NutrientSpec("carbohydrate_g", "g", {"EAR": 270.2, "RNI": 297.6, "AI": 325.2}),
                NutrientSpec("fiber_g", "g", {"AI": 434.6}),
            ),
            age_x=(105, 145),
            condition_rows=(
                (
                    346.9,
                    DemoRow(
                        "pregnant_trimester_1",
                        "female",
                        SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
                        SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
                        "pregnant",
                        "pregnancy_trimester_1_additional",
                    ),
                ),
                (
                    353.9,
                    DemoRow(
                        "pregnant_trimester_2",
                        "female",
                        SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
                        SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
                        "pregnant",
                        "pregnancy_trimester_2_additional",
                    ),
                ),
                (
                    360.9,
                    DemoRow(
                        "pregnant_trimester_3",
                        "female",
                        SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
                        SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
                        "pregnant",
                        "pregnancy_trimester_3_additional",
                    ),
                ),
                (370.9, LACTATION_ADDITIONAL),
            ),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[11],
            410,
            650,
            "PDF p.12 / printed p.xii",
            "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
            (
                NutrientSpec("fat_g", "g", {"AI": 186.5}),
                NutrientSpec("linoleic_acid_g", "g", {"AI": 272.7}),
                NutrientSpec("alpha_linolenic_acid_g", "g", {"AI": 357.3}),
                NutrientSpec(
                    "epa_dha_mg",
                    "mg",
                    {"AI": 443.9},
                    source_variant="epa_dha_total_with_dha_parenthetical",
                ),
            ),
            age_x=(95, 135),
            condition_rows=((623.3, PREGNANCY_ADDITIONAL), (640.9, LACTATION_ADDITIONAL)),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[12],
            133,
            365,
            "PDF p.13 / printed p.xiii",
            "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
            (
                NutrientSpec("protein_g", "g", {"EAR": 161.1, "RNI": 188.5, "AI": 215.9}),
                NutrientSpec(
                    "methionine_cysteine_g",
                    "g",
                    {"EAR": 270.8, "RNI": 298.2, "AI": 325.6},
                    source_variant="amino_acid_component",
                ),
                NutrientSpec(
                    "leucine_g",
                    "g",
                    {"EAR": 380.4, "RNI": 407.8, "AI": 435.2},
                    source_variant="amino_acid_component",
                ),
            ),
            age_x=(105, 140),
            condition_rows=(
                (
                    364.6,
                    DemoRow(
                        "pregnant_trimester_2",
                        "female",
                        SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
                        SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
                        "pregnant",
                        "pregnancy_trimester_2_additional",
                    ),
                ),
                (369.8, PREGNANCY_TOTAL),
                (
                    375.0,
                    DemoRow(
                        "pregnant_trimester_3",
                        "female",
                        SOURCE_UNSPECIFIED_AGE_MIN_MONTHS,
                        SOURCE_UNSPECIFIED_AGE_MAX_MONTHS,
                        "pregnant",
                        "pregnancy_trimester_3_additional",
                    ),
                ),
                (385.4, LACTATION_TOTAL),
            ),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[12],
            426,
            665,
            "PDF p.13 / printed p.xiii",
            "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
            (
                NutrientSpec(
                    "isoleucine_g",
                    "g",
                    {"EAR": 161.1, "RNI": 188.5, "AI": 215.9},
                    source_variant="amino_acid_component",
                ),
                NutrientSpec(
                    "valine_g",
                    "g",
                    {"EAR": 270.8, "RNI": 298.2, "AI": 325.6},
                    source_variant="amino_acid_component",
                ),
                NutrientSpec(
                    "lysine_g",
                    "g",
                    {"EAR": 380.4, "RNI": 407.8, "AI": 435.2},
                    source_variant="amino_acid_component",
                ),
            ),
            age_x=(105, 140),
            condition_rows=((651.0, PREGNANCY_TOTAL), (661.1, LACTATION_TOTAL)),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[13],
            132,
            365,
            "PDF p.14 / printed p.xiv",
            "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
            (
                NutrientSpec(
                    "phenylalanine_tyrosine_g",
                    "g",
                    {"EAR": 162.6, "RNI": 189.9, "AI": 217.4},
                    source_variant="amino_acid_component",
                ),
                NutrientSpec(
                    "threonine_g",
                    "g",
                    {"EAR": 272.0, "RNI": 299.3, "AI": 326.7},
                    source_variant="amino_acid_component",
                ),
                NutrientSpec(
                    "tryptophan_g",
                    "g",
                    {"EAR": 381.4, "RNI": 408.7, "AI": 436.1},
                    source_variant="amino_acid_component",
                ),
            ),
            age_x=(105, 145),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[13],
            410,
            645,
            "PDF p.14 / printed p.xiv",
            "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
            (
                NutrientSpec(
                    "histidine_g",
                    "g",
                    {"EAR": 172.3, "RNI": 219.0, "AI": 265.7},
                    source_variant="amino_acid_component",
                ),
                NutrientSpec("water_ml", "mL", {"AI": 354.2}, source_variant="liquid_water"),
                NutrientSpec("water_ml", "mL", {"AI": 401.3}, source_variant="total_water"),
            ),
            age_x=(105, 145),
            condition_rows=((628.4, PREGNANCY_TOTAL), (639.7, LACTATION_TOTAL)),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[14],
            149,
            375,
            "PDF p.15 / printed p.xv",
            "2025 한국인 영양소 섭취기준 - 지용성비타민",
            (
                NutrientSpec(
                    "vitamin_a_ug",
                    "ug RAE",
                    {"EAR": 168.3, "RNI": 210.1, "AI": 251.8, "UL": 293.5},
                ),
                NutrientSpec(
                    "vitamin_d_ug",
                    "ug",
                    {"EAR": 334.6, "RNI": 374.9, "AI": 415.3, "UL": 455.6},
                ),
            ),
            age_x=(105, 145),
            condition_rows=((366.8, PREGNANCY_ADDITIONAL), (376.6, LACTATION_ADDITIONAL)),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[14],
            416,
            635,
            "PDF p.15 / printed p.xv",
            "2025 한국인 영양소 섭취기준 - 지용성비타민",
            (
                NutrientSpec(
                    "vitamin_e_mg",
                    "mg alpha-TE",
                    {"EAR": 168.3, "RNI": 210.1, "AI": 251.8, "UL": 293.5},
                ),
                NutrientSpec(
                    "vitamin_k_ug",
                    "ug",
                    {"EAR": 334.6, "RNI": 374.9, "AI": 415.3, "UL": 455.6},
                ),
            ),
            age_x=(105, 145),
            condition_rows=((622.1, PREGNANCY_ADDITIONAL), (631.4, LACTATION_ADDITIONAL)),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[15],
            149,
            650,
            "PDF p.16 / printed p.xvi",
            "2025 한국인 영양소 섭취기준 - 수용성비타민",
            (
                NutrientSpec(
                    "vitamin_c_mg",
                    "mg",
                    {"EAR": 167.8, "RNI": 208.9, "AI": 250.1, "UL": 291.3},
                ),
                NutrientSpec(
                    "thiamin_mg",
                    "mg",
                    {"EAR": 333.2, "RNI": 374.4, "AI": 415.0, "UL": 455.9},
                ),
            ),
            age_x=(105, 145),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[15],
            418,
            650,
            "PDF p.16 / printed p.xvi",
            "2025 한국인 영양소 섭취기준 - 수용성비타민",
            (
                NutrientSpec(
                    "riboflavin_mg",
                    "mg",
                    {"EAR": 163.7, "RNI": 196.6, "AI": 229.4, "UL": 262.1},
                ),
                NutrientSpec(
                    "niacin_mg",
                    "mg NE",
                    {"EAR": 297.8, "RNI": 335.8, "AI": 374.4, "UL": 435.3},
                    ul_unit="mg nicotinic acid",
                    source_variant="dual_ul_nicotinic_acid_nicotinamide",
                    ul_unit_secondary="mg nicotinamide",
                ),
            ),
            age_x=(105, 145),
            condition_rows=((636.5, PREGNANCY_ADDITIONAL), (646.3, LACTATION_ADDITIONAL)),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[16],
            136,
            635,
            "PDF p.17 / printed p.xvii",
            "2025 한국인 영양소 섭취기준 - 수용성비타민",
            (
                NutrientSpec(
                    "vitamin_b6_mg",
                    "mg",
                    {"EAR": 168.4, "RNI": 209.8, "AI": 251.6, "UL": 293.1},
                ),
                NutrientSpec(
                    "folate_ug",
                    "ug DFE",
                    {"EAR": 332.3, "RNI": 369.3, "AI": 405.4, "UL": 449.6},
                    ul_unit="ug folic acid",
                    source_variant="dfe_reference_folic_acid_ul",
                ),
            ),
            age_x=(105, 145),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[16],
            405,
            635,
            "PDF p.17 / printed p.xvii",
            "2025 한국인 영양소 섭취기준 - 수용성비타민",
            (
                NutrientSpec(
                    "vitamin_b12_ug",
                    "ug",
                    {"EAR": 161.5, "RNI": 189.0, "AI": 216.6, "UL": 243.9},
                ),
                NutrientSpec(
                    "pantothenic_acid_mg",
                    "mg",
                    {"EAR": 271.0, "RNI": 299.1, "AI": 326.5, "UL": 353.1},
                ),
                NutrientSpec("biotin_ug", "ug", {"EAR": 380.5, "RNI": 408.7, "AI": 436.0}),
            ),
            age_x=(105, 145),
            condition_rows=((623.2, PREGNANCY_ADDITIONAL), (632.9, LACTATION_ADDITIONAL)),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[17],
            154,
            455,
            "PDF p.18 / printed p.xviii",
            "2025 한국인 영양소 섭취기준 - 비타민 유사 영양소",
            (
                NutrientSpec(
                    "choline_mg",
                    "mg",
                    {"EAR": 246.0, "RNI": 310.2, "AI": 374.3, "UL": 441.3},
                ),
            ),
            age_x=(140, 215),
            condition_rows=((435.7, PREGNANCY_ADDITIONAL), (448.4, LACTATION_ADDITIONAL)),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[18],
            147,
            655,
            "PDF p.19 / printed p.xix",
            "2025 한국인 영양소 섭취기준 - 다량무기질",
            (
                NutrientSpec(
                    "calcium_mg",
                    "mg",
                    {"EAR": 155.5, "RNI": 182.9, "AI": 209.5, "UL": 235.9},
                ),
                NutrientSpec(
                    "phosphorus_mg",
                    "mg",
                    {"EAR": 262.7, "RNI": 289.6, "AI": 316.5, "UL": 343.4},
                ),
                NutrientSpec(
                    "sodium_mg",
                    "mg",
                    {"EAR": 370.3, "RNI": 397.2, "AI": 424.1, "CDRR": 457.1},
                ),
            ),
            age_x=(100, 135),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[18],
            433,
            655,
            "PDF p.19 / printed p.xix",
            "2025 한국인 영양소 섭취기준 - 다량무기질",
            (
                NutrientSpec(
                    "chloride_mg",
                    "mg",
                    {"EAR": 155.5, "RNI": 182.9, "AI": 209.5, "UL": 235.9},
                ),
                NutrientSpec(
                    "potassium_mg",
                    "mg",
                    {"EAR": 262.7, "RNI": 289.6, "AI": 316.5, "UL": 343.4},
                ),
                NutrientSpec(
                    "magnesium_mg",
                    "mg",
                    {"EAR": 370.3, "RNI": 397.2, "AI": 424.1, "UL": 457.1},
                    ul_unit="mg supplemental",
                ),
            ),
            age_x=(100, 135),
            condition_rows=((643.9, PREGNANCY_ADDITIONAL), (653.5, LACTATION_ADDITIONAL)),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[19],
            149,
            655,
            "PDF p.20 / printed p.xx",
            "2025 한국인 영양소 섭취기준 - 미량무기질",
            (
                NutrientSpec(
                    "iron_mg",
                    "mg",
                    {"EAR": 161.2, "RNI": 188.5, "AI": 215.9, "UL": 243.2},
                ),
                NutrientSpec(
                    "zinc_mg",
                    "mg",
                    {"EAR": 270.6, "RNI": 297.9, "AI": 325.3, "UL": 352.6},
                ),
                NutrientSpec(
                    "copper_ug",
                    "ug",
                    {"EAR": 380.0, "RNI": 407.3, "AI": 434.7, "UL": 462.0},
                ),
            ),
            age_x=(105, 145),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[19],
            421,
            655,
            "PDF p.20 / printed p.xx",
            "2025 한국인 영양소 섭취기준 - 미량무기질",
            (
                NutrientSpec(
                    "fluoride_mg",
                    "mg",
                    {"EAR": 161.2, "RNI": 188.5, "AI": 215.9, "UL": 243.2},
                ),
                NutrientSpec(
                    "manganese_mg",
                    "mg",
                    {"EAR": 270.6, "RNI": 297.9, "AI": 325.3, "UL": 352.6},
                ),
                NutrientSpec(
                    "iodine_ug",
                    "ug",
                    {"EAR": 380.0, "RNI": 407.3, "AI": 434.7, "UL": 462.0},
                ),
            ),
            age_x=(105, 145),
            condition_rows=((644.5, PREGNANCY_ADDITIONAL), (654.7, LACTATION_ADDITIONAL)),
        )
        _process_section(
            rows,
            metadata,
            pdf.pages[20],
            133,
            365,
            "PDF p.21 / printed p.xxi",
            "2025 한국인 영양소 섭취기준 - 미량무기질",
            (
                NutrientSpec(
                    "selenium_ug",
                    "ug",
                    {"EAR": 161.2, "RNI": 188.5, "AI": 215.9, "UL": 243.2},
                ),
                NutrientSpec(
                    "molybdenum_ug",
                    "ug",
                    {"EAR": 270.6, "RNI": 297.9, "AI": 325.3, "UL": 352.6},
                ),
                NutrientSpec(
                    "chromium_ug",
                    "ug",
                    {"EAR": 380.0, "RNI": 407.3, "AI": 434.7, "UL": 462.0},
                ),
            ),
            age_x=(105, 145),
            condition_rows=((352.5, PREGNANCY_ADDITIONAL), (362.4, LACTATION_ADDITIONAL)),
        )

    rows.sort(key=_row_sort_key)
    _write_rows(rows, output_path)
    return len(rows)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser.

    Returns:
        Configured parser.
    """
    parser = argparse.ArgumentParser(description="Digitize KDRIs 2025 official summary CSV.")
    parser.add_argument("--extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the KDRIs 2025 digitization CLI.

    Args:
        argv: Optional CLI arguments.

    Returns:
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    row_count = digitize_summary_pdf(args.extracted_dir, args.output)
    print(f"Digitized {row_count} approved KDRIs 2025 rows into {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
