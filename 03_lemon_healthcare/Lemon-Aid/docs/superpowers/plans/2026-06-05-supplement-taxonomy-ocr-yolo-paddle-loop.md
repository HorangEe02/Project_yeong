# 2026-06-05 — Supplement Taxonomy, OCR, YOLO, PaddleOCR Learning Loop

## Summary

현재 `data/nutrition_reference/crawling-image`는 DB에 바로 넣을 수 있는
`category -> brand -> product` 구조가 아니라, 실제로는
`category -> product candidate -> review/detail-page` 구조다. 각 product
candidate 폴더 이름에 브랜드/제품명/수집 ID가 섞여 있으므로, 43개 영양제 성분
카테고리는 seed 가능하지만 브랜드명과 제품명은 operator review 또는 명시적인
자동검증 게이트가 끝나기 전까지 신뢰 라벨로 취급하지 않는다.

이번 단계의 목표는 세 가지다.

1. 43개 성분 카테고리를 `supplement_categories` 기준 taxonomy로 고정한다.
2. review 이미지를 human ground truth 기반 OCR benchmark로 만들고, CLOVA OCR과
   Google Vision을 teacher provider로 비교한다.
3. detail page 이미지를 YOLO section bbox annotation에 사용하고, PaddleOCR이
   held-out human GT 기준 95% 이상이면 학습 루프를 종료하는 gate를 둔다.

## Verified Current Facts

- Crawling image audit result:
  - Category folder count: `43`
  - Product folder count: `388`
  - Image count: `137,809`
  - Detail-page image count: `5,289`
  - Review image count: `132,520`
  - Non-image file count: `185`
- Product candidate layout result:
  - Product candidates with review directory: `367`
  - Product candidates with detail-page directory: `387`
  - Product candidates with both review and detail-page directories: `366`
  - Product candidates with only one expected source directory: `22`
  - Product candidates missing detail-page directory: `1`
  - Product candidates missing review directory: `21`
- Structure mismatch:
  - Expected by user: `category -> brand -> product/review/detail`
  - Actual current data: `category -> product candidate -> review/detail-page`
  - Product folder names contain brand/product/source-id candidates, but are not safe DB brand labels yet.
- DB migration already defines supplement taxonomy tables:
  - `supplement_categories`
  - `supplement_products`
  - `supplement_product_categories`
- Saved staging output separates:
  - `43` category seed rows: DB-write eligible after DB preflight
  - `388` brand/product candidate rows: review required
- Current DB/operator verification:
  - Active supplement category rows: `43/43`
  - Operator-reviewed brand/product queue: `388/388` valid and complete
  - Auto product rows: `387/387`
  - Auto product-category mappings: `387/387`
  - Stale auto product-category mappings: `0`
  - Product rows still missing a reviewed manufacturer value: `14`
  - Extra active category rows after cleanup: `0`
- Separate food taxonomy verification:
  - TAXO59 catalog/nutrition/link verification rows: `59/59`

## Current Verified State (2026-06-06 KST)

- The supplement category DB contract is verified at `43/43` active rows.
- Brand/product review is no longer the current blocker; the queue is complete
  with `388` valid operator-reviewed rows.
- The current DB automation contract is verified at `387` products and `387`
  product-category mappings, with `0` stale mappings.
- Food taxonomy import verification is complete for the TAXO59-compatible
  catalog path with `59` verified catalog/nutrition/link rows.
- The current blocking operator queue is `review_pii_screening:001`.
- Current blocker batch rows: `50` blank privacy decisions.
- Remaining blank operator rows across queues: `420`.
- Current human-facing operator action: `complete_blank_privacy_decisions`.
- Completed brand/product batch overrides are preserved by the command
  checklist via `--batch-override-dir`; current preserved override count is `8`.

## No-Go Gates Still Active

- Do not run teacher OCR or provider comparison until strict PII preflight has
  `0` blank, pending, or invalid rows.
- Do not materialize OCR ground-truth fixtures until PII-cleared rows and
  human-reviewed expected sections pass the ground-truth manifest preflight.
- Do not promote a YOLO section dataset until bbox review, promotion, and
  section dataset gates pass.
