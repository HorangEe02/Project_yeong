# 2026-06-17 Ingredient Recall 0.85/0.90 Redesign

## Executive Summary

현재 A100 holdout27 structured ROI/full fallback gate 기준 최고 관측값은 다음이다.

| Run | field_macro | field_micro | ingredient_recall | Status |
|---|---:|---:|---:|---|
| b192 + server detector + post-pass + unclip25 | 0.4962 | 0.5455 | 0.5730 | continue_extraction_improvement |
| b192 + server detector + post-pass + unclip30 | 0.5678 | 0.5986 | 0.6023 | continue_extraction_improvement |
| b128/b64 adaptive union, unclip25 | 0.5379 | 0.5874 | 0.6067 | continue_extraction_improvement |
| b128/b64 oracle best, unclip25 | 0.5524 | 0.6014 | 0.6067 | continue_extraction_improvement |

결론은 명확하다. 지금의 recognition 후보 병합과 `unclip` 조정만으로는 `ingredient_recall >= 0.85`에 도달하기 어렵다. 목표 달성을 위해서는 성분표 영역을 놓치지 않도록 입력 자체를 재설계하고, OCR 후보를 여러 관점에서 만든 뒤, structured extractor가 성분명과 함량을 더 공격적으로 복원하되 hallucination을 막는 방식으로 바꿔야 한다.

목표는 두 단계로 둔다.

| Gate | Target | 의미 |
|---|---:|---|
| Promotion candidate | ingredient_recall >= 0.85 | production 후보로 검토 가능 |
| Stretch target | ingredient_recall >= 0.90 | 성분 누락이 사용자 확인 UX 수준으로 충분히 낮아진 상태 |

## Verified Technical Basis

- PaddleOCR 3.x OCR pipeline은 text detection, text recognition, optional orientation/unwarping 모듈로 구성된다. 공식 문서상 detection threshold, box threshold, unclip ratio, side limit, recognition model directory를 runtime parameter로 줄 수 있다.
- `text_det_unclip_ratio`는 text region expansion/dilation coefficient이며 값이 클수록 detection box가 넓어진다. 공식 기본값은 `2.0`이고, Lemon-Aid의 `2.5/3.0/3.5`는 공식 추천값이 아니라 holdout 실험값이다.
- Ultralytics YOLO predict 결과는 crop 저장과 summary 변환을 지원한다. 따라서 section detector의 crop 품질 진단과 hard-case dataset 생성을 자동화할 수 있다.

References:
- PaddleOCR OCR Pipeline: https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html
- Ultralytics YOLO Predict: https://docs.ultralytics.com/modes/predict/
- RapidFuzz fuzz API: https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html
- LayoutParser project: https://layout-parser.github.io/
- LayoutParser paper: https://arxiv.org/abs/2103.15348

## 2026-06-18 A100 Section-Aware v2 Execution Result

사용자 승인 후 `backend/scripts/run_paddleocr_adaptive_structured_eval.py` 개선본을 A100 `G:\lemon-aid\backend\scripts\run_paddleocr_adaptive_structured_eval.py`에 업로드했다. 이후 hardcase 원인 분류 결과를 반영해 `paddleocr_clova_eval.py`의 alias/glyph-confusion post-pass도 A100에 반영하고 같은 locked holdout41 gate를 재실행했다.

검증:

```text
run_paddleocr_adaptive_structured_eval.py local/remote sha256 = 7df7d4b4293b4a9c11515a3d34f8af9a2318229d4bcd270435cf35c0d0400644
paddleocr_clova_eval.py local/remote sha256                    = b7af6a67f68662a6095ec6d3edaec2841fe0a8fe5a987ce14772f6e73e8aa09b
```

실행 조건:

