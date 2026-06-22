# OCR 벤치마크 — 필수 섹션 결정 + b32 holdout 차단 분석 (2026-06-13)

> 작성 근거: GT preflight 권위 출력(`preflight_supplement_ocr_ground_truth_manifest.py`). 원본 OCR 텍스트·이미지 미열람(집계만).
> 대상 체인: 운영자 수동 GT(완료) → **벤치마크 게이트 해제** → b32 holdout 재평가 → (det thresh 배선은 완료).

## 0. 현재까지 완료 (이 세션)

- **PII 스크리닝 215건 해소** (이전) + **운영자 수동 GT 완료**: `expected` 215/215 작성, 210 human_reviewed.
- **det thresh 3종 런타임 배선 완료** (커밋 892bceaa): `text_det_thresh`/`box_thresh`/`unclip_ratio` → config + paddle.py. **b32 평가와 독립** — 이미 main 경로에 들어감.

## 1. 차단점 ① — 필수 섹션 방법론 결정 (사용자/팀)

GT preflight 권위 측정값:

| 필수 섹션 집합 | 벤치마크 가능 행 | holdout 최소(30) 충족 | 비고 |
|---|---:|:---:|---|
| §9.0 기본 4종 (ingredient_amounts·intake_method·**precautions·allergen_warnings**) | **1** | ❌ | 평가 불가 |
| 핵심 2종 (ingredient_amounts·intake_method) | **203** | ✅ | 진행 가능 |

섹션별 GT 보유(권위, preflight `missing_required_section_counts` 역산):

- `intake_method`: 210 보유
- `ingredient_amounts`: 203 보유
- `precautions`: **11 보유**
- `allergen_warnings`: **1 보유**

**해석**: `precautions`/`allergen_warnings`는 실제 영양제 라벨 대부분에 **물리적으로 없는 섹션**이다. 이를 필수로 두면 운영자가 완성한 GT의 ~99%가 벤치마크에서 제외된다. field_match 메트릭은 섹션별 채점이므로, 존재하는 섹션만 채점하고 없는 섹션을 필수에서 빼도 메트릭 무결성은 유지된다.

**권고**: 핵심 2종(ingredient_amounts·intake_method)을 필수로, precautions/allergen_warnings는 **존재 시 채점·부재 시 제외**(optional). 단, 이는 §9.0/확정판 가이드의 명시 필수 4종을 바꾸는 것이라 **팀 합의 필요**.

남은 12건(미충족): ingredients 누락 12 = not-ready 12 — 운영자 추가 작성 또는 벤치마크 제외.

## 2. 차단점 ② — b32 holdout 평가 compute (사용자 승인)

필수 섹션 결정으로 벤치마크가 빌드돼도(스크립트 11~13, 외부 호출 없음), **실제 b32 holdout 평가**(러너북 14: `collect_supplement_ocr_observations`)는:

- `Requires external opt-in: True` (CLOVA/Google Vision/PaddleOCR-local).
- b32 recognition 모델은 **A100(155.230.153.222)** 상주, 백엔드 venv에 PaddleOCR 미설치.
- → **A100 원격 실행(사용자 승인) 또는 로컬 PaddleOCR+b32 모델 셋업**이 전제.

즉 b32 holdout 재평가는 ① 방법론 결정 + ② compute 승인 **둘 다** 필요.

## 3. 다음 액션 (결정 후)

- **결정 B(핵심 2종) 채택 시** — Claude가 즉시 가능(외부 호출 0):
  1. `build_supplement_ocr_benchmark_manifest` (--required-expected-section ingredient_amounts intake_method)
  2. `assign_paddleocr_benchmark_splits` (group-by product hash, leakage-safe)
  3. `gate_supplement_ocr_benchmark` → **벤치마크 게이트 해제 확인**
  → 산출물은 `outputs/generated/...`(미커밋 — 사적 이미지 materialize 포함).
- **그 다음(b32 평가)** — A100 승인 후: §9.3 structured eval `--eval-split holdout` (ned≥0.90 + acc 하한), §9.4 rec export·gate.

## 4. 결정 필요 (이 문서의 질문)

1. **필수 섹션 집합**: 핵심 2종(권고) vs §9.0 기본 4종 유지? → **결정: 핵심 2종 채택** (2026-06-13)
2. **b32 holdout compute**: A100 원격 실행 승인 여부 → **승인됨** (2026-06-13)