- Do not start or stop a PaddleOCR training loop from training metrics alone.
  The stop condition remains held-out/test human GT text precision, recall, and
  F1 all `>= 0.95`, with leakage checks passed.
- Do not persist or display raw OCR text, provider payloads, source image paths,
  object URIs, owner hashes, or product folder literals in operator-facing
  artifacts.

## Official References

- Ultralytics object detection task documentation:
  https://docs.ultralytics.com/tasks/detect/
- Ultralytics detection dataset format:
  https://docs.ultralytics.com/datasets/detect/
- PaddleOCR OCR pipeline usage:
  https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- PaddleOCR detection training metrics:
  https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html
- PaddleOCR recognition training metrics:
  https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
- Google Cloud Vision OCR:
  https://cloud.google.com/vision/docs/ocr
- NAVER Cloud CLOVA OCR:
  https://api.ncloud-docs.com/docs/en/ai-application-service-ocr

## DB Design

### Supplement Categories

Use the 43 `crawling-image` top-level folder names as supplement category keys.
These rows map to `supplement_categories`.

Rules:

- Category key must be normalized and unique.
- Category display name can preserve the source folder name when safe.
- Category rows are active by default only after import preflight passes.
- Do not infer disease, efficacy, or medical purpose from category folder names.

### Brands And Products

Do not treat current product folder names as trusted brand rows. They are
candidate labels only unless they passed the reviewed DB-import contract or the
separate auto-product verification contract for a clearly marked environment.

Review output should map each product candidate into:

- `manufacturer`
- `display_name`
- `source`
- `source_product_ref`
- `category_key`
- `review_status`

Only reviewed rows can be inserted into:

- `supplement_products`
- `supplement_product_categories`

The latest verified state has two separate contracts:

- operator review contract: `388` valid rows, used as the human-reviewed
  label source;
- automation DB contract: `387` products and `387` mappings, used as the
  verified import state.

Reports and follow-up scripts must name which contract they use. They must not
silently mix the two counts.

### Food Taxonomy

`/Users/yeong/Downloads/food/food_nutrition_taxo59.csv` is mapped into the
existing food taxonomy schema instead of creating a standalone
`food_nutrition` table. The SQL file from that folder performs
`DROP TABLE IF EXISTS food_nutrition`, so it must not be applied directly to
the project database.

The project-compatible target is:

- `food_cuisines`
- `food_courses`
- `food_catalog_items`
- `food_catalog_items.nutrition_reference`

## OCR Benchmark Design

### Ground Truth

Review images may become OCR fixtures only after:

- PII screening is complete.
- Operator marks image as safe for teacher OCR transfer.
- Human-reviewed ground truth is filled.
- Operator-edited ground truth passes the redacted benchmark-readiness preflight.
- Required result-card sections are present before the fixture becomes scoreable.
- Benchmark manifest materializes only private hashed fixture image refs.

Human GT is the only ground truth. CLOVA OCR and Google Vision are teacher
providers, not truth sources.

### Providers

- Teacher providers:
  - `clova_ocr`
  - `google_vision_document`
- Target provider:
  - `paddleocr_local`

All providers must be evaluated against the same fixture split.

### PaddleOCR 95 Percent Stop Criterion

The user-facing target “글씨를 정확하게 95% 이상 추출” is operationalized as:

- held-out split only: `holdout` or `test`
- human reviewed fixtures only
- leakage check passed
- minimum fixture count met
- `normalized_text_precision >= 0.95`
- `normalized_text_recall >= 0.95`
- `normalized_text_f1 >= 0.95`

If any condition fails, the loop continues:

1. Collect error cases.
2. Create PaddleOCR detection/recognition annotation tasks.
3. Materialize PaddleOCR train/val/test dataset.
4. Train and evaluate candidate model.
5. Compare to baseline.
6. Re-run target gate on held-out human GT.

## YOLO Section Bbox Design

Use detail page images for section bbox annotation. Do not use COCO pretrained
YOLO predictions as final supplement section labels.

Allowed supplement section classes:

- `product_identity`
- `supplement_facts`
- `ingredient_amounts`
- `intake_method`
- `precautions`
- `allergen_warning`
- `other_ingredients`
- `functional_claims`

