# Supplement Operator Unblock Runbook

- Schema: `supplement-operator-unblock-runbook-v1`
- Status: `blocked_by_operator_review`
- Completion allowed: `false`
- Next batch: `brand_product_review:001`
- Next batch file: `brand_product_review-001.jsonl`
- Source editable file: `decisions.todo.jsonl`
- Total blank rows: `808`
- Requirements: `3` verified / `3` pending / `5` blocked

## Queue Summary

| Queue | Status | Batches | Blank | Valid | Next batch | Reason counts |
| --- | --- | ---: | ---: | ---: | --- | --- |
| brand_product_review | `pending_operator_review` | 8 | 388 | 0 | brand_product_review:001 | blank_decision=388 |
| review_pii_screening | `pending_operator_review` | 5 | 215 | 0 | review_pii_screening:001 | blank_decision=215 |
| yolo_section_annotation | `pending_operator_review` | 5 | 205 | 0 | yolo_section_annotation:001 | blank_boxes=205 |

## Unblock Sequence

| Order | Queue | Action | Unblocks |
| ---: | --- | --- | --- |
| 1 | brand_product_review | complete_brand_product_human_review | taxonomy product/category DB import |
| 2 | review_pii_screening | complete_review_image_pii_screening | manual OCR ground truth and teacher OCR comparison |
| 3 | yolo_section_annotation | complete_supplement_section_bbox_review | YOLO section dataset and PaddleOCR improvement loop |
| 4 | post_operator_gates | run_post_completion_gates_in_order | remaining requirement gates: brand_product_db_import, taxonomy_db_import_verified, review_image_ground_truth_privacy_gate, manual_ocr_ground_truth, teacher_ocr_paddleocr_comparison, detail_page_yolo_bbox_annotation, section_yolo_dataset_ready, paddleocr_training_loop_ready |

## Current Post-Completion Gates

- `1` `preflight_supplement_operator_review_batch_file`: confirm operator local batch is complete
- `2` `reconcile_supplement_operator_review_batch_files`: merge completed batch into reconciled queue copies
- `3` `preflight_supplement_operator_review_batch_progress`: confirm queue level batch progress after reconcile
- `4` `extract_supplement_brand_reviewed_decisions`: separate reviewed brand decisions from blank queue stubs
- `5` `preflight_supplement_brand_review_decisions`: check strict brand decision readiness
- `6` `gate_supplement_brand_db_import`: gate product import manifest preparation
- `7` `apply_supplement_brand_review_decisions`: create approved product import manifest
- `8` `import_supplement_taxonomy_approved_manifest`: dry run category product and mapping import
- `9` `gate_supplement_product_db_apply`: gate reviewed product db apply
- `10` `verify_supplement_taxonomy_db_import`: verify imported categories products and mappings

## Safety

- Source images read: `false`
- DB write performed: `false`
- OCR provider call performed: `false`
- LLM call performed: `false`
- Training execution performed: `false`
- Raw OCR/provider payload stored: `false`

## Source Docs

- https://docs.ultralytics.com/datasets/detect/
- https://docs.ultralytics.com/tasks/detect/
- https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- https://cloud.google.com/vision/docs/ocr
- https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
- https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
- https://www.postgresql.org/docs/current/ddl-constraints.html
- https://supabase.com/docs/guides/database/postgres/row-level-security
