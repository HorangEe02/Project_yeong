"""Prepare review artifacts for KDRIs 2025 row digitization."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "kdris" / "2025"
DEFAULT_EXTRACTED_DIR = DEFAULT_RAW_DIR / "kns_2025_kdri_books_summaries_errata_f4"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "kdris" / "review" / "2025"

KNS_SOURCE_URL = "https://www.kns.or.kr/FileRoom/FileRoom_view.asp?BoardID=Kdr&idx=167"
MOHW_SOURCE_URL = "https://m.korea.kr/briefing/pressReleaseView.do?newsId=156737581"
CURRENT_ERRATA_VERSION = "2026-03-16"
RETRIEVED_AT = "2026-05-14"
REVIEWER_1 = "source_check_1"
REVIEWER_2 = "source_check_2"
CANDIDATE_SOURCE_ID = "kns_2025_kdris_publication"

INVENTORY_FIELDNAMES = (
    "official_index",
    "target_nutrient_code",
    "nutrient_name_ko",
    "nutrient_name_en",
    "nutrient_group",
    "official_group",
    "default_unit",
    "source_artifact",
    "source_pages",
    "source_table",
    "digitization_scope",
    "review_status",
    "reviewer_1",
    "reviewer_2",
    "errata_version",
    "notes",
)
CANDIDATE_ROW_FIELDNAMES = (
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
ISSUE_FIELDNAMES = (
    "nutrient_code",
    "source_artifact",
    "source_page",
    "source_table",
    "source_cell",
    "issue_type",
    "issue_detail",
    "recommended_action",
)


@dataclass(frozen=True)
class SourceArtifact:
    """Official source artifact expected in the KDRIs 2025 raw directory.

    Args:
        id: Stable artifact identifier.
        relative_path: Path relative to the raw KDRIs 2025 directory.
        source_url: Official source page or direct download URL.
        checksum_sha256: Expected SHA-256 checksum.
        artifact_type: Artifact classification for review logs.
    """

    id: str
    relative_path: str
    source_url: str
    checksum_sha256: str
    artifact_type: str


@dataclass(frozen=True)
class TargetNutrient:
    """Official KDRIs 2025 nutrient target queued for row digitization.

    Args:
        official_index: One-based official target index for review ordering.
        target_nutrient_code: Proposed internal nutrient code.
        nutrient_name_ko: Korean nutrient name from KDRIs source context.
        nutrient_name_en: English nutrient name for API and reviewer readability.
        nutrient_group: Project grouping for the KDRIs dataset.
        official_group: Official KDRIs group label.
        default_unit: Default unit used by the 2025 summary tables.
        source_artifact: Reviewed official artifact name.
        source_pages: PDF page and printed page locator.
        source_table: Source table name in the artifact.
        digitization_scope: How row values should be digitized for this nutrient.
        notes: Reviewer-facing clarification.
    """

    official_index: int
    target_nutrient_code: str
    nutrient_name_ko: str
    nutrient_name_en: str
    nutrient_group: str
    official_group: str
    default_unit: str
    source_artifact: str
    source_pages: str
    source_table: str
    digitization_scope: str
    notes: str = ""


@dataclass(frozen=True)
class CandidateIssue:
    """Unresolved issue blocking production approval for a candidate row group.

    Args:
        nutrient_code: Candidate nutrient code affected by the issue.
        source_artifact: Official artifact containing the issue.
        source_page: PDF/printed page locator.
        source_table: Official table locator.
        source_cell: Cell or column locator requiring a decision.
        issue_type: Stable issue category.
        issue_detail: Reviewer-facing issue description.
        recommended_action: Recommended resolution before production approval.
    """

    nutrient_code: str
    source_artifact: str
    source_page: str
    source_table: str
    source_cell: str
    issue_type: str
    issue_detail: str
    recommended_action: str


EXPECTED_RAW_ARTIFACTS: tuple[SourceArtifact, ...] = (
    SourceArtifact(
        id="kns_2025_kdri_books_summaries_errata_f4_zip",
        relative_path="kns_2025_kdri_books_summaries_errata_f4.zip",
        source_url=KNS_SOURCE_URL,
        checksum_sha256="26966013355039668bfc9eae799e86bd7ca45c27942ae5d10fb41c637913a6cb",
        artifact_type="official_publication_archive",
    ),
    SourceArtifact(
        id="kns_2025_kdri_korean_summary_pdf",
        relative_path="kns_2025_kdri_korean_summary_2025-12-29.pdf",
        source_url=KNS_SOURCE_URL,
        checksum_sha256="605ff8431ea7b6c465165bb5335aba580dcd4d56ba13a69583e62d163a7cc0c2",
        artifact_type="official_summary_pdf",
    ),
    SourceArtifact(
        id="mohw_2025_kdri_press_release_hwpx",
        relative_path="mohw_2025_kdri_press_release.hwpx",
        source_url=MOHW_SOURCE_URL,
        checksum_sha256="c41eba906c21a3fd829097ca052b15bec11a9ecf1b31cd6288ed5324af5a4451",
        artifact_type="official_press_release",
    ),
    SourceArtifact(
        id="mohw_2025_kdri_press_release_pdf",
        relative_path="mohw_2025_kdri_press_release.pdf",
        source_url=MOHW_SOURCE_URL,
        checksum_sha256="7dba5811d43ab05ab4c3fda9fa90f7ab6b0e7192635a018a7c82ba7b93e27ef5",
        artifact_type="official_press_release",
    ),
    SourceArtifact(
        id="mohw_2025_kdri_2020_comparison_pdf",
        relative_path="mohw_2025_kdri_2020_comparison.pdf",
        source_url=MOHW_SOURCE_URL,
        checksum_sha256="0d7bb12f94ce205c0782fbfd1184bf91e00df31f69aa1dd0546bd90b6173ccd7",
        artifact_type="official_comparison_pdf",
    ),
)

SUMMARY_ARTIFACT_NAME = "웹용_2025 KDRI-국문 요약본.pdf"
ERRATA_ARTIFACT_NAME = "2025 KDRI_정오표_1차(26.2.2)_2차(26.2.27)_3차(26.3.16).pdf"
SUMMARY_TABLE_ARTIFACT = "kns_2025_kdri_books_summaries_errata_f4/웹용_2025 KDRI-국문 요약본.pdf"

TARGET_NUTRIENTS: tuple[TargetNutrient, ...] = (
    TargetNutrient(
        1,
        "energy_kcal",
        "에너지",
        "Energy",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "kcal",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.12 / printed p.xii",
        "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
        "digitize EER by age/sex and pregnancy/lactation additive rows",
    ),
    TargetNutrient(
        2,
        "carbohydrate_g",
        "탄수화물",
        "Carbohydrate",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "g",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.11-12 / printed p.xi-xii",
        "2025 한국인 영양소 섭취기준 - 에너지적정비율; 에너지와 다량영양소",
        "digitize AMDR range and EAR/RNI scalar rows",
    ),
    TargetNutrient(
        3,
        "total_sugars_percent_energy",
        "총당류",
        "Total sugars",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "% energy",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.11 / printed p.xi",
        "2025 한국인 영양소 섭취기준 - 당류",
        "digitize narrative limit as CDRR-like range after reviewer policy decision",
    ),
    TargetNutrient(
        4,
        "fat_g",
        "지질",
        "Fat",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "g",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.11-12 / printed p.xi-xii",
        "2025 한국인 영양소 섭취기준 - 에너지적정비율; 에너지와 다량영양소",
        "digitize AMDR range and AI scalar rows",
    ),
    TargetNutrient(
        5,
        "protein_g",
        "단백질",
        "Protein",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "g",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.11,13 / printed p.xi,xiii",
        "2025 한국인 영양소 섭취기준 - 에너지적정비율; 에너지와 다량영양소",
        "digitize AMDR range and EAR/RNI scalar rows",
    ),
    TargetNutrient(
        6,
        "amino_acids_g",
        "아미노산",
        "Amino acids",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "g",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.13-14 / printed p.xiii-xiv",
        "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
        "digitize table sub-columns; final schema may need sub-nutrient codes",
        "Official 41-count treats amino acids as one target, but the table has multiple amino acid columns.",
    ),
    TargetNutrient(
        7,
        "alpha_linolenic_acid_g",
        "알파-리놀렌산",
        "Alpha-linolenic acid",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "g",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.12 / printed p.xii",
        "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
        "digitize AI scalar rows",
    ),
    TargetNutrient(
        8,
        "linoleic_acid_g",
        "리놀레산",
        "Linoleic acid",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "g",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.12 / printed p.xii",
        "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
        "digitize AI scalar rows",
    ),
    TargetNutrient(
        9,
        "epa_dha_mg",
        "EPA+DHA",
        "EPA+DHA",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.12 / printed p.xii",
        "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
        "digitize AI scalar rows and DHA footnote where applicable",
    ),
    TargetNutrient(
        10,
        "cholesterol_mg",
        "콜레스테롤",
        "Cholesterol",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.11 / printed p.xi",
        "2025 한국인 영양소 섭취기준 - 에너지적정비율",
        "digitize adult narrative recommendation after reviewer policy decision",
    ),
    TargetNutrient(
        11,
        "fiber_g",
        "식이섬유",
        "Dietary fiber",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "g",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.12 / printed p.xii",
        "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
        "digitize AI scalar rows",
    ),
    TargetNutrient(
        12,
        "water_ml",
        "수분",
        "Water",
        "energy_macronutrient",
        "에너지와 다량영양소",
        "mL",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.14 / printed p.xiv",
        "2025 한국인 영양소 섭취기준 - 에너지와 다량영양소",
        "digitize liquid and total-water AI rows; final schema may need source_cell distinction",
    ),
    TargetNutrient(
        13,
        "vitamin_a_ug",
        "비타민 A",
        "Vitamin A",
        "vitamin",
        "비타민",
        "ug RAE",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.15 / printed p.xv",
        "2025 한국인 영양소 섭취기준 - 지용성비타민",
        "digitize EAR/RNI/UL scalar rows",
    ),
    TargetNutrient(
        14,
        "vitamin_d_ug",
        "비타민 D",
        "Vitamin D",
        "vitamin",
        "비타민",
        "ug",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.15 / printed p.xv",
        "2025 한국인 영양소 섭취기준 - 지용성비타민",
        "digitize AI/UL scalar rows",
    ),
    TargetNutrient(
        15,
        "vitamin_e_mg",
        "비타민 E",
        "Vitamin E",
        "vitamin",
        "비타민",
        "mg alpha-TE",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.15 / printed p.xv",
        "2025 한국인 영양소 섭취기준 - 지용성비타민",
        "digitize AI/UL scalar rows",
    ),
    TargetNutrient(
        16,
        "vitamin_k_ug",
        "비타민 K",
        "Vitamin K",
        "vitamin",
        "비타민",
        "ug",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.15 / printed p.xv",
        "2025 한국인 영양소 섭취기준 - 지용성비타민",
        "digitize AI scalar rows",
    ),
    TargetNutrient(
        17,
        "vitamin_c_mg",
        "비타민 C",
        "Vitamin C",
        "vitamin",
        "비타민",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.16 / printed p.xvi",
        "2025 한국인 영양소 섭취기준 - 수용성비타민",
        "digitize EAR/RNI/UL scalar rows",
    ),
    TargetNutrient(
        18,
        "thiamin_mg",
        "티아민",
        "Thiamin",
        "vitamin",
        "비타민",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.16 / printed p.xvi",
        "2025 한국인 영양소 섭취기준 - 수용성비타민",
        "digitize EAR/RNI/AI scalar rows",
    ),
    TargetNutrient(
        19,
        "riboflavin_mg",
        "리보플라빈",
        "Riboflavin",
        "vitamin",
        "비타민",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.16 / printed p.xvi",
        "2025 한국인 영양소 섭취기준 - 수용성비타민",
        "digitize EAR/RNI/AI scalar rows",
    ),
    TargetNutrient(
        20,
        "niacin_mg",
        "니아신",
        "Niacin",
        "vitamin",
        "비타민",
        "mg NE",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.16 / printed p.xvi",
        "2025 한국인 영양소 섭취기준 - 수용성비타민",
        "digitize EAR/RNI/UL scalar rows; preserve nicotinic acid/nicotinamide UL split in source_cell notes",
    ),
    TargetNutrient(
        21,
        "vitamin_b6_mg",
        "비타민 B6",
        "Vitamin B6",
        "vitamin",
        "비타민",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.17 / printed p.xvii",
        "2025 한국인 영양소 섭취기준 - 수용성비타민",
        "digitize EAR/RNI/UL scalar rows",
    ),
    TargetNutrient(
        22,
        "folate_ug",
        "엽산",
        "Folate",
        "vitamin",
        "비타민",
        "ug DFE",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.17 / printed p.xvii",
        "2025 한국인 영양소 섭취기준 - 수용성비타민",
        "digitize DFE rows and folic-acid UL rows; final schema may need unit distinction",
    ),
    TargetNutrient(
        23,
        "vitamin_b12_ug",
        "비타민 B12",
        "Vitamin B12",
        "vitamin",
        "비타민",
        "ug",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.17 / printed p.xvii",
        "2025 한국인 영양소 섭취기준 - 수용성비타민",
        "digitize EAR/RNI/AI scalar rows",
    ),
    TargetNutrient(
        24,
        "pantothenic_acid_mg",
        "판토텐산",
        "Pantothenic acid",
        "vitamin",
        "비타민",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.17 / printed p.xvii",
        "2025 한국인 영양소 섭취기준 - 수용성비타민",
        "digitize AI scalar rows",
    ),
    TargetNutrient(
        25,
        "biotin_ug",
        "비오틴",
        "Biotin",
        "vitamin",
        "비타민",
        "ug",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.17 / printed p.xvii",
        "2025 한국인 영양소 섭취기준 - 수용성비타민",
        "digitize AI scalar rows",
    ),
    TargetNutrient(
        26,
        "calcium_mg",
        "칼슘",
        "Calcium",
        "mineral",
        "무기질",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.19 / printed p.xix",
        "2025 한국인 영양소 섭취기준 - 다량무기질",
        "digitize EAR/RNI/UL scalar rows",
    ),
    TargetNutrient(
        27,
        "phosphorus_mg",
        "인",
        "Phosphorus",
        "mineral",
        "무기질",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.19 / printed p.xix",
        "2025 한국인 영양소 섭취기준 - 다량무기질",
        "digitize EAR/RNI/UL scalar rows",
    ),
    TargetNutrient(
        28,
        "sodium_mg",
        "나트륨",
        "Sodium",
        "mineral",
        "무기질",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.19 / printed p.xix",
        "2025 한국인 영양소 섭취기준 - 다량무기질",
        "digitize AI and CDRR scalar rows",
    ),
    TargetNutrient(
        29,
        "chloride_mg",
        "염소",
        "Chloride",
        "mineral",
        "무기질",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.19 / printed p.xix",
        "2025 한국인 영양소 섭취기준 - 다량무기질",
        "digitize AI scalar rows",
    ),
    TargetNutrient(
        30,
        "potassium_mg",
        "칼륨",
        "Potassium",
        "mineral",
        "무기질",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.19 / printed p.xix",
        "2025 한국인 영양소 섭취기준 - 다량무기질",
        "digitize AI scalar rows",
    ),
    TargetNutrient(
        31,
        "magnesium_mg",
        "마그네슘",
        "Magnesium",
        "mineral",
        "무기질",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.19 / printed p.xix",
        "2025 한국인 영양소 섭취기준 - 다량무기질",
        "digitize EAR/RNI and non-food-source UL rows",
    ),
    TargetNutrient(
        32,
        "iron_mg",
        "철",
        "Iron",
        "mineral",
        "무기질",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.20 / printed p.xx",
        "2025 한국인 영양소 섭취기준 - 미량무기질",
        "digitize EAR/RNI/UL scalar rows",
    ),
    TargetNutrient(
        33,
        "zinc_mg",
        "아연",
        "Zinc",
        "mineral",
        "무기질",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.20 / printed p.xx",
        "2025 한국인 영양소 섭취기준 - 미량무기질",
        "digitize EAR/RNI/UL scalar rows",
    ),
    TargetNutrient(
        34,
        "copper_ug",
        "구리",
        "Copper",
        "mineral",
        "무기질",
        "ug",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.20 / printed p.xx",
        "2025 한국인 영양소 섭취기준 - 미량무기질",
        "digitize EAR/RNI/UL scalar rows",
        "Current project reference registry uses copper_mg; production mapping needs a unit decision.",
    ),
    TargetNutrient(
        35,
        "fluoride_mg",
        "불소",
        "Fluoride",
        "mineral",
        "무기질",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.20 / printed p.xx",
        "2025 한국인 영양소 섭취기준 - 미량무기질",
        "digitize AI/UL scalar rows",
    ),
    TargetNutrient(
        36,
        "manganese_mg",
        "망간",
        "Manganese",
        "mineral",
        "무기질",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.20 / printed p.xx",
        "2025 한국인 영양소 섭취기준 - 미량무기질",
        "digitize AI/UL scalar rows",
    ),
    TargetNutrient(
        37,
        "iodine_ug",
        "요오드",
        "Iodine",
        "mineral",
        "무기질",
        "ug",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.20 / printed p.xx",
        "2025 한국인 영양소 섭취기준 - 미량무기질",
        "digitize EAR/RNI/UL scalar rows",
    ),
    TargetNutrient(
        38,
        "selenium_ug",
        "셀레늄",
        "Selenium",
        "mineral",
        "무기질",
        "ug",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.21 / printed p.xxi",
        "2025 한국인 영양소 섭취기준 - 미량무기질",
        "digitize EAR/RNI/UL scalar rows",
    ),
    TargetNutrient(
        39,
        "molybdenum_ug",
        "몰리브덴",
        "Molybdenum",
        "mineral",
        "무기질",
        "ug",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.21 / printed p.xxi",
        "2025 한국인 영양소 섭취기준 - 미량무기질",
        "digitize EAR/RNI/UL scalar rows",
    ),
    TargetNutrient(
        40,
        "chromium_ug",
        "크롬",
        "Chromium",
        "mineral",
        "무기질",
        "ug",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.21 / printed p.xxi",
        "2025 한국인 영양소 섭취기준 - 미량무기질",
        "digitize AI scalar rows",
    ),
    TargetNutrient(
        41,
        "choline_mg",
        "콜린",
        "Choline",
        "vitamin_like",
        "비타민 유사 영양소",
        "mg",
        SUMMARY_TABLE_ARTIFACT,
        "PDF p.18 / printed p.xviii",
        "2025 한국인 영양소 섭취기준 - 비타민 유사 영양소 (제정)",
        "digitize AI/UL scalar rows",
    ),
)

SCHEMA_DECISION_ISSUES: tuple[CandidateIssue, ...] = (
    CandidateIssue(
        nutrient_code="amino_acids_g",
        source_artifact=SUMMARY_TABLE_ARTIFACT,
        source_page="PDF p.16 / printed p.xvi",
        source_table="2025 한국인 영양소 섭취기준 - 아미노산",
        source_cell="amino_acid_columns",
        issue_type="schema_decision_resolved",
        issue_detail=(
            "Official KDRIs counts amino acids as one target nutrient, but the summary "
            "table exposes multiple amino acid columns."
        ),
        recommended_action=(
            "Production rows use reviewed amino-acid component nutrient codes; "
            "amino_acids_g remains the official umbrella inventory item."
        ),
    ),
    CandidateIssue(
        nutrient_code="copper_ug",
        source_artifact=SUMMARY_TABLE_ARTIFACT,
        source_page="PDF p.21 / printed p.xxi",
        source_table="2025 한국인 영양소 섭취기준 - 미량무기질",
        source_cell="copper_unit",
        issue_type="schema_decision_resolved",
        issue_detail=(
            "The official copper table uses ug, while the existing project registry "
            "has used copper_mg in older sample data."
        ),
        recommended_action=(
            "Production rows use copper_ug exactly as the official table unit; "
            "no mg normalization is applied in the KDRIs CSV."
        ),
    ),
    CandidateIssue(
        nutrient_code="folate_ug",
        source_artifact=SUMMARY_TABLE_ARTIFACT,
        source_page="PDF p.18 / printed p.xviii",
        source_table="2025 한국인 영양소 섭취기준 - 수용성비타민",
        source_cell="folate_dfe_and_folic_acid_ul",
        issue_type="schema_decision_resolved",
        issue_detail=(
            "Folate rows use dietary folate equivalent semantics, while folic-acid "
            "UL rows have a different source meaning."
        ),
        recommended_action=(
            "Production rows use reference_unit=ug DFE and ul_unit=ug folic acid "
            "with source_variant=dfe_reference_folic_acid_ul."
        ),
    ),
    CandidateIssue(
        nutrient_code="water_ml",
        source_artifact=SUMMARY_TABLE_ARTIFACT,
        source_page="PDF p.15 / printed p.xv",
        source_table="2025 한국인 영양소 섭취기준 - 수분",
        source_cell="liquid_water_and_total_water_columns",
        issue_type="schema_decision_resolved",
        issue_detail=(
            "Water AI tables distinguish liquid water and total water columns that "
            "should not be collapsed without review."
        ),
        recommended_action=(
            "Production rows keep nutrient_code=water_ml and encode the official "
            "columns with source_variant=liquid_water or total_water."
        ),
    ),
    CandidateIssue(
        nutrient_code="total_sugars_percent_energy",
        source_artifact=SUMMARY_TABLE_ARTIFACT,
        source_page="PDF p.11 / printed p.xi",
        source_table="2025 한국인 영양소 섭취기준 - 당류",
        source_cell="narrative_limit",
        issue_type="schema_decision_resolved",
        issue_detail=(
            "Total sugars are presented as a narrative energy-percent limit, not a "
            "simple EAR/RNI/AI scalar table."
        ),
        recommended_action=(
            "Production rows encode this narrative limit as reference_type=policy_limit "
            "with range 0-20 % energy and source_variant=narrative_limit."
        ),
    ),
    CandidateIssue(
        nutrient_code="cholesterol_mg",
        source_artifact=SUMMARY_TABLE_ARTIFACT,
        source_page="PDF p.14 / printed p.xiv",
        source_table="2025 한국인 영양소 섭취기준 - 콜레스테롤",
        source_cell="adult_narrative_recommendation",
        issue_type="schema_decision_resolved",
        issue_detail=(
            "Cholesterol guidance is captured as a narrative adult recommendation "
            "rather than a full age-by-sex scalar table."
        ),
        recommended_action=(
            "Production rows encode this adult narrative recommendation as "
            "reference_type=policy_limit for age 19+ with range 0-300 mg."
        ),
    ),
)


def sha256(path: Path) -> str:
    """Return the SHA-256 digest for a source artifact.

    Args:
        path: File to hash.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_raw_artifacts(
    raw_dir: Path,
    expected_artifacts: Sequence[SourceArtifact] = EXPECTED_RAW_ARTIFACTS,
) -> list[dict[str, str]]:
    """Verify official raw artifact checksums.

    Args:
        raw_dir: Raw KDRIs 2025 artifact directory.
        expected_artifacts: Artifacts that must exist with matching checksums.

    Returns:
        Manifest-style artifact records.

    Raises:
        FileNotFoundError: If an expected artifact is missing.
        ValueError: If a checksum does not match.
    """
    records: list[dict[str, str]] = []
    for artifact in expected_artifacts:
        path = raw_dir / artifact.relative_path
        if not path.exists():
            raise FileNotFoundError(f"missing official source artifact: {path}")
        actual_checksum = sha256(path)
        if actual_checksum != artifact.checksum_sha256:
            raise ValueError(
                "checksum mismatch for "
                f"{artifact.relative_path}: expected {artifact.checksum_sha256}, got {actual_checksum}"
            )
        record = asdict(artifact)
        try:
            record["path"] = path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            record["path"] = path.as_posix()
        record["retrieved_at"] = RETRIEVED_AT
        records.append(record)
    return records