| Item | Value |
|---|---|
| Run ID | `2026-06-18-section-aware-v2-glyphalias-unclip30-b128-b64-holdout41` |
| Bundle | `holdout41-bundle` |
| Split | locked holdout41 |
| Detector profile | `server_detection` |
| `det_unclip_ratio` | `3.0` |
| ROI preset | `section_aware_v2` |
| Primary recognizer | `b128_20260615` |
| Secondary recognizer | `b64_stage3dict_20260612` |
| Raw OCR artifact | not written |

산출물:

```text
G:\lemon-aid\outputs\generated\ocr-eval\2026-06-18-section-aware-v2-glyphalias-unclip30-b128-b64-holdout41
```

결과:

| Strategy | field_macro | field_micro | ingredient_recall | Gate |
|---|---:|---:|---:|---|
| `b128_20260615` | 0.7715 | 0.7544 | 0.7368 | continue_extraction_improvement |
| `b64_stage3dict_20260612` | 0.7801 | 0.7661 | 0.7158 | continue_extraction_improvement |
| `union` | 0.7694 | 0.7544 | 0.7474 | continue_extraction_improvement |
| `evidence_union` | 0.7779 | 0.7661 | 0.7579 | continue_extraction_improvement |
| `oracle_best` | 0.7889 | 0.7778 | 0.7579 | continue_extraction_improvement |

기존 holdout41 `section_aware + unclip30` 대비:

| Strategy | field_macro | field_micro | ingredient_recall |
|---|---:|---:|---:|
| `b128_20260615` | +0.0089 | +0.0117 | +0.0105 |
| `b64_stage3dict_20260612` | +0.0100 | +0.0176 | +0.0211 |
| `union` | +0.0000 | +0.0000 | +0.0106 |
| `evidence_union` | +0.0085 | +0.0117 | +0.0211 |
| `oracle_best` | +0.0134 | +0.0176 | +0.0211 |

Gate 결과:

```text
status=continue_extraction_improvement
fixture_count=41
field_match_macro_met=false
field_match_micro_met=false
ingredient_recall_met=false
leakage_check_passed=true
privacy_review_cleared=true
provider_is_local=true
```

남은 hardcase:

```text
field_lt50=6
field_zero=2
ingredient_all_missed=5
```

`field_zero` 또는 `ingredient_all_missed` fixture ID:

```text
review-ocr-gt-1abbae28290528c00d7d
review-ocr-gt-268022b949153871f953
review-ocr-gt-4fdd024e46acb74839f2
review-ocr-gt-ad1bc7a503d8725df7e7
review-ocr-gt-bd9b5355050d35470c35
```

해석:

- `section_aware_v2`와 evidence merge 강화는 aggregate `ingredient_recall`을 `0.7368 -> 0.7579`로 올렸지만, 목표 `0.85`에는 아직 부족하다.
- `field_zero=2`, `ingredient_all_missed=5`는 그대로 남았다. 따라서 다음 병목은 단순 crop 후보 부족만이 아니라, hardcase별 OCR raw text에 성분명이 실제로 있는지와 structured extractor가 해당 evidence를 metric 후보로 연결하는지의 문제다.
- operator-only raw OCR 임시 분석은 `G:\lemon-aid\outputs\_operator_tmp\raw-ocr-hardcases\2026-06-18-section-aware-v2-unclip30-b128-b64-holdout41-rawdebug`에만 남겼고, raw OCR text/provider payload는 repo에 commit하지 않았다.
- sanitized hardcase 원인 분류 결과는 `metric_or_ocr_confusion_fuzzy_recoverable=1`, `ocr_rec_or_alias_gap=3`, `roi_or_detection_miss=1`이다. 즉, broad fuzzy threshold를 낮추는 방식으로 회수 가능한 케이스는 제한적이며, 최소 4개 fixture는 recognition/alias/GT 보강 또는 ROI detector 개선이 필요하다.
- broad RapidFuzz fuzzy alias 확장은 `Vitamin C`만 보이는 케이스에서 `Vitamin D`까지 후보로 확장되는 false positive를 만들 수 있어 배제했다. 현재 반영된 후처리는 긴 alias에 한정한 deterministic glyph-confusion exact match이다.

