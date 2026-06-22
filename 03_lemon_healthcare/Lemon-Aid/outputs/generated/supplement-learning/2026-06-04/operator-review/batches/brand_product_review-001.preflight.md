# Supplement Operator Review Batch File Preflight

Schema: `supplement-operator-review-batch-file-preflight-v1`

이 문서는 operator-local batch JSONL 1개가 reconcile 가능한지 aggregate count만 표시합니다.

- Batch: `brand_product_review:001`
- Queue: `brand_product_review`
- Status: `pending`
- Ready for reconcile: `false`
- Batch review CSV status: `matched`
- Batch review CSV rows: `50`
- Batch review CSV matches batch: `true`

## Counts

- Expected rows: `50`
- Actual rows: `50`
- Valid rows: `0`
- Blank rows: `50`
- Pending rows: `0`
- Invalid rows: `0`
- Missing rows: `0`
- Extra rows: `0`

## Reason Counts

- `blank_decision`: `50`

## Next Steps

- `finish_current_batch_edits`
- `keep_row_count_equal_to_batch_plan`
- `rerun_batch_file_preflight`

## Rule

이 preflight가 `complete`여도 reconcile 후 queue-level preflight와 downstream gate를 다시 실행해야 합니다.
