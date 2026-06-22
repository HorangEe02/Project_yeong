# Supplement Operator Post-Completion Command Plan

Schema: `supplement-operator-post-completion-command-plan-v1`

This plan uses script keys and artifact roles only. It omits shell paths, row payloads, OCR text, provider payloads, source refs, and labels.

- Batch: `brand_product_review:001`
- Queue: `brand_product_review`
- Batch status: `pending`
- Execution allowed: `false`

## Blockers

- `batch_not_complete`
- `blank_rows_remaining`

## Steps

| # | Script key | Purpose | Gate policy |
| ---: | --- | --- | --- |
| 1 | preflight_supplement_operator_review_batch_file | confirm operator local batch is complete | must_pass_before_reconcile |
| 2 | reconcile_supplement_operator_review_batch_files | merge completed batch into reconciled queue copies | no_source_overwrite |
| 3 | preflight_supplement_operator_review_batch_progress | confirm queue level batch progress after reconcile | must_pass_before_queue_preflight |
| 4 | extract_supplement_brand_reviewed_decisions | separate reviewed brand decisions from blank queue stubs | partial_preview_only |
| 5 | preflight_supplement_brand_review_decisions | check strict brand decision readiness | strict_zero_blank_pending_invalid_required |
| 6 | gate_supplement_brand_db_import | gate product import manifest preparation | must_pass_before_product_manifest |
| 7 | apply_supplement_brand_review_decisions | create approved product import manifest | dry_run_or_manifest_only_before_db_gate |
| 8 | import_supplement_taxonomy_approved_manifest | dry run category product and mapping import | dry_run_before_product_db_apply |
| 9 | gate_supplement_product_db_apply | gate reviewed product db apply | must_pass_before_db_apply |
| 10 | verify_supplement_taxonomy_db_import | verify imported categories products and mappings | read_only_after_apply |

## Safety Rules

- `run_local_batch_preflight_first`
- `run_reconcile_before_queue_preflight`
- `never_apply_or_promote_until_strict_gate_passes`
- `keep_raw_ocr_provider_payload_and_local_paths_out_of_outputs`