## Problem Diagnosis

현재 병목은 단일 원인이 아니다.

1. 성분표 section detection/ROI crop 단계에서 성분표가 완전히 들어오지 않는 fixture가 있다.
2. OCR text detection이 성분명과 수치를 따로 읽거나, 작은 숫자와 단위를 누락한다.
3. OCR 후보를 union해도 `ingredient_all_missed`가 9~11개 남는다.
4. structured extractor는 `성분명 + 숫자 + 단위`가 명확한 경우에는 좋아졌지만, 표 형태, 괄호형 `%DV`, split column, 영어 원문 성분명, 원재료명 선언부까지 아직 충분히 회수하지 못한다.
5. holdout hard-case line crop 재학습은 같은 holdout gate의 production 승격 근거로 쓰면 leakage 위험이 있다. 따라서 stage4는 진단/새 split 설계용으로만 사용하고, production 판단은 분리된 validation/test에서 해야 한다.

## Redesign Principle

`ingredient_recall`을 0.85 이상으로 올리려면 recall-first 구조가 필요하다.

| Layer | 기존 | 재설계 |
|---|---|---|
| ROI | detector bbox 1개 중심 | section별 multi-crop + padded crop + full-image fallback + adjacent panel crop |
| OCR | 단일 detector config | unclip30 기본 + low-threshold recall pass + high-precision pass 병합 |
| Recognition | b192 단일 후보 중심 | b192 primary + b128/b64 secondary + baseline fallback 후보 union |
| Parsing | explicit amount pattern 중심 | table-row, split-column, declaration, bilingual alias, fuzzy ingredient dictionary 병합 |
| Eval | aggregate metric 확인 | failure fixture별 원인 taxonomy와 ablation gate |

## Phase A: Metric And Hardcase Budget

먼저 목표 달성에 필요한 최소 개선량을 고정한다.

현재 `ingredient_recall=0.6023`이면:

| Target | 필요한 절대 상승폭 |
|---|---:|
| 0.85 | +0.2477 |
| 0.90 | +0.2977 |

따라서 작은 post-pass만으로는 부족하다. 다음 정보를 산출해야 한다.

- holdout27 각 fixture의 `ingredient_total`, `ingredient_found`, `missed_count`
- missed ingredient의 normalized name list
- miss 원인 분류: `roi_miss`, `ocr_det_miss`, `ocr_rec_error`, `parser_miss`, `gt_contamination`, `multi_panel_order`
- hard-case fixture에서 raw OCR은 임시 분석 디렉터리에만 저장하고 commit 금지

Acceptance:
- hard-case 9~11개 fixture의 실패 원인이 fixture별로 1차 분류되어야 한다.
- `ingredient_all_missed`를 9개 이하에서 3개 이하로 줄이는 것을 0.85 진입 전제 조건으로 둔다.

## Phase B: Section ROI Recall-First Redesign

성분표가 crop 밖에 있으면 OCR/파서는 복구할 수 없다. ROI 단계는 precision보다 recall을 우선한다.

### B1. Multi-Crop Strategy

각 이미지에서 다음 OCR 입력을 모두 만든다.

1. `ingredient_amounts` detected crop, padding 8~12%
2. `supplement_facts` detected crop, padding 8~12%
3. `other_ingredients` detected crop, padding 8~12%
4. 위 세 섹션의 union bounding box crop
5. section detector confidence가 낮으면 full-image OCR fallback
6. vertical bottle label일 때 center strip crop and lower strip crop

### B2. Detector Gate

새 목표는 mAP가 아니라 downstream ingredient recall이다.

| Detector metric | Gate |
|---|---:|
| ingredient section recall on reviewed boxes | >= 0.95 |
| supplement_facts section recall | >= 0.95 |
| crop contains all expected ingredient text, human spot-check | >= 0.90 |