YOLO26 may be used for initialization or smoke tests only. A custom supplement
section dataset is required before trusting section predictions.

YOLO output should be used to crop image regions before OCR:

1. Detect section bbox.
2. Clamp bbox to original image bounds.
3. OCR each crop.
4. If required sections are missing, run full-image OCR fallback.
5. Send only structured section candidates to parser/LLM.

## Implementation Order

1. Keep the existing 43-category seed and 388 brand/product review-gated staging.
2. Add a dedicated PaddleOCR 95% target gate that reads only redacted eval summaries.
3. Add/verify benchmark evaluation summary output compatible with the target gate.
4. Continue operator review for brand/product candidates.
5. Continue PII-safe review image GT creation.
6. Run the redacted OCR ground-truth preflight on operator-edited GT rows.
7. Build the human-reviewed OCR benchmark manifest only after that preflight is ready.
8. Continue detail-page bbox annotation for YOLO section dataset.
9. Assign product-group-safe `train`/`holdout`/`test` splits to human GT fixtures.
10. Run teacher OCR comparison on human GT fixtures.
11. Mine PaddleOCR failures and create annotation tasks.
12. Run PaddleOCR fine-tuning only after dataset split validation.
13. Stop only when the target gate reaches held-out 95% precision/recall/F1.

## Self Review

- Risk: Current folder structure does not contain trusted brand subfolders.
  - Mitigation: The canonical model is `category -> product candidate`; brand/product labels remain review gated, and structure audit now reports review/detail-page directory coverage.
- Risk: Teacher OCR outputs can be wrong.
  - Mitigation: Teacher providers are comparison baselines only; human GT is truth.
- Risk: Data leakage can inflate the 95% target.
  - Mitigation: Stop gate requires held-out/test split and explicit leakage pass.
- Risk: YOLO26 pretrained checkpoints do not know supplement label sections.
  - Mitigation: COCO pretrained is allowed only for initialization, never final labels.
- Risk: PaddleOCR training metrics do not directly measure final OCR extraction quality.
  - Mitigation: Detection/recognition gates remain separate, and final stop criterion uses benchmark text precision/recall/F1.
- Risk: Reviewed and auto-product DB artifacts can be confused.
  - Mitigation: Treat `388` operator-reviewed rows and `387` auto-imported DB
    rows as separate contracts. Reports must name which artifact they use.
- Risk: A readiness-stage next action can become stale after partial
  reconciliation.
  - Mitigation: `operator_next_action` now derives from the current blocker
    batch contents and is preferred by work orders, command checklists, and the
    completion audit.
- Risk: Completed brand/product batch overrides can be lost when regenerating
  the next queue checklist.
  - Mitigation: `build_supplement_operator_next_command_checklist.py` now
    supports `--batch-override-dir` and preserves already-applied override
    files while generating the next PII/YOLO commands.
- Risk: External OCR providers can be invoked before privacy screening is
  complete.
  - Mitigation: Checklist gates still require strict PII preflight before any
    teacher OCR transfer. External provider runs remain explicit opt-in.
- Risk: Teacher OCR commands can be listed before a benchmark manifest and
  split summary prove readiness.
  - Mitigation: The post-completion plan and command checklist now place
    `gate_supplement_ocr_benchmark` after benchmark materialization and
    leakage-safe split assignment, and the generated gate command uses
    `--require-ready-for-teacher-ocr-eval` before provider observations.
- Risk: A generated command checklist can drift from the post-completion plan.
  - Mitigation: The completion audit now verifies both artifacts. Teacher OCR
    remains unsafe unless the plan and checklist agree on benchmark manifest
    creation, split assignment, ready-required benchmark gating, and explicit
    provider opt-in ordering.
- Risk: Optional gate summaries can be stale relative to the current completion
  audit and queue progress.
  - Mitigation: The operator unblock runbook now shows each optional gate's
    consistency status and warning codes, so a stale brand/OCR/YOLO gate cannot
    silently override the current blocker or next operator action.

## Implemented Gate Chain

The first concrete implementation now supports two equivalent safe paths:

- private raw-text path: use when human GT/provider text has already been
  collected in a private local file.
