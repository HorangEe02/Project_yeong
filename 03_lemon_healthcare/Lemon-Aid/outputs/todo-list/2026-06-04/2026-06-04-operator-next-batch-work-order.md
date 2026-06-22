# Operator Next Batch Work Order

## Summary

- `brand_product_review:001`을 다음 operator batch로 고정하는 redacted work order 도구를 구현했습니다.
- 이 도구는 이미 redacted 처리된 3개 artifact만 읽습니다.
  - learning pipeline readiness report
  - operator review batch progress preflight
  - operator review workpack summary
- decision JSONL row payload, 원본 이미지, OCR 원문, provider payload, LLM output, DB record는 읽지 않습니다.

## Implemented Files

- `backend/scripts/build_supplement_operator_next_batch_work_order.py`
  - 입력 artifact schema를 검증합니다.
  - batch progress의 `next_incomplete_batch_key`와 workpack summary의 `next_batch_key`가 다르면 fail-closed 처리합니다.
  - readiness stage, workpack guide, batch JSONL filename, row range, aggregate progress, post-completion gates를 하나의 work order로 출력합니다.
  - 출력 schema는 `supplement-operator-review-next-work-order-v1`입니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_next_batch_work_order.py`
  - 정상 next-batch 선택
  - progress/workpack next batch mismatch fail-closed
  - unsafe artifact fail-closed
  - CLI JSON/Markdown write를 검증합니다.

## Actual Artifact

- Generated:
  - `lemon-supplement-operator-next-batch-work-order.current.json`
  - `lemon-supplement-operator-next-batch-work-order.current.md`
- Actual aggregate:
  - `batch_key`: `brand_product_review:001`
  - `queue_key`: `brand_product_review`
  - `stage_status`: `pending_operator_review`
  - `batch_status`: `pending`
  - `workpack_file_name`: `brand_product_review-001.md`
  - `batch_file_name`: `brand_product_review-001.jsonl`
  - `source_editable_file_name`: `decisions.todo.jsonl`
  - `row_index_start`: 1
  - `row_index_end`: 50
  - `expected_row_count`: 50
  - `valid_row_count`: 0
  - `blank_row_count`: 50
  - `total_blank_row_count`: 808

## Post Completion Gates

After `brand_product_review:001` is manually completed:

1. `reconcile_operator_batch_files`
2. `rerun_operator_batch_progress_preflight`
3. `rerun_brand_decision_preflight`
4. `create_approved_product_import_only_after_blank_invalid_counts_are_zero`

## Verification

```bash
cd backend
.venv/bin/python -m ruff check scripts/build_supplement_operator_next_batch_work_order.py Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_next_batch_work_order.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_next_batch_work_order.py
.venv/bin/python scripts/build_supplement_operator_next_batch_work_order.py --readiness <readiness-report.json> --batch-progress <batch-progress.json> --workpack-summary <workpack-summary.json> --output <next-work-order.json> --markdown-output <next-work-order.md>
```

Additional checks:

- `git diff --check`
- redaction probe against next work order JSON/Markdown

Current expanded verification:

- `ruff check` passed for next-batch work order, readiness report, workpack, batch progress preflight, and their focused unit tests.
- `pytest --no-cov` passed for the same connected flow: 31 tests passed.
- `git diff --check` passed.
- Redaction probe returned no matches for source image paths, local absolute paths, raw OCR/provider payload markers, source refs, or product-folder literals.

## Security Review

- No source images were read.
- No row payloads were read.
- No raw OCR/provider payload was stored.
- No DB write, external OCR call, LLM call, training execution, or YOLO promotion was performed.
- The work order exposes file names and aggregate counts only.

## Official References

- Python argparse: https://docs.python.org/3/library/argparse.html
- Python json: https://docs.python.org/3/library/json.html
- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
