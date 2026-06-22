# 2026-06-18 Best Model Recovery And 0.85/0.90 Gate Redesign

## Current State

The current locked holdout41 result is still below the production gate.

Latest operator table to preserve as the current decision baseline:

| Holdout | Best deployable strategy | field_macro | field_micro | ingredient_recall | Status |
|---|---|---:|---:|---:|---|
| holdout27 | `evidence_union` | 0.7096 | 0.7183 | 0.7045 | continue_extraction_improvement |
| holdout41 | `evidence_union` | 0.7813 | 0.7661 | 0.7474 | continue_extraction_improvement |

| Strategy | field_macro | field_micro | ingredient_recall | Status |
|---|---:|---:|---:|---|
| `b128_20260615` | 0.7715 | 0.7544 | 0.7368 | continue_extraction_improvement |
| `b64_stage3dict_20260612` | 0.7801 | 0.7661 | 0.7158 | continue_extraction_improvement |
| `union` | 0.7694 | 0.7544 | 0.7474 | continue_extraction_improvement |
| `evidence_union` | 0.7779 | 0.7661 | 0.7579 | continue_extraction_improvement |
| `oracle_best` | 0.7889 | 0.7778 | 0.7579 | continue_extraction_improvement |

The best measured non-oracle path is `evidence_union`, but `ingredient_recall=0.7579` is not close enough to reach 0.85 by minor threshold tuning alone.

## Recovered Models

| Role | Local path | Promotion status |
|---|---|---|
| Current gate-best runtime candidate | `outputs/generated/supplement-learning/2026-06-18/a100-paddleocr-best-models/b128_20260615_best_accuracy_inference/` | Use as primary candidate. |
| Latest hardcase experiment candidate | `outputs/generated/supplement-learning/2026-06-18/a100-paddleocr-best-models/v6_train_hardcase_b128_task2_best_accuracy_inference/` | Evaluate only; not promoted yet. |

Only inference export files were copied. Raw OCR text, provider payloads, private images, and train/holdout GT were not copied.

## Why The Existing Direction Is Not Enough

Hardcase analysis on `field_zero=2` and `ingredient_all_missed=5` showed:

| Likely cause | Count | Implication |
|---|---:|---|
| `metric_or_ocr_confusion_fuzzy_recoverable` | 1 | Controlled alias/glyph recovery can help only a small part. |
| `ocr_rec_or_alias_gap` | 3 | Recognition/dictionary/alias training must improve. |
| `roi_or_detection_miss` | 1 | At least one fixture still needs better section detection or crop coverage. |

Broad fuzzy matching is not safe. A previous broad RapidFuzz alias pass could turn a visible `Vitamin C` evidence into a false `Vitamin D` candidate. Therefore, fuzzy recovery must be bounded by evidence windows, expected section, amount co-occurrence, and explicit alias groups.

## Redesign Goal

| Gate | Required target |
|---|---:|
| Promotion | `field_macro >= 0.85`, `field_micro >= 0.85`, `ingredient_recall >= 0.85` |
| Stretch | `field_macro >= 0.90`, `field_micro >= 0.90`, `ingredient_recall >= 0.90` |

All measurements must use locked holdout27/holdout41 or a new untouched test split. Train-only hardcases may be used for training, but holdout hardcases must not be used for model fitting.

## Phase 1: Section-Aware ROI v3

The current `section_aware_v2` improves crop coverage but leaves `field_zero=2` and `ingredient_all_missed=5`. The next ROI layer should be detector-led, not heuristic-only.

Implement:

- YOLO section detector outputs for `supplement_facts`, `ingredient_amounts`, `other_ingredients`, `warnings`, and `directions`.
- Per-section crops with padding ratios `0.08`, `0.12`, `0.16` as experimental values only.
- Union crop for adjacent section boxes.
- Left/right column crops for supplement facts tables.
- Lower declaration crop for `Other Ingredients`/원재료명 sections.
- Full-image fallback retained as a recall safety path.

Gate:

- `ingredient_all_missed` must drop from 5 to 2 or less on locked holdout41.
- `field_zero` must drop from 2 to 0 or 1.
- If ROI v3 does not reduce these counts, stop OCR tuning and expand/review section boxes first.

## Phase 2: OCR Multi-Pass Candidate Generation

Use PaddleOCR's official configurable parameters for detection and local model injection:

- `text_recognition_model_dir` for local recognizer inference.
- `text_det_thresh`, `text_det_box_thresh`, `text_det_unclip_ratio` for detector recall/precision sweeps.