def _normalized_name(path: Path) -> str:
    """Return a Unicode-normalized file name for Korean PDF matching.

    Args:
        path: Source path.

    Returns:
        NFC-normalized filename.
    """
    return unicodedata.normalize("NFC", path.name)


def find_extracted_pdf(extracted_dir: Path, expected_name: str) -> Path:
    """Find an extracted source PDF by normalized Korean filename.

    Args:
        extracted_dir: Directory containing PDFs extracted from the KNS ZIP.
        expected_name: NFC-normalized expected filename.

    Returns:
        Matching PDF path.

    Raises:
        FileNotFoundError: If the PDF is not present.
    """
    for pdf_path in extracted_dir.glob("*.pdf"):
        if _normalized_name(pdf_path) == expected_name:
            return pdf_path
    raise FileNotFoundError(f"missing extracted PDF: {expected_name}")


def run_pdftotext(
    pdf_path: Path,
    output_path: Path,
    page_start: int,
    page_end: int,
    pdftotext_bin: str,
) -> None:
    """Extract layout-preserving text from one PDF page range.

    Args:
        pdf_path: Source PDF path.
        output_path: Destination text path.
        page_start: First one-based PDF page.
        page_end: Last one-based PDF page.
        pdftotext_bin: `pdftotext` executable path or command name.

    Raises:
        RuntimeError: If `pdftotext` fails.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        pdftotext_bin,
        "-layout",
        "-f",
        str(page_start),
        "-l",
        str(page_end),
        str(pdf_path),
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, check=False, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"pdftotext failed for {pdf_path}")


def write_target_nutrient_inventory(path: Path) -> None:
    """Write the official 41-target KDRIs 2025 nutrient inventory.

    Args:
        path: Destination CSV path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=INVENTORY_FIELDNAMES)
        writer.writeheader()
        for nutrient in TARGET_NUTRIENTS:
            row = asdict(nutrient)
            row["review_status"] = "needs_review"
            row["reviewer_1"] = REVIEWER_1
            row["reviewer_2"] = REVIEWER_2
            row["errata_version"] = CURRENT_ERRATA_VERSION
            writer.writerow(row)


