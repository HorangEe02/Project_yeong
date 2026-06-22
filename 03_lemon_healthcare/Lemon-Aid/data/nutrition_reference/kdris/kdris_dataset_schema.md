# KDRIs Dataset Schema

This document defines the CSV contract for the project-owned KDRIs lookup table. The 2025 dataset file now contains approved rows digitized from the official KNS summary PDF with the tracked `2026-03-16` errata version. Do not add guessed or LLM-generated nutrient values.

## Official Source Baseline

- Ministry of Health and Welfare press release: https://www.korea.kr/briefing/pressReleaseView.do?newsId=156737581
- Korean Nutrition Society publication archive: https://www.kns.or.kr/fileroom/FileRoom_view.asp?BoardID=Kdr&idx=167
- Current tracked reference year: `2025`
- Current tracked errata version: `2026-03-16`

## File Layout

Production candidate file:

- `data/nutrition_reference/kdris/kdris_2025.csv`

Development sample fixture:

- `data/nutrition_reference/kdris/kdris_2020.csv`

The 2020 sample fixture remains available only for local algorithm and API shape tests. It must not be used in production.

## Required Columns

| Column | Required | Description |
| --- | --- | --- |
| `nutrient_code` | Yes | Internal nutrient code used by API requests and unit conversion logic. |
| `nutrient_name_ko` | Yes | Korean nutrient display name from the reviewed KDRIs source table. |
| `nutrient_name_en` | Yes | English nutrient display name when available or team-approved translation. |
| `nutrient_group` | Yes | One of the source groups such as `energy_macronutrient`, `vitamin`, or `mineral`. |
| `sex` | Yes | `male`, `female`, or `all`. |
| `age_min_months` | Yes | Inclusive lower age bound in months. |
| `age_max_months` | Yes | Inclusive upper age bound in months. |
| `pregnancy_status` | Yes | `none`, `pregnant`, or `lactating`. |
| `condition_detail` | No | Condition subtype needed to preserve official table semantics, such as trimester-specific pregnancy add-ons, pregnancy/lactation additional amounts, or total-amount rows. |
| `source_variant` | No | Official table variant that should not be flattened into the nutrient code, such as `liquid_water`, `total_water`, `dfe_reference_folic_acid_ul`, or `dual_ul_nicotinic_acid_nicotinamide`. |
| `reference_type` | Yes | KDRIs reference type such as `EER`, `EAR`, `RNI`, `AI`, `AMDR`, `CDRR`, or `UL`. |
| `reference_amount` | Conditional | Scalar reference amount. Required unless a min/max range is used. |
| `reference_amount_min` | Conditional | Lower bound for range-based references such as AMDR. |
| `reference_amount_max` | Conditional | Upper bound for range-based references such as AMDR. |
| `reference_unit` | Yes | Unit used by the reference value. |
| `ul_amount` | No | Tolerable upper intake level amount when KDRIs provides one. |
| `ul_unit` | Conditional | Required when `ul_amount` is present. |
| `ul_amount_secondary` | No | Secondary UL amount when an official cell expresses two UL forms, such as niacin. |
| `ul_unit_secondary` | Conditional | Required when `ul_amount_secondary` is present. |
| `source_id` | Yes | Manifest source id, for example `kns_2025_kdris_publication`. |
| `source_artifact` | Yes | Exact source file or artifact name reviewed. |
| `source_page` | Yes | Page number or page range in the source artifact. |
| `source_table` | Yes | Table number/name from the source artifact. |
| `source_cell` | Yes | Cell or row/column locator within the source table. |
| `errata_version` | Yes | Official errata version applied to this row. Current target: `2026-03-16`. |
| `review_status` | Yes | `draft`, `needs_review`, `approved`, or `rejected`. |
| `reviewer_1` | Conditional | First reviewer identifier. Required for approved rows. |
| `reviewer_2` | Conditional | Second reviewer identifier. Required for approved rows. |
| `reviewed_at` | Conditional | ISO date of final review. Required for approved rows. |

## Validation Rules

- Every production row must have `review_status=approved`.
- Every production row must point to an official 2025 source row and the latest tracked errata version.
- The validator rejects rows containing `sample_fixture` in source fields.
- Age ranges are represented in months to avoid ambiguity for infants and children.
- Age ranges must not overlap for the same `nutrient_code`, `sex`, `pregnancy_status`, `condition_detail`, `source_variant`, and `reference_type`.
- Scalar references use `reference_amount`; range references use both `reference_amount_min` and `reference_amount_max`.
- `ul_unit` must be present whenever `ul_amount` is present.
- `ul_unit_secondary` must be present whenever `ul_amount_secondary` is present.
- The source manifest checksum must match the dataset file before promotion.

## Resolved 2025 Schema Decisions

- Amino acids use component nutrient codes in production rows; `amino_acids_g` remains the official umbrella item in the target inventory.
- Copper uses official `copper_ug` rows without converting to milligrams.
- Folate uses `reference_unit=ug DFE`; folic-acid UL is preserved through `ul_unit=ug folic acid` and `source_variant=dfe_reference_folic_acid_ul`.
- Water keeps `nutrient_code=water_ml` and uses `source_variant=liquid_water` or `source_variant=total_water`.
- Total sugars use `reference_type=policy_limit`, `0-20 % energy`, and `source_variant=narrative_limit`.
- Cholesterol uses `reference_type=policy_limit`, age `19+`, and `0-300 mg`.
- Pregnancy/lactation rows preserve trimester, additional-amount, and total-amount semantics in `condition_detail`.

## Review Workflow

1. Extract candidate rows from the official KDRIs source artifacts.
2. Record `source_artifact`, `source_page`, `source_table`, and `source_cell` for every row.
3. Apply the latest official errata listed by the Korean Nutrition Society.
4. Have two reviewers compare each row against the source artifact.
5. Mark rows `approved` only after both reviewers sign off.
6. Run `python backend/scripts/validate_kdris_dataset.py --require-approved` before changing production settings.
