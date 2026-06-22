# Operator Post-Completion Reviewed Extract Flow

## Summary

- `brand_product_review` batch 검수 완료 후 실행해야 하는 후속 단계에 reviewed-only extract를 명시했습니다.
- 목적은 전체 queue에 blank stub이 남은 상태에서 부분 manifest preview를 실행할 때, blank row와 실제 reviewed row를 분리하는 것입니다.
- 이 변경은 strict DB import gate를 완화하지 않습니다.

## Updated Artifacts

- `build_supplement_operator_next_batch_work_order.py`
  - brand post-completion gates에 `extract_reviewed_brand_decisions_for_partial_manifest_preview`를 추가했습니다.
- `build_supplement_operator_review_workpack.py`
  - brand workpack Completion Rule에 reviewed-only extract 실행 단계를 추가했습니다.

## Actual Regenerated Outputs

- Next batch remains: `brand_product_review:001`
- Batch status: `pending`
- Blank rows in next batch: `50`
- Work order post-completion gates now include:
  - `reconcile_operator_batch_files`
  - `rerun_operator_batch_progress_preflight`
  - `extract_reviewed_brand_decisions_for_partial_manifest_preview`
  - `rerun_brand_decision_preflight`
  - `create_approved_product_import_only_after_blank_invalid_counts_are_zero`

## Safety

- Source rows/images were not read by these tools.
- No DB write, OCR provider call, LLM call, or training execution was performed.
- The new reviewed-only step is for partial manifest preview input separation only.
- Product/brand DB import remains blocked until strict brand decision preflight has no blank, invalid, unmatched, missing, or pending rows.

## Verification

- `cd backend && .venv/bin/python -m ruff check scripts/build_supplement_operator_next_batch_work_order.py scripts/build_supplement_operator_review_workpack.py Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_next_batch_work_order.py Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_workpack.py`
- `cd backend && .venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_next_batch_work_order.py Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_workpack.py`