- live provider path: use when provider OCR is executed by the existing
  collector and only redacted observations are persisted.

The implemented scripts are:

1. `build_paddleocr_text_metric_manifest.py`
   - reads a private raw-text manifest containing human GT and OCR text,
   - computes normalized LCS character precision/recall/F1 in memory,
   - emits only redacted metric observations,
   - stores no raw OCR text, provider payload, absolute paths, image bytes, or source refs.
2. `assign_paddleocr_benchmark_splits.py`
   - reads a human-reviewed benchmark fixture manifest,
   - preserves only the redacted `product_dir_hash` as the leakage group,
   - assigns deterministic `train`/`holdout`/`test` splits by product group,
   - verifies a product group does not appear in multiple splits,
   - stores no raw OCR text, provider payload, absolute paths, image bytes, or source refs.
3. `gate_supplement_ocr_benchmark.py`
   - blocks CLOVA/Google Vision/PaddleOCR comparison until strict PII review,
     human-reviewed GT, benchmark manifest creation, and product-group-safe
     split assignment have all passed,
   - requires the benchmark manifest summary to declare the full user-facing
     supplement result-card sections: `ingredient_amounts`, `intake_method`,
     and `precautions`,
   - now requires a split summary before returning `ready_for_teacher_ocr_eval`,
   - keeps PaddleOCR training blocked until the later metric/baseline gates pass.
4. `collect_supplement_ocr_observations.py`
   - runs explicitly opted-in providers,
   - keeps OCR text only in process memory,
   - attaches normalized text precision/recall/F1 to each completed observation
     when human-reviewed expected text or structured fallback is available,
   - persists only redacted observation rows.
5. `merge_paddleocr_text_observations_into_benchmark.py`
   - joins flat redacted collector observations back into benchmark fixture rows,
   - fails on unmatched observations unless explicitly allowed,
   - stores no raw OCR text, provider payload, absolute paths, image bytes, or source refs.
6. `build_paddleocr_text_extraction_eval_summary.py`
   - reads a redacted OCR benchmark manifest,
   - aggregates numeric PaddleOCR observation metrics,
   - requires `holdout` or `test` split,
   - requires human-reviewed expected fixtures,
   - counts missing metric evidence as zero contribution,
   - emits `supplement-paddleocr-text-extraction-eval-summary-v1`.
7. `gate_paddleocr_text_extraction_target.py`
   - reads the eval summary,
   - requires human-reviewed held-out/test fixtures,
   - requires no leakage,
   - requires precision/recall/F1 >= 0.95,
   - prints only redacted status,
   - stores no raw OCR text, provider payload, absolute paths, image bytes, or source refs.
8. `preflight_paddleocr_text_target_chain.py`
   - checks whether the current manifest is ready for the final 95% target gate,
   - verifies supported benchmark/metric row schema, held-out/test split,
     human-reviewed GT, leakage pass, PaddleOCR observation presence, and complete
     numeric precision/recall/F1,
   - prints only counts, check names, status, and safe next-step tokens,
   - stores no raw OCR text, provider payload, absolute paths, image bytes, or source refs.
9. `preflight_supplement_ocr_ground_truth_manifest.py`
   - checks operator-edited OCR ground-truth JSONL before benchmark materialization,
   - requires human-reviewed rows, explicit `ready_for_benchmark_after_review`,
     PII-cleared status, and required result-card section evidence,
   - prints only row counts, issue counts, missing-section counts, and safe status tokens,
   - stores no raw OCR text, provider payload, absolute paths, image bytes, or source refs.
10. `audit_supplement_crawling_image_taxonomy.py`
   - now reports product candidate layout coverage without exposing source paths
     or product folder literals,
   - distinguishes candidates with review, detail-page, both, single-source,
     and missing expected source directories,
   - keeps the user-requested brand-folder mismatch explicit in `observations`.
11. `build_supplement_ocr_benchmark_manifest.py`
   - defaults to requiring `ingredient_amounts` so empty ingredient GT cannot
     become scoreable,
   - supports repeatable `--required-expected-section` for stricter operation
     runs,
   - should be run with `ingredient_amounts`, `intake_method`, and
     `precautions` when the benchmark is intended to validate the full
     user-facing supplement result cards,
   - skips rows that are human-reviewed but not explicitly marked ready for
     benchmark use.
