# Supplement Operator Review Next Batch Work Order

Schema: `supplement-operator-review-next-work-order-v1`

이 문서는 다음 수동 검수 batch의 redacted 작업 지시서입니다. row id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로를 포함하지 않습니다.

## Next Batch

- Batch: `brand_product_review:001`
- Queue: `brand_product_review`
- Stage: `brand_product_review`
- Stage status: `pending_operator_review`
- Batch status: `pending`
- Workpack guide: `brand_product_review-001.md`
- Batch JSONL: `brand_product_review-001.jsonl`
- Batch review CSV: `brand_product_review-001.review.csv`
- Source editable file: `decisions.todo.jsonl`
- Row range: `1-50`

## Progress

- Expected rows: `50`
- Valid rows: `0`
- Blank rows: `50`
- Pending rows: `0`
- Invalid rows: `0`
- Missing rows: `0`
- Total blank rows across queues: `808`

## Reason Counts

- `blank_decision`: `50`

## Source Bundle Files

- `decisions.todo.jsonl`
- `review-index.html`
- `README.md`
- `review.csv`

## Checklist

- `fill_reviewed_manufacturer`
- `fill_reviewed_product_name`
- `set_approve_or_reject_decision`
- `keep_db_import_attestation_explicit`

## Post Completion Gates

- `reconcile_operator_batch_files`
- `rerun_operator_batch_progress_preflight`
- `extract_reviewed_brand_decisions_for_partial_manifest_preview`
- `rerun_brand_decision_preflight`
- `create_approved_product_import_only_after_blank_invalid_counts_are_zero`

## Rule

preflight 통과 전에는 DB apply, teacher OCR transfer, YOLO dataset promotion, PaddleOCR 학습을 진행하지 않습니다.