## 5. 실행 결과 (2026-06-13, 결정 반영 후)

### 5.1 벤치마크 빌드 — ✅ 완료 (외부 호출 0)
- GT preflight(core-2): **203 ready** / 12 not-ready(ingredients 누락).
- benchmark manifest: **203 fixtures**(materialized 203, raw_ocr/payload/absolute_paths 전부 false).
- split: **holdout 41 · test 20 · train 142**, product-group 분할, **leakage_check_passed**, ready_for_holdout_eval=true.

### 5.2 게이트 스크립트 snag (GT 문제 아님 — 별도 수선)
- `gate_supplement_ocr_benchmark.py` → `status: error`. 원인: **GT 번들 요약(`ocr-ground-truth-review-bundle/summary.json`)이 stale 에러본**(2026-06-12 15:05 step-9 재실행 실패가 summary만 덮음, `ground_truth_template_row_count: None`). 게이트가 이 None을 `_non_negative_int`로 읽다 ValueError.
- **GT 자체는 정상**(preflight 203 ready). 게이트는 `--ground-truth-bundle-summary`를 필수로 보지만(omit 시 gt_review_ready=False→BLOCKED_GT), 번들 요약은 step-9 재생성이 운영자 편집 `todo.jsonl`을 덮을 위험이라 **재실행 금지**.
- **수선책(작은 툴링)**: 운영자 편집 `todo.jsonl`을 건드리지 않고 번들 요약만 정상 재생성하는 경로 필요(step-9에 summary-only 모드 없음). 또는 게이트가 preflight를 GT-readiness 권위로 쓰도록 보강.
- **중요**: 이 게이트는 **외부 teacher OCR(CLOVA/Google) 인가용**. b32 holdout 평가(`paddleocr_clova_eval.py`)는 게이트 JSON을 안 쓰고 `--bundle-dir`+`--rec-model-dir`만 필요 → 게이트 snag은 b32 평가를 막지 않음.

### 5.3 A100 상태 (2026-06-13 11:31 KST, 원격 확인)
- **GPU는 `bone_age` 프로젝트 점유**(~48GB, 4 프로세스).
- **PaddleOCR 실험 다수 진행 중**(워처 8+): `v2_clean_p90_fresh_lr2e4_b96`, `v2_clean_p90_stage2(_ckpt)`, `v2_clean_p10`, `v2_low_lr_mix_20260610_stage3`, `lr1e4_b16`·`lr5e5_b16` 변종.
- 최신 종료 run `lr5e5_b16_now10`: early-stop(stale 10/10), best **acc 0.8385 · ned 0.8982**(best_epoch 2) — **아직 b32(ned 0.90132) 미달**. b32가 여전히 best ned.

### 5.4 b32 holdout 평가 — 실행 전 확인 필요 (새 정보 반영)
`paddleocr_clova_eval.py --bundle-dir <holdout 번들> --rec-model-dir <b32> --apply`는 A100에서:
- 벤치마크 번들(사적 라벨 203 + GT)을 **A100로 전송** 필요(per-row `teacher_ocr_allowed`/`external_transfer_allowed` 준수).
- bone_age GPU + 진행 중 PaddleOCR 학습과 **경합**.
→ 상태 확인 승인은 받았으나, 이 무거운 평가를 활성 실험 위에 올리려면 **타이밍/방식 확인 필요**(진행 run 정리 후 vs 지금, 어느 체크포인트=b32 vs v2_clean_p90 최신).

### 5.5 b32 holdout 평가 — ✅ 실행 완료 (2026-06-13, 사용자 "즉시 실행" 승인)

홀드아웃 번들(41행, per-row `external_transfer_allowed=true`·`contains_personal_data=false` 확인 후) A100 전송 → `paddleocr_clova_eval.py --rec-model-dir <inference_b32_holdout> --apply` 실행 → 결과 JSON pull.

산출물: `outputs/generated/.../reconciled/b32-holdout-eval/b32_field_match.json` (schema `paddleocr-clova-eval-v3`).

**확인값 (집계 — 원본 OCR 텍스트 미포함, fixture_id는 해시):**

