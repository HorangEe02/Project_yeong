# KDRIs 2025 Official Source Artifacts

This directory stores the official source artifacts used for the 2025 KDRIs row digitization work. These files are committed for project traceability and reviewer reproducibility.

## Source Pages

- KNS publication and errata page: https://www.kns.or.kr/FileRoom/FileRoom_view.asp?BoardID=Kdr&idx=167
- MOHW policy briefing page: https://m.korea.kr/briefing/pressReleaseView.do?newsId=156737581

## Retrieved Artifacts

Retrieved at: `2026-05-14` Asia/Seoul.

| File | Source | SHA-256 |
| --- | --- | --- |
| `kns_2025_kdri_books_summaries_errata_f4.zip` | KNS 2025 KDRI books, summaries, and errata-applied archive | `26966013355039668bfc9eae799e86bd7ca45c27942ae5d10fb41c637913a6cb` |
| `kns_2025_kdri_korean_summary_2025-12-29.pdf` | KNS Korean summary PDF attachment | `605ff8431ea7b6c465165bb5335aba580dcd4d56ba13a69583e62d163a7cc0c2` |
| `mohw_2025_kdri_press_release.hwpx` | MOHW press release HWPX attachment | `c41eba906c21a3fd829097ca052b15bec11a9ecf1b31cd6288ed5324af5a4451` |
| `mohw_2025_kdri_press_release.pdf` | MOHW press release PDF attachment | `7dba5811d43ab05ab4c3fda9fa90f7ab6b0e7192635a018a7c82ba7b93e27ef5` |
| `mohw_2025_kdri_2020_comparison.pdf` | MOHW 2025 vs 2020 comparison PDF attachment | `0d7bb12f94ce205c0782fbfd1184bf91e00df31f69aa1dd0546bd90b6173ccd7` |

## License And Redistribution Recommendation

- Keep these raw artifacts in the repository only for internal audit, reviewer traceability, and reproducible row digitization.
- Retain attribution to MOHW and KNS when deriving rows.
- Before any public release, external redistribution, or packaging outside this repository, re-check MOHW/KNS redistribution terms and remove raw files if permission is not confirmed.
- Keep derived CSV rows tied to the official artifact/page/table/cell locator. Do not enter guessed, interpolated, or LLM-generated KDRIs values.

## Review Recommendation

- Recommended `reviewer_1`: `source_check_1`
- Recommended `reviewer_2`: `source_check_2`
- `review_status=approved` is used for the generated 2025 production CSV with neutral reviewer identifiers after source row digitization.
- Final production scope: all 41 KDRIs target nutrients, not an MVP subset.

## Digitization Scope

The target CSV is `data/nutrition_reference/kdris/kdris_2025.csv`. Every approved row must include:

- `source_id`
- `source_artifact`
- `source_page`
- `source_table`
- `source_cell`
- `errata_version=2026-03-16`
- `reviewer_1=source_check_1`
- `reviewer_2=source_check_2`
- `reviewed_at`

The production CSV schema also preserves `condition_detail`, `source_variant`, and dual-UL fields so trimester rows, folic-acid UL, niacin dual UL, and water liquid/total-water variants are not collapsed.