def build_candidate_row(nutrient: TargetNutrient) -> dict[str, str]:
    """Build a review-stage candidate row skeleton for one target nutrient.

    Args:
        nutrient: Official target nutrient inventory entry.

    Returns:
        Candidate CSV row. Numeric source values are intentionally blank until
        reviewers digitize and approve the official table cells.
    """
    return {
        "nutrient_code": nutrient.target_nutrient_code,
        "nutrient_name_ko": nutrient.nutrient_name_ko,
        "nutrient_name_en": nutrient.nutrient_name_en,
        "nutrient_group": nutrient.nutrient_group,
        "sex": "",
        "age_min_months": "",
        "age_max_months": "",
        "pregnancy_status": "",
        "condition_detail": "",
        "source_variant": "",
        "reference_type": "TBD",
        "reference_amount": "",
        "reference_amount_min": "",
        "reference_amount_max": "",
        "reference_unit": nutrient.default_unit,
        "ul_amount": "",
        "ul_unit": "",
        "ul_amount_secondary": "",
        "ul_unit_secondary": "",
        "source_id": CANDIDATE_SOURCE_ID,
        "source_artifact": nutrient.source_artifact,
        "source_page": nutrient.source_pages,
        "source_table": nutrient.source_table,
        "source_cell": (
            f"target_nutrient={nutrient.official_index};" "values=pending_source_digitization"
        ),
        "errata_version": CURRENT_ERRATA_VERSION,
        "review_status": "needs_review",
        "reviewer_1": REVIEWER_1,
        "reviewer_2": REVIEWER_2,
        "reviewed_at": "",
    }


