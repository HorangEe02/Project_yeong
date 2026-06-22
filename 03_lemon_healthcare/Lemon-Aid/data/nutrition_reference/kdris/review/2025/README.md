# KDRIs 2025 Digitization Review Scope

Generated at: `2026-05-14` Asia/Seoul.

## Official Sources

- KNS publication and errata page: https://www.kns.or.kr/FileRoom/FileRoom_view.asp?BoardID=Kdr&idx=167
- MOHW policy briefing page: https://m.korea.kr/briefing/pressReleaseView.do?newsId=156737581

## Generated Artifacts

- Target nutrient inventory: `data/nutrition_reference/kdris/review/2025/kdris_2025_target_nutrient_inventory.csv`
- Candidate row skeletons: `data/nutrition_reference/kdris/review/2025/kdris_2025_candidate_rows.csv`
- Candidate blocking issues: `data/nutrition_reference/kdris/review/2025/kdris_2025_candidate_issues.csv`
- Source artifact manifest: `data/nutrition_reference/kdris/review/2025/kdris_2025_source_artifacts.json`
- Summary table text: `data/nutrition_reference/kdris/review/2025/source_text/kns_summary_pages_11_21.txt`
- Errata text: `data/nutrition_reference/kdris/review/2025/source_text/kns_errata_2026_03_16.txt`

## Review Rules

1. Use `data/nutrition_reference/kdris/kdris_2025.csv` only for rows that two independent source checks approve.
2. Keep all unapproved extracted values outside the production CSV.
3. Every production row must record `source_artifact`, `source_page`, `source_table`, `source_cell`, `reviewer_1`, `reviewer_2`, and `reviewed_at`.
4. Apply the `2026-03-16` errata before marking any row approved.
5. Preserve ambiguous table cases for review instead of guessing values.
6. Use neutral reviewer identifiers `source_check_1` and `source_check_2` unless project roles are assigned later.

## Resolved Schema Decisions For Production

- Amino acids: production rows use component nutrient codes while `amino_acids_g` stays as the official umbrella inventory item.
- Copper: production rows use official `copper_ug`; no mg normalization is applied in the KDRIs CSV.
- Folate: production rows use `reference_unit=ug DFE`, `ul_unit=ug folic acid`, and `source_variant=dfe_reference_folic_acid_ul`.
- Water: production rows keep `nutrient_code=water_ml` and distinguish `source_variant=liquid_water` from `source_variant=total_water`.
- Total sugars: production rows use `reference_type=policy_limit`, range `0-20 % energy`, and `source_variant=narrative_limit`.
- Cholesterol: production rows use `reference_type=policy_limit`, range `0-300 mg`, and age scope `19+`.
