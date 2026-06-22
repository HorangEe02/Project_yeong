# Supplement Operator CSV Apply Check

## Summary

- `brand_product_review:001`의 batch-local CSV 적용 경로를 최신 strict gate 기준으로 다시 정리했다.
- 현재 command checklist는 contact-sheet preflight → CSV triage → `--require-all-reviewed` CSV apply → applied-batch preflight → reconcile 순서로 고정한다.
- 빈 CSV에 대해 `--require-all-reviewed` negative smoke를 실행했고, `status=error`, `error_code=validation_error`, `original_batch_file_modified=false`, `output_row_count=0`으로 실패했다.
- 이전에 생성된 `batches-applied/brand_product_review-001.jsonl`은 blank review 상태에서 만든 historical dry-run 산출물이며, 현재 최신 명령 흐름에서는 수동 review 완료 전 사용하면 안 된다.
- 따라서 brand/product DB import, review-image OCR ground truth, teacher OCR 비교, YOLO bbox dataset, PaddleOCR improvement loop는 계속 operator review 완료 이후 단계다.

## Artifacts

| Artifact | Status |
| --- | --- |
| `outputs/generated/supplement-learning/2026-06-05/operator-review/batches/brand_product_review-001.review.csv` | 50 rows, 50 blank decisions |
| `outputs/generated/supplement-learning/2026-06-05/operator-review/operator-next-command-checklist.md` | starts with contact-sheet preflight and uses `--require-all-reviewed` before applied-batch preflight |
| `outputs/generated/supplement-learning/2026-06-05/operator-review/operator-post-completion-command-plan.md` | `post_completion_execution_allowed=false`, blocked by `batch_not_complete` and `blank_rows_remaining` |
| `outputs/generated/supplement-learning/2026-06-05/operator-review/batches-applied/brand_product_review-001.jsonl` | historical dry-run copy only; not a current reconcile input until CSV review is complete |
| temporary negative smoke output | `status=error`, `validation_error`, `output_row_count=0`, source batch not modified |

## Current Gate Result

| Field | Value |
| --- | ---: |
| Expected rows | 50 |
| Review CSV blank rows | 50 |
| `--require-all-reviewed` blank CSV apply | blocked |
| Negative smoke output rows | 0 |
| Source batch modified | false |
| Post-completion execution allowed | false |
| Ready for reconcile | false |

## Interpretation

The command flow is now connected and stricter: a blank review CSV cannot even
create the applied batch copy used by reconcile. This is the correct fail-closed
state. Blank review rows cannot become DB import manifests, OCR ground-truth
fixtures, YOLO section datasets, or PaddleOCR training candidates.

## Next Action

1. Fill the 50 rows in `brand_product_review-001.review.csv`.
2. Keep row order and row count unchanged.
3. Rerun `operator-next-command-checklist.md` command 1 and confirm contact-sheet alignment.
4. Rerun command 2 to review triage priority and catch partial rows.
5. Run command 3 only after all rows are reviewed; it uses `--require-all-reviewed`.
6. Continue command 4 only when command 3 creates the applied batch copy.
7. Continue reconcile and downstream brand/product gates only after applied-batch preflight reports `ready_for_reconcile=true`.

## Safety

- DB write performed: false.
- OCR provider call performed: false.
- LLM call performed: false.
- Source images read: false.
- Raw OCR text/provider payload/local absolute paths stored in this report: false.

## References

- Python argparse: https://docs.python.org/3/library/argparse.html
- Python csv: https://docs.python.org/3/library/csv.html
- Python json: https://docs.python.org/3/library/json.html
- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