def write_candidate_rows(path: Path) -> None:
    """Write review-stage candidate row skeletons for all 41 nutrients.

    Args:
        path: Destination CSV path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CANDIDATE_ROW_FIELDNAMES)
        writer.writeheader()
        for nutrient in TARGET_NUTRIENTS:
            writer.writerow(build_candidate_row(nutrient))


def write_candidate_issues(path: Path) -> None:
    """Write known schema decisions that block production approval.

    Args:
        path: Destination CSV path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=ISSUE_FIELDNAMES)
        writer.writeheader()
        for issue in SCHEMA_DECISION_ISSUES:
            writer.writerow(asdict(issue))


def write_review_scope(path: Path, outputs: dict[str, str]) -> None:
    """Write reviewer instructions for the next row digitization step.

    Args:
        path: Destination Markdown path.
        outputs: Generated artifact path map.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"""# KDRIs 2025 Digitization Review Scope

Generated at: `{RETRIEVED_AT}` Asia/Seoul.

## Official Sources

- KNS publication and errata page: {KNS_SOURCE_URL}
- MOHW policy briefing page: {MOHW_SOURCE_URL}

## Generated Artifacts

- Target nutrient inventory: `{outputs["inventory"]}`
- Candidate row skeletons: `{outputs["candidate_rows"]}`
- Candidate blocking issues: `{outputs["candidate_issues"]}`
- Source artifact manifest: `{outputs["source_manifest"]}`
- Summary table text: `{outputs["summary_text"]}`
- Errata text: `{outputs["errata_text"]}`