| 지표 | 값 |
|---|---:|
| field_match_ratio_**macro** | **0.6049** |
| field_match_ratio_**micro** | **0.614** (field_matched_total 105/171) |
| ingredient_recall | 0.6842 (65/95) |
| mean_normalized_text_recall | 0.5597 |
| mean_normalized_text_precision | 0.2832 |
| scored / skipped / failed | 41 / 0 / 0 |
| field_match_threshold | 85.0 |

**구성 확인:**
- `recognition_model_dir` = `...\supplement_rec_..._b32_..._20260611\inference_b32_holdout` → **b32 사용 확정**.
- `recognition_model` 라벨 = `korean_PP-OCRv5_mobile_rec` (프로파일 라벨일 뿐, 실제 인식은 `--rec-model-dir` b32 override).
- `detection_model` = `PP-OCRv5_server_det` (범용 검출기), `det_thresh`/`box_thresh`/`unclip_ratio` 전부 `null`=공식 기본(0.3/0.6/2.0).

**해석:**
- field_match **macro 0.6049 / micro 0.614** 는 0.85 게이트 **미달**. 단, b32 인식 자체는 **val ned 0.9013** — 병목은 인식이 아니라 **범용 섹션 검출기**(전용 section-detector 미배선) + det thresh 미튜닝.
- 기록상 full-image 베이스라인(~0.56) 대비 macro 0.6049로 **소폭 상회**. det thresh 3종은 이미 런타임 배선(892bceaa)됐으므로, **검출기 교체/튜닝**이 다음 레버.

**프라이버시:** 결과 JSON은 집계 지표 + per-image 카운트(field/ingredient 수, 정규화 recall)만. 인식 문자열·라벨 원문 0건. fixture_id는 `review-ocr-gt-<hash>`. → 커밋 가능(미커밋 영역이나 안전).

**정리 완료(2026-06-13):** 로컬 `/tmp/b32_holdout_bundle` 삭제, A100의 `holdout_eval_bundle`(사적 43파일)·`paddleocr_clova_eval_holdout.py`·`inference_b32_holdout`(재export 가능) 삭제. **run dir + `best_accuracy.pdparams`(b32 체크포인트) 보존 확인**.

**다음 레버(이후 작업, 미실행):** ① 전용 supplement section-detector 학습/배선, ② det thresh 스윕(0.3 기준 ±) — 재평가 시 `inference_b32_holdout` 재export 필요(체크포인트로부터 수초).

## 6. 전용 섹션 검출기 배선 — ✅ 코드 완료 (2026-06-13, 학습은 게이트)

### 6.1 설계 결정 (architect panel, 만장일치)
- **결론**: 기존 `enable_vision_classifier` + `vision_classifier_model` 표면이 **이미 전용 섹션 검출기 슬롯**이다. `UltralyticsYoloRunner._validate_model_class_contract`가 로드 모델에 `VISION_SECTION_LABELS`(8종) 노출을 강제(COCO/label-only 거부) → 별도 `supplement_section_*` 표면은 **중복**이라 채택 안 함(2/3 architect 9점, dedicated 옹호자도 self 5.5 + "HIGH redundancy" 인정).
- detector→crop→OCR 경로는 이미 end-to-end 존재: factory `_build_vision_adapter` → `YoloLabelDetector.detect_regions` → `UltralyticsYoloRunner` → 서비스 `crop_before_primary` per-section 크롭.

### 6.2 실제 코드 변경 (배선 보강, 미커밋)
- `config.py`: 상수 `DEFAULT_VISION_CLASSIFIER_MODEL`(=`yolo26n.pt`, stock COCO→로드 시 거부) + 신규 `vision_roi_max_detections`(default 16, ge1/le50) — 섹션 경로에 없던 detection cap(food 경로엔 존재).
- `ultralytics_runner.py`: `UltralyticsYoloRunner`에 `max_detections` 필수 kw(≤0 → ValueError) + `_normalize_prediction_results` 절단. **절단 키는 다운스트림과 동일한 `(label_priority, -confidence)`** — confidence-only면 고우선(priority 0 product_identity) 섹션이 cap에서 탈락 가능(adversarial review에서 적발·수정).
- `yolo.py`: `vision_roi_max_detections` 배선.
- `readiness.py`: `section_roi_model_configured`(bool) — `enable_vision_classifier` ∧ 모델이 stock가 아님. **경로 문자열 미노출**(privacy review ship).
- `.env.example`: `VISION_ROI_MAX_DETECTIONS=16` + 슬롯 의미 주석.
- 테스트: runner 절단(우선순위 dominance)·non-positive 거부, readiness configured/unconfigured, config default. **2049 pass / 1 fail**(fail은 무관한 미커밋 `.mcp.json` 편집).

