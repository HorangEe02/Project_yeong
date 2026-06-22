# KDRIs 2025 Schema Decisions

Reviewed at: `2026-05-14`

This artifact records the six schema decisions that were blocking production promotion of the 2025 KDRIs rows.

| Issue | Production decision |
| --- | --- |
| Amino acids | Use component nutrient codes for the official amino-acid columns. Keep `amino_acids_g` as the official umbrella item in the target inventory only. |
| Copper unit | Use official `copper_ug` rows without converting to `copper_mg` in the KDRIs CSV. |
| Folate semantics | Use `reference_unit=ug DFE`; encode folic-acid UL as `ul_unit=ug folic acid` and `source_variant=dfe_reference_folic_acid_ul`. |
| Water columns | Keep `nutrient_code=water_ml`; distinguish `source_variant=liquid_water` and `source_variant=total_water`. |
| Total sugars narrative limit | Use `reference_type=policy_limit`, `reference_amount_min=0`, `reference_amount_max=20`, `reference_unit=% energy`, and `source_variant=narrative_limit`. |
| Cholesterol adult recommendation | Use `reference_type=policy_limit`, age `19+`, `reference_amount_min=0`, `reference_amount_max=300`, and `reference_unit=mg`. |

Additional preservation rule: pregnancy/lactation rows keep `condition_detail` values for trimester, additional-amount, and total-amount semantics rather than flattening these cases into the base demographic rows.