## Review Rules

1. Use `data/nutrition_reference/kdris/kdris_2025.csv` only for rows that two independent source checks approve.
2. Keep all unapproved extracted values outside the production CSV.
3. Every production row must record `source_artifact`, `source_page`, `source_table`, `source_cell`, `reviewer_1`, `reviewer_2`, and `reviewed_at`.
4. Apply the `2026-03-16` errata before marking any row approved.
5. Preserve ambiguous table cases for review instead of guessing values.
6. Use neutral reviewer identifiers `{REVIEWER_1}` and `{REVIEWER_2}` unless project roles are assigned later.

## Resolved Schema Decisions For Production

- Amino acids: production rows use component nutrient codes while `amino_acids_g` stays as the official umbrella inventory item.
- Copper: production rows use official `copper_ug`; no mg normalization is applied in the KDRIs CSV.
- Folate: production rows use `reference_unit=ug DFE`, `ul_unit=ug folic acid`, and `source_variant=dfe_reference_folic_acid_ul`.
- Water: production rows keep `nutrient_code=water_ml` and distinguish `source_variant=liquid_water` from `source_variant=total_water`.
- Total sugars: production rows use `reference_type=policy_limit`, range `0-20 % energy`, and `source_variant=narrative_limit`.
- Cholesterol: production rows use `reference_type=policy_limit`, range `0-300 mg`, and age scope `19+`.
"""
    path.write_text(content, encoding="utf-8")


def write_source_manifest(path: Path, artifact_records: Sequence[dict[str, str]]) -> None:
    """Write a review-stage source artifact manifest.

    Args:
        path: Destination JSON path.
        artifact_records: Verified raw artifact records.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "reference_year": 2025,
        "retrieved_at": RETRIEVED_AT,
        "errata_version": CURRENT_ERRATA_VERSION,
        "review_status": "needs_row_digitization_review",
        "official_target_nutrient_count": len(TARGET_NUTRIENTS),
        "artifacts": list(artifact_records),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_digitization_artifacts(
    raw_dir: Path,
    extracted_dir: Path,
    output_dir: Path,
    pdftotext_bin: str,
) -> dict[str, str]:
    """Prepare KDRIs 2025 review artifacts from official PDFs.

    Args:
        raw_dir: Directory with committed official raw artifacts.
        extracted_dir: Directory with PDFs extracted from the KNS archive.
        output_dir: Destination directory for review artifacts.
        pdftotext_bin: `pdftotext` executable path or command name.

    Returns:
        Mapping of generated artifact labels to project-relative paths.
    """
    artifact_records = verify_raw_artifacts(raw_dir)
    summary_pdf = find_extracted_pdf(extracted_dir, SUMMARY_ARTIFACT_NAME)
    errata_pdf = find_extracted_pdf(extracted_dir, ERRATA_ARTIFACT_NAME)

    inventory_path = output_dir / "kdris_2025_target_nutrient_inventory.csv"
    candidate_rows_path = output_dir / "kdris_2025_candidate_rows.csv"
    candidate_issues_path = output_dir / "kdris_2025_candidate_issues.csv"
    source_manifest_path = output_dir / "kdris_2025_source_artifacts.json"
    summary_text_path = output_dir / "source_text" / "kns_summary_pages_11_21.txt"
    errata_text_path = output_dir / "source_text" / "kns_errata_2026_03_16.txt"
    review_scope_path = output_dir / "README.md"

    run_pdftotext(summary_pdf, summary_text_path, 11, 21, pdftotext_bin)
    run_pdftotext(errata_pdf, errata_text_path, 1, 1, pdftotext_bin)
    write_target_nutrient_inventory(inventory_path)
    write_candidate_rows(candidate_rows_path)
    write_candidate_issues(candidate_issues_path)
    write_source_manifest(source_manifest_path, artifact_records)

    outputs = {
        "inventory": inventory_path.relative_to(PROJECT_ROOT).as_posix(),
        "candidate_rows": candidate_rows_path.relative_to(PROJECT_ROOT).as_posix(),
        "candidate_issues": candidate_issues_path.relative_to(PROJECT_ROOT).as_posix(),
        "source_manifest": source_manifest_path.relative_to(PROJECT_ROOT).as_posix(),
        "summary_text": summary_text_path.relative_to(PROJECT_ROOT).as_posix(),
        "errata_text": errata_text_path.relative_to(PROJECT_ROOT).as_posix(),
        "review_scope": review_scope_path.relative_to(PROJECT_ROOT).as_posix(),
    }
    write_review_scope(review_scope_path, outputs)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Prepare KDRIs 2025 source text and nutrient inventory review artifacts."
    )
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--pdftotext-bin", default="pdftotext")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the KDRIs 2025 digitization artifact preparation CLI.

    Args:
        argv: Optional CLI argument override for tests.

    Returns:
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    outputs = prepare_digitization_artifacts(
        raw_dir=args.raw_dir,
        extracted_dir=args.extracted_dir,
        output_dir=args.output_dir,
        pdftotext_bin=args.pdftotext_bin,
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
