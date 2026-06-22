# Supplement Operator Next Command Checklist

- Schema: `supplement-operator-next-command-checklist-v1`
- Queue: `brand_product_review`
- Batch: `brand_product_review:001`
- Batch file: `brand_product_review-001.jsonl`
- Status: `ready_after_operator_edits`

## Commands

### 1. preflight_supplement_operator_review_batch_file

Confirm the edited local batch is complete before reconcile.

```sh
backend/.venv/bin/python backend/scripts/preflight_supplement_operator_review_batch_file.py --batch-plan outputs/generated/supplement-learning/2026-06-04/operator-review/operator-review-batch-plan.json --batch-key brand_product_review:001 --batch-file outputs/generated/supplement-learning/2026-06-04/operator-review/batches/brand_product_review-001.jsonl --output outputs/generated/supplement-learning/2026-06-04/operator-review/batches/brand_product_review-001.jsonl.preflight.json --markdown-output outputs/generated/supplement-learning/2026-06-04/operator-review/batches/brand_product_review-001.jsonl.preflight.md
```

- Gate policy: `must_pass_before_reconcile`

### 2. reconcile_supplement_operator_review_batch_files

Merge completed batch files into reconciled queue copies without overwriting sources.

```sh
backend/.venv/bin/python backend/scripts/reconcile_supplement_operator_review_batch_files.py --batch-plan outputs/generated/supplement-learning/2026-06-04/operator-review/operator-review-batch-plan.json --brand-decisions outputs/generated/supplement-learning/2026-06-04/operator-review/brand-product-review-bundle/decisions.todo.jsonl --pii-decisions outputs/generated/supplement-learning/2026-06-04/operator-review/review-pii-screening-bundle/decisions.todo.jsonl --yolo-annotations outputs/generated/supplement-learning/2026-06-04/operator-review/yolo-section-annotation-bundle/annotation.todo.jsonl --batch-dir outputs/generated/supplement-learning/2026-06-04/operator-review/batches --output-dir outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled --summary-output outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/reconcile.summary.json --markdown-output outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/reconcile.summary.md
```

- Gate policy: `no_source_overwrite`

### 3. preflight_supplement_operator_review_batch_progress

Confirm queue-level progress after reconcile.

```sh
backend/.venv/bin/python backend/scripts/preflight_supplement_operator_review_batch_progress.py --batch-plan outputs/generated/supplement-learning/2026-06-04/operator-review/operator-review-batch-plan.json --brand-decisions outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/brand_product_review.reconciled.jsonl --pii-decisions outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/review_pii_screening.reconciled.jsonl --yolo-annotations outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/yolo_section_annotation.reconciled.jsonl --output outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/operator-review-batch-progress.json --markdown-output outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/operator-review-batch-progress.md
```

- Gate policy: `must_pass_before_queue_preflight`

### 4. extract_supplement_brand_reviewed_decisions

Separate reviewed brand decisions from blank queue stubs for preview-only gating.

```sh
backend/.venv/bin/python backend/scripts/extract_supplement_brand_reviewed_decisions.py --taxonomy-staging outputs/todo-list/2026-06-04/2026-06-04-supplement-taxonomy-db-staging.jsonl --decisions outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/brand_product_review.reconciled.jsonl --output outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/brand-product-reviewed.decisions.jsonl --summary outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/brand-product-reviewed.summary.json
```

- Gate policy: `partial_preview_only`

### 5. preflight_supplement_brand_review_decisions

Run strict brand review preflight; this must reach zero blank rows before DB import.

```sh
backend/.venv/bin/python backend/scripts/preflight_supplement_brand_review_decisions.py --taxonomy-staging outputs/todo-list/2026-06-04/2026-06-04-supplement-taxonomy-db-staging.jsonl --decisions outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/brand_product_review.reconciled.jsonl --output outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/brand-product-review-preflight.json --require-all-reviewed
```

- Gate policy: `strict_zero_blank_pending_invalid_required`

### 6. gate_supplement_brand_db_import

Gate approved product import manifest creation after strict brand preflight.

```sh
backend/.venv/bin/python backend/scripts/gate_supplement_brand_db_import.py --brand-decision-preflight outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/brand-product-review-preflight.json --output outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/brand-db-import-gate.json --markdown-output outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/brand-db-import-gate.md
```

- Gate policy: `must_pass_before_product_manifest`

### 7. apply_supplement_brand_review_decisions

Create the approved product import manifest after all brand rows are reviewed.

```sh
backend/.venv/bin/python backend/scripts/apply_supplement_brand_review_decisions.py --taxonomy-staging outputs/todo-list/2026-06-04/2026-06-04-supplement-taxonomy-db-staging.jsonl --decisions outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/brand_product_review.reconciled.jsonl --output outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/approved-product-import-manifest.jsonl --summary outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/approved-product-import-manifest.summary.json --require-all-reviewed
```

- Gate policy: `manifest_only_no_db_write`

## Safety

- Commands are not executed by this generator.
- Paths are repo-relative.
- DB apply is not included in this checklist.
- Source image, OCR text, provider payload, row payload, and product folder literals are not emitted.

## Source Docs

- https://docs.python.org/3/library/argparse.html
- https://docs.python.org/3/library/json.html
- https://www.postgresql.org/docs/current/ddl-constraints.html
- https://supabase.com/docs/guides/database/postgres/row-level-security