### 6.3 활성화 방법 (ops/config, 코드 0)
`VISION_CLASSIFIER_MODEL`을 학습된 section 가중치 경로로 지정 + `ENABLE_VISION_CLASSIFIER=true` + `OCR_ROI_PREPROCESSING_POLICY=crop_before_primary`. 운영 활성화는 docs/17 §9 게이트 #2 승인 필요(`validate_runtime_security`).

### 6.4 게이트 (학습 — 이번 변경 범위 밖)
- **새 모델 학습**: `yolo_section_annotation` 큐 **205건 미검토 bbox**(운영자, 사적 이미지) + A100. 도구는 완비(`train_ultralytics_section_detector.py`, `a100_section_detector_spawn_detached.py`, `materialize_…`, `validate_…`).
- **기존 모델**: 2026-06-09 yolo26s 300ep run(305img/1929box) 존재하나 클래스 불균형(other_ingredients train 42/val 1/test 2)으로 운영 적합성 미검증.

## 7. det thresh 스윕 — ✅ 완료 (2026-06-13, 사용자 승인 A100 재전송)

홀드아웃 번들(41행, 전송 전 41/41 external_transfer_allowed·contains_personal_data=False 재확인) A100 재전송 → b32 inference 재export(보존된 best_accuracy.pdparams로부터) → **5개 config 스윕** → 결과 pull → A100/로컬 사적 산출물 정리(체크포인트 보존).

**확인값 (집계만, 원본 OCR 텍스트 0건):**

| config | macro | Δmacro | micro | ingredient_recall | ntext_precision |
|---|---:|---:|---:|---:|---:|
| baseline (기본 0.3/0.6/2.0) | 0.6425 | — | 0.6199 | 0.6421 | 0.3023 |
| text_det_thresh 0.2 | 0.6486 | +0.0061 | 0.6257 | 0.6421 | 0.3033 |
| **text_det_box_thresh 0.4** | **0.6523** | **+0.0098** | **0.6374** | **0.6632** | 0.2796 |
| text_det_unclip_ratio 2.5 | 0.6470 | +0.0045 | 0.6199 | 0.6526 | 0.3023 |
| combined (0.2/0.4/2.5) | 0.6397 | −0.0028 | 0.6257 | 0.6526 | 0.2816 |

**해석:**
- **승자: `text_det_box_thresh=0.4`** — 단일 노브 최대(macro +0.0098, micro +0.0175, ingredient_recall +0.021). 무학습 free lever.
- 개별 노브 모두 소폭 +(thresh 0.2 +0.006, unclip 2.5 +0.0045)이나, **combined는 오버슈트(−0.0028)** — 텍스트를 과다 복원해 precision 하락(0.3023→0.2816). 노브 동시 적용은 역효과.
- 레버 크기 **작음**(사용자 사전 평가와 일치). 그러나 box_thresh=0.4는 일관된 +이고 비용 0.
- **베이스라인 재측정 주의**: 이번 baseline 0.6425는 §5.5 기록(0.6049)보다 높다. 그 사이 운영자가 GT `expected`를 정련 → **신뢰 신호는 cross-run(vs 0.6049)이 아니라 within-sweep Δ**다(동일 GT·동일 스크립트·동일 export로 통제).

**권고**: 런타임에 `LOCAL_OCR_TEXT_DET_BOX_THRESH=0.4` 적용(설정 필드 `local_ocr_text_det_box_thresh`는 892bceaa로 이미 배선됨, 기본 None=PaddleOCR 0.6). 41-image 홀드아웃 근거이므로 코드 기본값 하드변경보다 **문서화된 튜너블 권고**로 팀 채택 결정. 산출물: `outputs/generated/…/b32-holdout-eval/det-thresh-sweep/*.json`(gitignore, 집계만).