### B3. Runtime Wiring

Runtime에는 다음 설정을 추가한다.

```text
OCR_ROI_MULTI_CROP_ENABLED=true
OCR_ROI_SECTION_TYPES=ingredient_amounts,supplement_facts,other_ingredients
OCR_ROI_UNION_CROP_ENABLED=true
OCR_ROI_ADJACENT_PANEL_FALLBACK_ENABLED=true
OCR_ROI_PADDING_RATIO=0.10
OCR_ROI_MAX_PADDING_PX=128
```

## Phase C: OCR Candidate Generation Redesign

`unclip30`은 유지하되, 단일 pass가 아니라 recall pass와 precision pass를 병합한다.

| Candidate | Purpose | Config |
|---|---|---|
| primary | 현재 최적 runtime | b192 + server detector + unclip30 |
| recall pass | 작은 숫자/단위 회수 | lower `text_det_box_thresh`, unclip30/35 |
| precision pass | 오탐 억제 | box04 or stricter threshold |
| recognizer fallback | b192 오류 보완 | b128/b64/baseline rec model |
| full-image fallback | ROI miss 보완 | server detector full image |

공식 문서에서 `text_det_thresh`, `text_det_box_thresh`, `text_det_unclip_ratio`, `text_det_limit_side_len`, `text_det_limit_type`, `text_rec_score_thresh`는 확인된다. 단, Lemon-Aid에서 어떤 값이 좋은지는 공식 문서가 아니라 holdout 실험값이다.

Candidate merge는 line-level이 아니라 ingredient-evidence-level로 바꾼다.

```text
OCR lines
  -> normalize
  -> line grouping
  -> ingredient evidence extraction
  -> evidence dedupe
  -> parser candidate merge
```

Acceptance:
- b192 unclip30 단독 대비 `ingredient_recall +0.10` 이상 상승하지 못하면 OCR 후보 병합만으로 0.85 도달 불가로 판단한다.

## Phase D: Structured Extractor Recall-First Redesign

extractor는 아래 케이스를 모두 명시적으로 지원해야 한다.

| Pattern | 예시 | Action |
|---|---|---|
| same line | `비타민C 100 mg 167%` | 기존 유지 |
| split line 2 | `비타민C / 100 mg` | 유지 |
| split line 3 | `비타민C / 100 / mg 167%` | 유지 및 test 확대 |
| table row | `비타민C 100 mg 167` | unit inference는 visible nearby header가 있을 때만 |
| amount-first | `100 mg 비타민C` | name/amount reorder |
| English+Korean | `Vitamin C 100 mg` | dictionary alias로 `비타민C (Vitamin C)` 후보 |
| declaration | `원료명: 비타민C, 아연...` | name-only candidate, review-required |
| mixed facts | `마그네슘 160 mg(51%), 비타민B6 12 mg(800%)` | comma-separated extraction |

중요한 제한:
- 숫자나 단위가 보이지 않으면 amount를 만들지 않는다.
- Gemma4나 dictionary가 amount를 추측하면 안 된다.
- dictionary alias는 name recall에만 사용하고, amount/unit은 OCR visible evidence에서만 온다.

Runtime feature flag:

```text
SUPPLEMENT_INGREDIENT_EVIDENCE_MERGE_ENABLED=true
SUPPLEMENT_INGREDIENT_ALIAS_MATCH_ENABLED=true
SUPPLEMENT_INGREDIENT_TABLE_ROW_PARSE_ENABLED=true
SUPPLEMENT_INGREDIENT_AMOUNT_FIRST_PARSE_ENABLED=true
SUPPLEMENT_INGREDIENT_DECLARATION_NAME_ONLY_ENABLED=true
```

Acceptance:
- parser-only ablation에서 기존 OCR text 기준 `ingredient_recall +0.07` 이상.
- false positive rate를 별도 측정한다. recall만 올리고 잘못된 성분 후보가 폭증하면 production 불가.