Candidate passes:

| Pass | Purpose | Notes |
|---|---|---|
| primary | Stable runtime | `b128_20260615` + `server_detection` + current `unclip30`. |
| hardcase-rec | Recognition alternative | v6 hardcase model, evaluated only as secondary. |
| recall-det | Small/low-contrast text recovery | Lower box threshold and larger unclip are experimental, not official recommended values. |
| precision-det | False-positive control | Higher box threshold; used for conflict resolution. |
| full-image | Safety fallback | Retain current full-image OCR fallback. |

Promotion condition:

- `evidence_union` must improve `ingredient_recall` by at least `+0.05` before more recognizer training is worth running.
- If multi-pass OCR improves line count but not ingredient recall, classify as parser/alias failure instead of adding more OCR passes.

## Phase 3: Ingredient-Evidence-Level Merge

Move from text-line union to ingredient evidence records.

Each evidence record should contain:

```text
ingredient_name_candidate
amount_candidate
unit_candidate
source_variant_id
section_type
row_or_window_id
confidence
accept_reason
reject_reason
```

Accept only when one of the following is true:

- Name and amount appear in the same row/window.
- Name appears in an ingredient declaration line and amount appears in the supplement facts row for the same alias group.
- Bilingual alias is explicit, for example `마그네슘 (Magnesium)`.
- Long alias passes deterministic OCR-glyph normalization and has nearby amount/unit evidence.

Reject when:

- Alias match is fuzzy-only and has no amount evidence.
- Short names such as `C`, `D`, `B6` are matched only by partial string similarity.
- The evidence comes from warning/direction text without dosage context.

## Phase 4: Structured Extractor Pattern Expansion

Add deterministic parser patterns for:

- Two-column supplement facts rows: `name | amount | %DV`.
- Split amount rows: `name` on one line, `100 mg` on the next nearby line.
- Parenthesized source forms: `Magnesium (as magnesium glycinate) 200 mg`.
- Korean-English bilingual forms: `마그네슘 (Magnesium) 200 mg`.
- Other-ingredients declaration forms where ingredients have no dosage, but should count as ingredient presence only if the metric target expects ingredient names without amount.

TODO: confirm whether the evaluation GT expects non-dosage `Other Ingredients` to count toward `ingredient_recall`. If yes, add a separate `ingredient_presence_only` evidence type. If no, keep dosage-bearing ingredient recall separate from excipient/declaration recall.

## Phase 5: Train-Only Hardcase Recognition Stage

The holdout hardcases must stay locked. Build the next recognizer dataset only from:

- train split OCR GT
- reviewed non-holdout line crops
- private-derived synthetic OCR data already approved for A100 transfer
- controlled hard negatives for vitamin/mineral confusions

Do not include holdout27/holdout41 images or GT in training data.

Training targets:

- Ingredient names with OCR confusions: `rn/m`, `l/i/1`, `O/0`, hyphen/space variations.
- Amount-unit compact forms: `100mg`, `100 mg`, `100 mcg`, `1,000 IU`.
- Bilingual labels and Korean transliterations.
- Table-row crops, not only isolated clean text lines.

Promotion gate:

1. Export `best_accuracy/inference`.
2. Run the same locked holdout27 and holdout41 structured ROI/full fallback gate.
3. Promote only if all three metrics improve and `ingredient_all_missed` decreases.

## Phase 6: 0.85/0.90 Decision Gates

| Stage | Required result |
|---|---|
| ROI v3 | `ingredient_all_missed <= 2` on holdout41 |
| OCR multi-pass | `ingredient_recall >= 0.80` before retraining |
| Evidence merge | `field_macro >= 0.82`, `field_micro >= 0.82`, `ingredient_recall >= 0.82` |
| Stage recognizer | all three metrics `>= 0.85` |
| Stretch | all three metrics `>= 0.90` on untouched test split |

If the pipeline reaches `ingredient_recall >= 0.85` but field metrics stay below 0.85, focus on section-specific field routing rather than recognizer training.

## Next Execution Order

1. Evaluate copied v6 inference model as secondary only against locked holdout41.
2. Add ROI v3 section detector crops and per-section crop accounting.
3. Add evidence record output to adaptive eval.
4. Add bounded ingredient evidence merge with reject reasons.
5. Build train-only stage7 hardcase recognizer dataset.
6. Train/export stage7 on A100.
7. Re-run locked holdout27/holdout41 gates.

## 2026-06-18 Implementation Update