12. `build_supplement_operator_next_batch_work_order.py`
   - reports `operator_next_action` from the current batch state,
   - distinguishes blank privacy decisions from later PII apply steps,
   - keeps row payloads, visible text, image paths, and source literals out of
     the work order.
13. `build_supplement_operator_next_command_checklist.py`
   - accepts `--batch-override-dir`,
   - preserves completed batch override files when generating next-step
     reconcile commands,
   - prefers `operator_next_action` over stale stage-level next-action tokens,
   - emits teacher OCR commands only after benchmark manifest creation, split
     assignment, and a ready-required OCR benchmark gate command.
14. `build_supplement_learning_completion_audit.py`
   - exposes `operator_next_action` in the audit summary,
   - accepts the generated `operator-next-command-checklist` as explicit
     evidence,
   - verifies the teacher OCR fail-closed order across both the
     post-completion plan and command checklist,
   - checks the gate command has `--ground-truth-bundle-summary`,
     `--ground-truth-preflight`, `--benchmark-summary`,
     `--benchmark-split-summary`, and
     `--require-ready-for-teacher-ocr-eval` before provider observations,
   - keeps overall completion blocked until operator review, GT, YOLO dataset,
     and PaddleOCR target evidence are complete.
15. `gate_supplement_ocr_benchmark.py`
   - supports `--require-ready-for-teacher-ocr-eval`,
   - writes the redacted gate summary first,
   - exits non-zero when the gate is still blocked so provider observation
     commands fail closed.
16. `build_supplement_operator_unblock_runbook.py`
   - exposes the current blocker batch and `operator_next_action` from the
     latest completion audit,
   - displays optional gate consistency against current queue progress and
     requirement status,
   - marks stale optional gate evidence instead of letting it silently drive
     the operator's next action.

Command shape:

```bash
cd backend

# Actual-run readiness preflight before spending provider/training time
.venv/bin/python scripts/preflight_paddleocr_text_target_chain.py \
  --benchmark-manifest <redacted-benchmark-or-metric-manifest.jsonl> \
  --output <paddleocr-text-target-chain-preflight.json> \
  --markdown-output <paddleocr-text-target-chain-preflight.md> \
  --eval-split holdout \
  --min-fixtures 30

# Option A: private raw-text path
.venv/bin/python scripts/build_paddleocr_text_metric_manifest.py \
  --private-text-manifest <private-human-gt-and-provider-text.jsonl> \
  --output <redacted-paddleocr-text-metrics.jsonl> \
  --eval-split holdout \
  --leakage-check-passed

.venv/bin/python scripts/build_paddleocr_text_extraction_eval_summary.py \
  --benchmark-manifest <redacted-paddleocr-text-metrics.jsonl> \
  --output <paddleocr-text-eval-summary.json> \
  --eval-split holdout \
  --leakage-check-passed

# Option B: live provider collector path
.venv/bin/python scripts/preflight_supplement_ocr_ground_truth_manifest.py \
  --ground-truth <human-reviewed-ground-truth.jsonl> \
  --output <ground-truth-preflight.json> \
  --markdown-output <ground-truth-preflight.md> \
  --required-expected-section ingredient_amounts \
  --required-expected-section intake_method \
  --required-expected-section precautions \
  --required-expected-section allergen_warnings

.venv/bin/python scripts/build_supplement_ocr_benchmark_manifest.py \
  --candidate-manifest <pii-cleared-review-candidates.jsonl> \
  --ground-truth <human-reviewed-ground-truth.jsonl> \
  --output <human-reviewed-benchmark.jsonl> \
  --source-run-id <run-id> \
  --required-expected-section ingredient_amounts \
  --required-expected-section intake_method \
  --required-expected-section precautions \
  --required-expected-section allergen_warnings

.venv/bin/python scripts/assign_paddleocr_benchmark_splits.py \
  --benchmark-manifest <human-reviewed-benchmark.jsonl> \
  --output <human-reviewed-benchmark-split.jsonl> \
  --summary <human-reviewed-benchmark-split.summary.json> \
  --min-holdout-fixtures 30

.venv/bin/python scripts/gate_supplement_ocr_benchmark.py \
  --pii-preflight <strict-pii-decision-preflight.json> \
  --ground-truth-bundle-summary <ground-truth-review-bundle-summary.json> \
  --benchmark-summary <human-reviewed-benchmark.summary.json> \
  --benchmark-split-summary <human-reviewed-benchmark-split.summary.json> \
  --output <ocr-benchmark-gate.json> \
  --markdown-output <ocr-benchmark-gate.md>

.venv/bin/python scripts/collect_supplement_ocr_observations.py \
  --manifest <human-reviewed-benchmark-split.jsonl> \
  --output-dir <provider-observation-dir> \
  --providers paddleocr_local

.venv/bin/python scripts/merge_paddleocr_text_observations_into_benchmark.py \
  --benchmark-manifest <human-reviewed-benchmark-split.jsonl> \
  --observations <provider-observation-dir>/supplement-ocr-observations.jsonl \
  --output <merged-provider-metric-benchmark.jsonl>

.venv/bin/python scripts/build_paddleocr_text_extraction_eval_summary.py \
  --benchmark-manifest <merged-provider-metric-benchmark.jsonl> \
  --output <paddleocr-text-eval-summary.json> \
  --eval-split holdout \
  --leakage-check-passed

# Final stop gate for both paths
.venv/bin/python scripts/gate_paddleocr_text_extraction_target.py \
  --eval-summary <paddleocr-text-eval-summary.json> \
  --output <paddleocr-target-gate.json> \
  --min-fixtures 30
```

