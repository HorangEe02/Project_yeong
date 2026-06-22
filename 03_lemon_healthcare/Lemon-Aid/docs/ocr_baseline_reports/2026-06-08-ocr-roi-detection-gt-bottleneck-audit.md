# OCR ROI/Detection/GT Bottleneck Audit

Date: 2026-06-08

Scope: diagnose why the current PaddleOCR learning loop is not approaching the 90%+ target after A100 recognition fine-tuning. This audit intentionally excludes raw OCR text, teacher labels, provider payloads, source paths, and private image contents.

Official references:
- PaddleOCR OCR pipeline supports separate text detection and text recognition models and local fine-tuned model directories: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- PaddleOCR text detection training/eval/export path: https://www.paddleocr.ai/main/en/version2.x/ppocr/model_train/detection.html
- Ultralytics YOLO detection dataset format and training path: https://docs.ultralytics.com/datasets/detect/ and https://docs.ultralytics.com/tasks/detect/

## Finding

The current bottleneck is not primarily the recognition model. It is the combination of:

1. ROI/section detection is not active in runtime or evaluation.
2. The section YOLO dataset is blocked because all 205 bbox annotation rows are still pending human review.
3. The formal 95% gate uses LCS precision/recall/F1 against structured-only GT, which structurally penalizes full-image OCR for reading extra label text.
4. Field-level recall is capped because full-image OCR often misses the specific ingredient/intake regions needed by the benchmark.

Recognition fine-tuning alone has already shown limited or negative movement:

| Run | Scope | Field macro | Field micro | Ingredient found | Holdout LCS precision | Holdout LCS recall | Holdout LCS F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline mobile | 203 | 0.5598 | 0.5524 | 306 / 566 | 0.3057 | 0.4932 | 0.2999 |
| Detection tuned mobile | 203 | 0.5862 | 0.5660 | 305 / 566 | 0.2914 | 0.5465 | 0.3238 |
| A100 v2 clean | 203 | 0.5371 | 0.5262 | 284 / 566 | 0.3018 | 0.5133 | 0.3161 |
| A100 p10 | 203 | 0.5617 | 0.5597 | 316 / 566 | 0.3200 | 0.5287 | 0.3243 |
| CPU fine-tuned | 203 | 0.5679 | 0.5639 | 310 / 566 | 0.2713 | 0.5274 | 0.3059 |

Detection tuning was the best no-training lever by field macro delta. A100 recognition p10 improved ingredient found count, but did not beat detection tuning on field macro or holdout recall.

## Evidence

Benchmark readiness is not the blocker:

- `reconciled/ocr-benchmark-gate.json`: `status=ready_for_teacher_ocr_eval`
- `benchmark_fixture_count=203`
- `benchmark_holdout_fixture_count=52`
- `benchmark_required_expected_sections=["ingredient_amounts", "intake_method"]`
- `benchmark_split_leakage_check_passed=true`
- `pii_strict_clear=true`

Formal target gate trust is also not the blocker:

- Baseline, tuned, A100 v2 clean, A100 p10, and CPU fine-tuned target gates all have trust checks true.
- Every failure is caused by metric checks, not privacy/leakage/schema checks.

The current formal gate is structurally mismatched to structured-only GT:

- `gate_paddleocr_text_extraction_target.py` requires all of `normalized_text_precision`, `normalized_text_recall`, and `normalized_text_f1` to reach the threshold.
- `paddleocr_clova_eval.py` already documents that LCS precision is structurally bounded when reference text is structured-only and PaddleOCR reads extra label text.
- On A100 p10 holdout, the average hypothesis/reference character ratio is 2.53x, median 1.89x, and max 11.16x. Therefore LCS precision stays near 0.32 even when some needed fields are present.

Field-level distribution confirms the recall/ROI issue:

| Run | Field 0% fixtures | Field <50% fixtures | Field >=90% fixtures | Ingredient all-missed fixtures |
|---|---:|---:|---:|---:|
| Baseline mobile | 31 / 203 | 76 / 203 | 49 / 203 | 67 / 203 |
| Detection tuned mobile | 28 / 203 | 63 / 203 | 49 / 203 | 60 / 203 |
| A100 p10 | 30 / 203 | 73 / 203 | 45 / 203 | 68 / 203 |

The detection-tuned run improves 30 fixtures and degrades 21 versus baseline. A100 p10 improves 29 and degrades 29 versus baseline. That pattern is consistent with full-image text region capture being a stronger lever than recognizer-only training.

## ROI/YOLO State

The runtime ROI path exists but is disabled by default:

- `Settings.enable_vision_classifier=false`
- `Settings.ocr_roi_preprocessing_policy=disabled`
- Production validation blocks both `ENABLE_VISION_CLASSIFIER=true` and non-disabled `OCR_ROI_PREPROCESSING_POLICY` without docs/17 gate sign-off.
- `_prepare_primary_ocr_image_inputs()` can OCR multiple detected regions and append a full-image fallback, but only when valid label regions are supplied.

The section detector dataset is not ready:

- `yolo-section-dataset-gate.json`: `status=blocked_by_annotation_review`
- `template_row_count=205`
- `pending_review_row_count=205`
- `valid_accepted_row_count=0`
- `dataset_materialization_ready=false`
- `section_yolo_training_allowed_now=false`
- Required labels include `product_identity`, `supplement_facts`, `ingredient_amounts`, `precautions`, `allergen_warning`, and `intake_method`.

The prior weak-supervision attempt was explicitly judged unsuitable:

- `2026-06-07-yolo26-section-detector-status-and-path.md` records 2,050 detected boxes from a diagnostic attempt, but 1,916 were unclassified, about 93%.
- Non-amount sections such as intake method, allergen warning, product identity, and functional claims had zero usable weak labels in that diagnostic.

## Interpretation

The current 90%+ goal is not reachable by repeatedly training the recognizer on line crops alone unless the target definition is changed to a recognizer-only validation metric. The application-level OCR target needs the image-to-section pipeline:

1. Detect or crop the relevant supplement label sections.
2. OCR those regions with full-image fallback.
3. Evaluate against a GT that matches the intended task:
   - structured extraction target: field match / ingredient recall / intake recall
   - full-text target: full transcription GT for LCS precision/recall/F1

Under the current structured-only GT, requiring LCS precision/F1 >= 0.95 is not a valid stop condition for full-image OCR because extra correctly-read label text lowers precision.

## Recommended Fix Sequence

1. Freeze the current A100 recognizer run as a diagnostic, not as the primary 90% path.
2. Complete the 205 section bbox reviews and promote them through the existing YOLO dataset gate.
3. Materialize and validate the section dataset in Ultralytics YOLO format.
4. Train a custom section detector on A100 and deploy `best.pt` as an artifact, not into git.
5. Run ROI-first PaddleOCR evaluation:
   - `ingredient_amounts` crop
   - `intake_method` crop
   - full-image fallback
   - merged OCR result
6. Add a separate structured extraction target gate based on field-level recall:
   - field_match_ratio
   - ingredient recall
   - intake method recall
   - minimum fixture count and leakage/privacy checks unchanged
7. Keep the current LCS precision/recall/F1 gate only for a future full-transcription GT benchmark.

## Do Not Do

- Do not commit raw OCR text, teacher labels, crop images, provider payloads, or source image paths.
- Do not treat the current LCS 0.95 target as achievable evidence for structured-only GT.
- Do not enable `ENABLE_VISION_CLASSIFIER=true` in production until the section detector dataset, model, and metric gate pass.