Applied locally for the next locked-gate run:

- `backend/scripts/run_paddleocr_adaptive_structured_eval.py`
  - added `--roi-crop-preset section_aware_v3`;
  - added `--ocr-pass-preset recall_precision_v1`;
  - added redacted ingredient evidence records with line hash, section type, window id, and accept reason;
  - kept raw OCR text restricted to `--raw-debug-dir` only.
- `backend/Nutrition-backend/src/services/supplement_parser.py`
  - added table-row ingredient parsing for forms such as `name | amount unit | %DV`;
  - retained review-required fallback semantics and did not fabricate missing amounts.
- `backend/scripts/build_paddleocr_hardcase_line_dataset.py`
  - added `--require-train-source` so stage recognizer datasets fail unless `eval_split=train`.

Measurement still required:

```powershell
python backend\scripts\run_paddleocr_adaptive_structured_eval.py `
  --bundle-dir <locked_holdout_bundle> `
  --splits <locked_splits_jsonl> `
  --output-dir <redacted_output_dir> `
  --primary-name b128_20260615 `
  --primary-rec-model-dir <b128_inference_dir> `
  --secondary-name v6_train_hardcase `
  --secondary-rec-model-dir <v6_inference_dir> `
  --roi-crop-preset section_aware_v3 `
  --ocr-pass-preset recall_precision_v1 `
  --det-unclip-ratio 3.0 `
  --apply
```

TODO: run the same command on locked holdout27 and holdout41 before claiming any
`field_macro`, `field_micro`, or `ingredient_recall` improvement.

## 2026-06-18 Stage7 Mixed-Dict Redesign

The first stage7 attempt used only `v6_train_hardcase_stage6_20260617`. Its
dataset dictionary has 196 rows, while the current `b128_20260615` recognizer
uses the full 1066-row dictionary. PaddleOCR therefore loaded the backbone but
reinitialized recognition heads because the output dimensions did not match.
That run is valid only as a diagnostic hardcase recognizer, not as a deployable
primary model.

New stage7 execution unit:

- preserve the current deployable `b128_20260615` model as the primary runtime
  candidate;
- build a mixed training dataset from `v2` plus train-only hardcase line crops;
- keep the base 1066-row dictionary to preserve the recognition head shape;
- exclude hardcase label rows containing chars absent from the base dictionary
  instead of appending chars and reinitializing the head;
- oversample train-only hardcase rows instead of using holdout27/holdout41;
- initialize from `supplement_rec_crawling_v2_clean_lr1e4_b128_20260615/best_accuracy`;
- train at lower LR so the model adapts to hardcase ingredient evidence without
  forgetting general label text.

Planned A100 run:

```text
dataset=v7_mix_v2_hardcase_stage6_20260618_2332
base=v2
hardcase=v6_train_hardcase_stage6_20260617
hardcase_train_repeat=8
batch=192
epoch=40
lr=0.00002
pretrained=output\supplement_rec_crawling_v2_clean_lr1e4_b128_20260615\best_accuracy
```

Promotion remains locked to the same holdout27/holdout41 structured
ROI/full-fallback gate. Validation `acc` and `norm_edit_dis` from the training
log are not production evidence by themselves.

Actual A100 run started:

```text
dataset=v7_mix_v2_hardcase_stage6_base1066_20260618_2350
run_suffix=v7_mix_base1066_from_b128_lr2e5_b192_20260618_2350
train_rows=103546
val_rows=6876
dict_rows=1066
hardcase_train_added_rows=32768
hardcase_val_added_rows=48
hardcase_train_skipped_unique_rows=4352
hardcase_val_skipped_unique_rows=176
batch=192
epoch=40
lr=0.00002
pretrained=output\supplement_rec_crawling_v2_clean_lr1e4_b128_20260615\best_accuracy
pid=37420
log=G:\lemon-aid\paddleocr_rec_work\full.v7_mix_base1066_from_b128_lr2e5_b192_20260618_2350.combined.log
```

Initial log check:

```text
load pretrain successful from output\supplement_rec_crawling_v2_clean_lr1e4_b128_20260615\best_accuracy
no recognition-head shape mismatch observed in the initial filtered log
latest checked progress=epoch [1/40], global_step 80
```

## References

- PaddleOCR General OCR Pipeline: https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html
- Ultralytics YOLO Predict/Crop Options: https://docs.ultralytics.com/modes/predict/
- RapidFuzz `fuzz.partial_ratio` and `score_cutoff`: https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html