## Actual-Run Readiness Snapshot

Current command:

```bash
cd backend
.venv/bin/python scripts/preflight_paddleocr_text_target_chain.py \
  --benchmark-manifest ../outputs/generated/supplement-learning/2026-06-05/ocr-ground-truth-candidates.jsonl \
  --output ../outputs/generated/supplement-learning/2026-06-05/operator-review/paddleocr-text-target-chain-preflight.json \
  --markdown-output ../outputs/generated/supplement-learning/2026-06-05/operator-review/paddleocr-text-target-chain-preflight.md \
  --eval-split holdout \
  --min-fixtures 30
```

Current redacted result:

- `status`: `blocked_by_candidate_manifest`
- `ready_for_target_gate`: `false`
- `row_count`: `215`
- `scoreable_fixture_count`: `0`
- `schema_version_counts`: `supplement-review-ocr-ground-truth-candidate-v1 = 215`
- `split_counts`: `<missing> = 215`
- `skip_reason_counts`: `candidate_manifest_requires_benchmark_build = 215`,
  `unsupported_row_schema = 215`,
  `split_mismatch_or_missing = 215`

Interpretation:

- The current file is still a redacted ground-truth candidate manifest.
- It is not yet a held-out/test benchmark or metric manifest.
- It is not yet an operator-edited ground-truth preflight artifact.
- The next required steps are:
1. complete PII and manual human GT review,
2. run `preflight_supplement_ocr_ground_truth_manifest.py` on operator-edited GT,
3. build a human-reviewed OCR benchmark manifest,
4. assign product-group-safe `train`/`holdout`/`test` splits,
5. collect or merge PaddleOCR observation metrics,
6. rerun the final target-chain preflight,
7. run the eval summary and 95% target gate only after preflight is ready.

## Next Concrete Change

Run the safe metric chain on actual human-reviewed benchmark fixtures:

1. verify the benchmark manifest has held-out/test split metadata and human-reviewed GT,
2. run `assign_paddleocr_benchmark_splits.py` so product groups cannot leak across splits,
3. run `collect_supplement_ocr_observations.py` for `paddleocr_local`,
4. run the same collector for teacher providers only when their external OCR opt-in gates pass,
5. merge redacted observations into benchmark rows,
6. build the eval summary,
7. run the 95% target gate.

If the target is below 95%, mine the failed PaddleOCR fixtures into annotation
tasks for detection/recognition fine-tuning. If the held-out 95% precision,
recall, and F1 target is met, stop the learning loop.