## Phase E: Data And Training Redesign

현재 stage4 hardcase dataset은 holdout hard case에서 만들어졌으므로 같은 holdout 승격 근거로 쓰면 안 된다. 새 trainable design은 다음처럼 분리한다.

1. holdout/test hardcases는 원인 분석과 synthetic pattern 설계에만 사용한다.
2. training용 hardcases는 train split 또는 새 operator-reviewed set에서 만든다.
3. hardcase line crop dataset은 실제 OCR miss pattern별로 나눈다.

Dataset buckets:

| Bucket | Source | Purpose |
|---|---|---|
| tiny amount unit | reviewed/train crops | `mg`, `μg`, `%`, 괄호형 단위 |
| Korean ingredient names | reviewed/train crops + synthetic | 성분명 recognition |
| English ingredient names | reviewed/train crops + synthetic | bilingual labels |
| table rows | rendered/synthetic + real crop | row-level recognition |
| vertical/curved label | real crop only | bottle photo robustness |

Training target:

| Stage | Goal |
|---|---|
| stage4 diagnostic | holdout hardcase 원인 재현 여부 확인 |
| stage5 production candidate | train/new-reviewed hardcases로 학습, holdout27 untouched |
| stage6 promotion | disjoint test split에서 0.85/0.90 gate |

## Phase F: Gemma4 Assist As Recall Guardrail

Gemma4는 final answer writer가 아니라 recall guardrail로 둔다.

Trigger:
- OCR ingredient count is 0
- `ingredient_all_missed`-like runtime pattern
- section detector found `ingredient_amounts`, but parser extracted no candidates
- user uploaded multiple images for one supplement and one photo likely contains supplement facts

Input:
- cropped section image
- OCR text lines
- expected JSON schema

Output:
- visible-only ingredient evidence candidates
- confidence
- no guessed amount/unit

Production rule:
- Gemma4 result is candidate evidence only.
- user confirmation 또는 OCR-visible evidence 없이는 DB 저장하지 않는다.

## Decision Gates

| Gate | Command target | Pass condition |
|---|---|---|
| A. unclip30 runtime candidate | structured holdout gate | already improved; keep as candidate |
| B. multi-crop ROI | holdout27 + reviewed crop audit | ingredient_all_missed <= 5 |
| C. OCR candidate merge | holdout27 | ingredient_recall >= 0.70 |
| D. extractor recall pass | holdout27 | ingredient_recall >= 0.78 |
| E. stage5 retrained recognizer | untouched holdout/test | ingredient_recall >= 0.85 |
| F. stretch | untouched holdout/test | ingredient_recall >= 0.90 |

## Immediate Execution Plan

1. Extract unclip30 hardcases.
2. Temporarily dump raw OCR only for the 9 `ingredient_all_missed` fixtures; do not commit.
3. Classify each missed fixture into ROI miss, detection miss, recognition miss, parser miss.
4. Implement multi-crop candidate generation and evidence-level merge behind feature flags.
5. Add extractor patterns for amount-first, comma-separated facts, table-row with visible header, bilingual alias.
6. Re-run holdout27 gate.
7. If `ingredient_recall < 0.75`, stop parser work and prioritize detector/ROI dataset expansion.
8. If `ingredient_recall >= 0.75`, build stage5 hardcase line crop training data from train/new-reviewed fixtures.

## Expected Outcome Boundaries

Do not claim 0.85/0.90 before measurement. The likely path is:

- `0.60 -> 0.70`: multi-crop + unclip30 + OCR candidate merge
- `0.70 -> 0.78`: extractor evidence merge and table/declaration parsing
- `0.78 -> 0.85`: new hardcase dataset and recognition retraining
- `0.85 -> 0.90`: section detector recall and data expansion, not only parser changes

These are target bands, not measured performance claims.
