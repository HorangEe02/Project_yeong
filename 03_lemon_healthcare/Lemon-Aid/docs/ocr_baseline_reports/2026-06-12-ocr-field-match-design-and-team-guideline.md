# 2026-06-12 OCR `field_match`/`ingredient_recall` 달성 — 상세 설계·팀 실행 가이드라인 (검증 확정판)

> 목표: `field_match >= 0.85`, `ingredient_recall >= 0.85` (보조: `norm_edit_dis >= 0.90`).
> 이 문서는 [2026-06-12 로드맵 초안](./2026-06-12-ocr-yolo-gemma4-roadmap-guidelines.md)을 **레포 실코드·실측 아티팩트·공식 문서로 전수 검증한 확정판**이다.
> 초안과 달라진 점: 모든 CLI 명령을 실제 스크립트 시그니처로 교정, metric 계산식을 코드 기준으로 명세, 현 실측 상태(검출기 게이트 blocked 포함)를 반영, 공식 문서 확인값/미확인값을 분리.
> 규칙: repo에 기록된 실측 수치만 사실로 적는다. 공식 문서에서 확인 불가한 값은 "실험값으로만 채택 가능"으로 표시한다.

---

## 0. 현재 위치 (실측 스냅샷 — 2026-06-12 기준)

설계에 앞서 팀이 공유해야 하는 현재 상태. 전부 repo 아티팩트 확인값이다.

| 항목 | 실측값 | 출처 |
|---|---|---|
| PaddleOCR mobile 베이스라인 (203장) | field_match macro **0.5598** / micro **0.5524**, ingredient_recall **0.5406** | `outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/paddleocr-baseline-mobile-v3.json` |
| det-tuned full-image (holdout 52장) | macro 0.5401 / micro 0.537, ingredient_recall 0.5205 | `…/reconciled/paddleocr-b64-full-image-det-tuned.holdout52.json` |
| 섹션 검출기 승격 게이트 | **blocked** — mAP50 0.2349 (임계 0.70), ingredient_amounts recall 0.1758, supplement_facts 0.2453, other_ingredients 0.0 | `…/reconciled/a100-section-detector-structured-eval-20260609/yolo26s-300ep-noearly-52g-b070-pyspawn-v2.detector-promotion-gate.json` |
| teacher OCR 벤치마크 게이트 | **blocked_by_pii_screening** — 후보 215행 전부 PII 미결, GT 0행, holdout fixture 0 | `outputs/generated/supplement-learning/2026-06-05/operator-review/ocr-benchmark-gate.md` |
| A100 recognition 후보 (b32, early-stopped) | best epoch 7: acc 0.8432 / **norm_edit_dis 0.90132** (학습 val 기준 — structured gate 미실행) | b32 checkpoint 동봉 `early_stop.*.status.json` |
| A100 진행 중 run (lr1e4_b16 `after_lr5e5`) | epoch 1, best acc 0.8348 / ned 0.8932 (학습 val), early-stop 워처(patience 10) 부착 완료 | A100 `train.log`·`early_stop.*.status.json` (2026-06-12 세션 확인) |
| 과거 실패 사례 | 합성 2-epoch CPU finetune: holdout field_match 0.518 → **0.037** (catastrophic forgetting) | `docs/ocr_baseline_reports/2026-06-07-cpu-finetune-results.md:32` |

**함의**: 목표(0.85/0.85)까지 격차는 field_match 기준 약 +0.30이며, 단일 레버로는 닿지 않는다. 검출기 게이트가 blocked이므로 ROI-scoped 승격 경로는 현재 닫혀 있고, full-image 기준 quick win + recognition fine-tune이 먼저 움직일 수 있는 레버다. teacher 벤치 경로는 PII 스크리닝 215건 해소 전까지 차단이다(§6).

---

## 1. Executive Summary

### 왜 OCR 학습 우선인가

| 근거 | 검증된 현재 상태 |
|---|---|
| 의존성 | `backend/pyproject.toml:23-26` — `ocr-local` extra = `paddlepaddle==3.2.0`, `paddleocr>=3.6,<3.7` (기본 설치/CI 제외, 게이트 통과 전) |
| 런타임 배선 | `config.py:462` `ocr_primary_provider='paddleocr'` 기본. provider/폴백 체인이 `ocr/factory.py`에 구현 완료 |
| 모델 매핑 | `ocr/providers/paddle.py:186-224` — `server_detection`=PP-OCRv5_server_det + korean_PP-OCRv5_mobile_rec. **`server` 프로파일은 rec까지 PP-OCRv5_server_rec로 교체되어 한국어 인식이 깨진다 — 금지** |
| 평가·게이트 | field_match/ingredient_recall 계산기와 승격 게이트 스크립트가 이미 존재 (§2, §9) |

새 VLM 스택 도입보다, 이미 배선된 PaddleOCR 경로에서 작은 텍스트 라인·성분 token recall을 끌어올리는 것이 blast radius가 작고 게이트로 검증 가능하다.

### Gemma4/MLX fine-tune을 주력으로 두지 않는 이유 (공식 문서 재검증 완료)

| 항목 | 검증 결과 |
|---|---|
| MLX 학습 경로 | **mlx-lm의 LoRA/QLoRA는 텍스트 LLM 전용** — 지원 아키텍처 목록에 비전 LLM 없음 ([mlx-lm LORA.md](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)). mlx-vlm의 Gemma 4 파인튜닝 동작 보증·메모리 요구치는 공식 문서에 없음 — 실험값으로만 채택 가능 |
| 공식 비전 FT 경로 | Gemma 비전 파인튜닝 공식 가이드는 HF Transformers + QLoRA (BF16 GPU 전제) — "Gemma4를 MLX로 바로 fine-tuning"은 공식 확인된 경로가 아님 |
| metric 적합성 | 목표 지표는 deterministic 추출 평가와 직결. VLM 학습은 hallucination/schema drift 방어가 별도 과제 |
| 기존 배선 | `OllamaVisionAssistAdapter`(`llm/ollama_vision.py:151`)는 이미 보조/검증 전용으로 설계됨 — primary OCR이 아님 |

### Gemma4를 어디에 보조로 붙일지 (현재 코드 기준)

런타임 호출 조건은 **이미 구현되어 있다** (`supplement_image_analysis.py:1378-1396`):

| 정책 (`MULTIMODAL_OCR_ASSIST_POLICY`) | 호출 조건 |
|---|---|
| `disabled` | 호출 안 함 (기본) |
| `ocr_empty_only` | OCR 결과 없음/빈 텍스트일 때만 |
| `low_confidence` | 빈 텍스트 또는 confidence < **0.80** (`supplement_parser.py:64` `OCR_LOW_CONFIDENCE_THRESHOLD`) |

출력은 `provider='ollama_vision_assist'`, confidence=None으로 반환되고 **final answer로 직접 저장되지 않는다**(§7). "ingredient gap/field missing 시 호출"은 현재 **미구현** — 구현 티켓 대상이다(§7, TODO).

---

## 2. 목표 Metric 정의 (코드 기준 명세)

### Primary gates

| Metric | Gate | 계산 위치 | 정확한 정의 (코드 확인) |
|---|---:|---|---|
| `field_match` | ≥ 0.85 (macro·micro 모두) | `paddleocr_clova_eval.py:153-210` / structured eval | 필드 단위 셋 = product_name, manufacturer, 성분별 display_name, 성분별 "amount unit" 결합 문자열, intake_method. **precautions/allergen/functional_claims는 단위에 미포함**. 정규화(NFKC→소문자→영숫자만) 후 rapidfuzz `partial_ratio >= 85.0`이면 match |
| `ingredient_recall` | ≥ 0.85 | 동일 | GT 성분 display_name(정규화)이 hypothesis 정규화 문자열에 **substring으로 포함**되는 비율 (micro: Σfound/Σtotal) |
| `norm_edit_dis` | ≥ 0.90 | PaddleOCR 자체 eval | **우리 코드가 계산하지 않는다** — `run_paddleocr_eval_from_finetune_plan.py`가 PaddleOCR eval stdout에서 파싱. 값은 유사도(높을수록 좋음) 방향 |

### Secondary metrics

| Metric | 용도 | 주의 |
|---|---|---|
| `acc` | recognition exact match | gate에서 `--min-metric acc=<하한>` 필수 (Requires human decision: 절대 하한) |
| `field_match_ratio_macro` | 이미지별 평균 — 특정 이미지 붕괴 감지 | **macro/micro 모집단 비대칭 존재**: LCS 스킵 이미지(참조 12,000자 초과 등)가 micro에는 포함, macro에는 제외 (`paddleocr_clova_eval.py:431-443`). 게이트 해석 시 scored_images 수 함께 보고 |
| `mean_normalized_text_recall`/`f1` | LCS 기반 텍스트 회수율 | structured eval의 `_merged_hypothesis`는 crop 없는 필드마다 full_text를 반복 삽입해 **precision이 구조적으로 낮게 나올 수 있음**(최대 6회 중복, `evaluate_…:538-559`) — f1 절대값 해석 주의, field_match/recall에는 영향 없음 |
| `roi_merge_stats` | ROI vs fallback 사용 비율 | structured eval 출력 포함 |
| detector mAP50/클래스 recall | 검출기 게이트 | §9.2 |

### full-image vs ROI-scoped 평가 차이

| 방식 | 용도 | 현재 상태 |
|---|---|---|
| full-image | 베이스라인·fallback 품질 | **현재 유일하게 열린 승격 경로** (검출기 blocked) |
| ROI-scoped | section별 text-space 축소 | 검출기 게이트 통과 후 primary 후보 |
| ROI + full fallback | production flow와 동일 | 최종 structured gate (§9.3) |

### holdout/leakage 방지 (구현 확인)

- split 배정은 `assign_paddleocr_benchmark_splits.py`가 **`product_dir_hash` group 단위**로 결정론 배정한다(같은 제품이 split을 넘지 못함). seed `lemon-aid-paddleocr-v1`, holdout 20%/test 10%, 최소 holdout fixture 30.
- teacher pseudo label은 원본 group id를 유지하고 단일 split에만 배정한다.
- holdout은 학습·HP 선택·rule tuning에 사용 금지. holdout 실패를 보고 rule을 고치면 다음 게이트는 새/nested holdout 사용.
- 원본 dataset(`rec_dataset\v2`) 불가침 — sanitized 사본만 사용 (핸드오프 고정 규칙).

---

## 3. 전체 Pipeline 설계 (런타임 배선 기준)

```text
input image → [ENABLE_VISION_CLASSIFIER=true 시] YOLO section detection
  → [OCR_ROI_PREPROCESSING_POLICY=crop_before_primary 시] ROI crop (최대 4개, label_priority·confidence 정렬)
  → full-image 입력은 항상 마지막에 추가 (fallback 내장)
  → PaddleOCR 추출 (다중 입력 결과는 텍스트 병합·confidence 평균)
  → deterministic post-processing → structured extraction
  → [assist policy 충족 시] Gemma4 후보/검증 (저장 금지)
  → user confirmation → redacted metric logging
```

| 단계 | 구현 위치 | 확인된 동작 |
|---|---|---|
| ROI 정책 | `config.py:551-558` | `disabled`(기본)/`detect_only`/`crop_before_primary`. `crop_before_primary`는 `ENABLE_VISION_CLASSIFIER=true` 필요(`config.py:893-897`) — **production은 docs/17 §9 게이트#2 통과 전 차단**(`config.py:984-1017`) |
| ROI crop | `supplement_image_analysis.py:1023-1073` | ROI 후보 최대 **4개**(`MAX_PRIMARY_OCR_ROI_CANDIDATES`), crop 실패 시 원본 폴백 + 경고 `ocr_roi_crop_unavailable` |
| PaddleOCR 전처리 | `config.py:607-622` | `none`/`autocontrast`(기본)/`grayscale_autocontrast`. **`label_enhance` 모드는 미구현** — 도입하려면 구현 티켓 필요 |
| 비전 어시스트 | §1, §7 | empty/low-confidence 정책만 구현. ROI 있으면 crop해 `yolo_roi`로 전달 |
| 로깅 | §9 sanitization | raw OCR/provider payload/절대경로 저장 금지 플래그 출력 |

---

## 4. 단계 A: 학습 전 Quick Wins

### A1. 모델 프로파일

| 설정 | 권장 | 근거 |
|---|---|---|
| `LOCAL_OCR_MODEL_PROFILE` | `server_detection` | det만 server로 올리고 한국어 mobile rec 유지 (`paddle.py:195-224`) |
| 금지 | `server` | rec까지 PP-OCRv5_server_rec로 교체됨 — PP-OCRv5에 한국어 server rec 없음 (공식 모델 목록에서 한국어는 v5/v3 mobile만 확인) |

참고: PaddleOCR 3.7부터 **PP-OCRv6 (tiny/small/medium 체계)** 가 기본이다 ([공식 OCR pipeline 문서](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.en.md)). repo는 v5 모델명을 고정 사용 중이므로 v6 전환은 별도 평가 후보로만 둔다(성능 우열 단정 금지 — v6 지표는 다른 평가셋 기준이라 공식 문서가 직접 비교 불가를 명시).

### A2. Detection 입력 크기 (런타임 배선 완료 항목)

| 설정 | 후보 | 공식/실험 구분 |
|---|---|---|
| `LOCAL_OCR_TEXT_DET_LIMIT_TYPE` | `max` | 공식: `min`=최단변 하한 보장, `max`=최장변 상한 보장 ([3.x OCR pipeline](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html)). 3.x 모듈 API 기본은 None=모델 config 따름 — PP-OCRv5_server_det 예시 출력은 `limit_side_len 736 / limit_type min` |
| `LOCAL_OCR_TEXT_DET_LIMIT_SIDE_LEN` | `1280`, `1536` | **실험 후보값** (공식 단일 추천 없음). holdout sweep 후 채택 |

### A3. Detection threshold (배선 상태 주의)

| 파라미터 | 공식 의미·기본값 | repo 배선 상태 |
|---|---|---|
| `text_det_thresh` | 픽셀 확률 임계, 기본 0.3 | eval 스크립트(`paddleocr_clova_eval.py:236-241`)에만 있음 — **런타임 `_predict_kwargs` 미배선** |
| `text_det_box_thresh` | 박스 평균점수 임계, 기본 0.6 | 동일 (eval만) |
| `text_det_unclip_ratio` | 영역 확장비. 공식 문서 내 기본값 표기가 1.5/2.0으로 **불일치** — 실효값은 모델 config 따름(실험 확인 필요) | 동일 (eval만) |
| `use_dilation` | 2.x 문서에만 존재(기본 False). **3.x 파이프라인/모듈 공식 문서에 미노출** | 런타임·eval 모두 없음 — **공식 확인 불가, 실험값으로만 채택 가능. default 후보 제외** |

✅ 2026-06-13 배선 완료: det thresh 3종(`text_det_thresh`/`text_det_box_thresh`/`text_det_unclip_ratio`)을 `config.py`의 `local_ocr_text_det_thresh`/`_box_thresh`/`_unclip_ratio`(기본 None=파이프라인 기본값 유지) + `paddle.py:_predict_kwargs`에 노출. 기존 `text_det_limit_*` 패턴 미러, 공식 파라미터명·기본값 URL 주석. **튠값 자체는 sweep에서 효과 확인된 값만 env로 설정**(코드는 빈 노출만 제공). 단위 테스트 2건(forward·unset omit).

### A4. 전처리

- 현재 구현: `autocontrast`(기본)·`grayscale_autocontrast`. 초안의 `label_enhance`(CLAHE/denoise/deskew/upscale)는 **미구현** — 채택하려면 ① 구현 → ② 같은 holdout에서 structured+line 지표 동시 비교.
- 금지: 무조건 이진화, 원본 overwrite, raw OCR 디버그 덤프.

### A5. ROI crop padding

- structured eval의 `--crop-pad` 기본 **12px** (`evaluate_…:70`). `max(12px, 0.12*box_h)` 류 동적 패딩은 실험 후보값 — holdout sweep으로만 채택.
- 평가 축: padding별 OCR empty rate, ingredient_recall, field_match.

### A6. 단위 정규화 post-pass

| 대상 | 예 |
|---|---|
| Unicode | NFC/NFKC 정규화 (metric 정규화는 NFKC — 코드 확인) |
| 단위 | `mg/MG/㎎`, `ug/µg/㎍`, IU 통일 token |
| 숫자/괄호 | 전각·콤마·괄호 정규화 |

학습 label 생성용 정규화와 production 추출용 정규화는 분리한다. raw teacher payload는 운영 로그 저장 금지.

### A7. before/after 평가 (실행 가능한 명령으로 교정)

```bash
# 1) PaddleOCR standalone sweep — 실제 CLI: --bundle-dir/--output 필수, dry-run 기본(--apply 시 스코어링)
.venv-paddle/bin/python backend/scripts/paddleocr_clova_eval.py \
  --bundle-dir <sanitized_bundle_dir> \
  --output outputs/generated/ocr-eval/<run-id>/sweep.json \
  --profile server --max-side 1280 \
  --det-box-thresh 0.5 --det-thresh 0.25 --det-unclip-ratio 1.8 \
  --preprocess-mode autocontrast \
  --apply

# 2) Detector ROI + full fallback structured eval — 실제 CLI: --source-bundle/--splits/--output 필수
python backend/scripts/evaluate_detector_roi_full_fallback_structured_extraction.py \
  --source-bundle <sanitized_bundle> --splits <splits.json> --eval-split holdout \
  --predicted-boxes-jsonl <redacted_predicted_boxes.jsonl> \
  --output outputs/generated/ocr-eval/<run-id>/structured.json --apply
```

주의: eval 스크립트의 `--profile server`는 내부적으로 server det + **한국어 mobile rec** 조합이다(`paddleocr_clova_eval.py:62-64`). 런타임 env는 `server_detection`을 쓴다 — 이름이 다르니 혼동 금지. 평가는 `.venv-paddle`(py3.12)에서 실행하고 집계는 메인 `.venv`(py3.13) — 프로세스 분리(2026-06-09 plan §1.5). paddlepaddle 버전 드리프트(pyproject 3.2.0/.venv-paddle 3.3.1/A100 3.2.2)는 게이트 측정 전 한 쌍으로 고정한다.

Requires human decision: target 미달이지만 개선된 quick-win 설정의 default 채택 최소 개선폭.

---

## 5. 단계 B: PaddleOCR Recognition Fine-tuning

### B1. 데이터셋 설계

PaddleOCR 공식 recognition 학습 형식: `SimpleDataSet` + `rec_gt_train.txt`/`rec_gt_test.txt` (`image_path\ttext`), dictionary는 학습 문자를 모두 포함한 UTF-8 파일 ([공식 recognition 학습 문서](https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html)).

| 필드 | 정책 |
|---|---|
| image | line crop만 (원본 이미지 전체 금지) |
| label | human-confirmed 또는 teacher consensus |
| source_group_id | 제품/원본 단위 — split 경계 유지 |
| label_source / privacy_class | human/consensus/synthetic 구분, 보존 범위 flag |

### B2. split 기준 — §2의 leakage 규칙 + 체크리스트

- [ ] 같은 원본 파생 crop/augmentation은 단일 split
- [ ] 같은 제품 SKU는 단일 split (`product_dir_hash` group)
- [ ] consensus 실패 sample은 holdout label 자동 승격 금지
- [ ] holdout 실패 분석 후 rule 수정 시 다음 게이트는 새 holdout

### B3. corpus 혼합 (계획값과 실행값 구분)

| 출처 | 값 | 지위 |
|---|---|---|
| 2026-06-10 todo (계획) | LR piecewise [1e-4, 2e-5], bs=128, 일반:도메인 ratio_list=[1.0, 0.1] | repo 계획값 — 공식 추천 아님 |
| A100 실행 중 run (실측) | lr5e5/lr1e4, b16/b32 계열 (`a100_compact_status_check_fixed.ps1`) | 실험 진행값 — 계획과 다름을 인지하고 결과로 판단 |
| PaddleOCR 공식 | config 키만 공식: `Global.epoch_num`, `Global.eval_batch_step`, `Optimizer.lr.learning_rate`, `Train.loader.batch_size_per_card` ([config 문서](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version2.x/ppocr/blog/config.en.md)) | **이 프로젝트 전용 권장 수치는 공식 문서에 없음** |

경고 사례(실측): 합성 단독 2-epoch CPU finetune은 holdout field_match 0.518→0.037로 붕괴했다 — 일반 corpus 혼합 없는 좁은 분포 학습 금지.

### B4. dictionary

- 기존 korean_dict 유지 우선 — **dict 변경 시 초기 acc=0부터 재학습**(2026-06-10 todo 확인 사항).
- 추가 후보는 라벨에 실재하는 특수문자(`µ ㎍ ㎎ % / ( ) - + .`)만, human-confirmed 기준. OCR 오류 문자를 dict에 넣지 않는다. UTF-8 고정.

### B5. 파라미터 기록 정책

LR/epoch/batch/eval interval/augmentation(RecConAug 제거 여부 포함)은 run metadata로 기록하고, holdout metric으로만 채택 판단한다. 공식 추천값처럼 쓰지 않는다.

### B6. export 후 런타임 연결

```bash
export OCR_PRIMARY_PROVIDER=paddleocr ENABLE_LOCAL_OCR=true
export LOCAL_OCR_MODEL_PROFILE=server_detection
export LOCAL_OCR_TEXT_RECOGNITION_MODEL_DIR=<inference-export-dir>   # checkpoint dir 금지
export LOCAL_OCR_TEXT_DET_LIMIT_TYPE=max LOCAL_OCR_TEXT_DET_LIMIT_SIDE_LEN=1280  # sweep 채택 시
```

`text_recognition_model_dir`는 `paddle.py:178-179`에서 PaddleOCR 초기화에 그대로 전달되고 predictor 캐시 키에 포함된다.

### B7. promotion gate (명령 교정)

```bash
# 실제 CLI: --finetuned-metrics/--baseline-metrics (초안의 --*-summary 아님)
python backend/scripts/gate_paddleocr_finetune_against_baseline.py \
  --task recognition \
  --baseline-metrics <baseline_rec_metrics.json> \
  --finetuned-metrics <finetuned_rec_metrics.json> \
  --min-metric acc=<team_threshold> --min-metric norm_edit_dis=0.90 \
  --output outputs/generated/ocr-eval/<run-id>/recognition-gate.json
```

판정 로직(코드 확인): `absolute_passed`(절대임계) AND `improvement_passed`(baseline+개선폭, 기본 0) 모두 충족해야 promote. `--min-metric`은 태스크 필수 지표(recognition: acc, norm_edit_dis)를 전부 커버해야 한다.

Promotion 체크리스트:
- [ ] `norm_edit_dis >= 0.90` (holdout 재평가 기준 — 학습 val 수치로 승격 금지)
- [ ] `acc` baseline 이상 + 팀 절대 하한 (Requires human decision)
- [ ] structured gate에서 field_match·ingredient_recall 동시 통과
- [ ] gate 출력 sanitization 플래그 통과 — 단, **gate JSON 파일에는 metric 값이 기록된다**(stdout만 값 미출력). "어디에도 값 저장 없음"이 아님에 주의
- [ ] inference export hash·config 기록

---

## 6. 단계 C: 데이터/Teacher Distillation

### C1. CLOVA + Google Vision 합의 라벨링

| 항목 | 정책 |
|---|---|
| 전제 게이트 | **현재 차단**: `ocr-benchmark-gate.md` — PII strict preflight·human GT·fixture·leakage check 통과 전 teacher 벤치 경로 금지 (후보 215행 PII 미결) |
| teacher | CLOVA + Google Cloud Vision (`TEXT_DETECTION`/`DOCUMENT_TEXT_DETECTION` — [공식 OCR 문서](https://cloud.google.com/vision/docs/ocr)) |
| 합의 | normalized text 기준 — epsilon은 Requires human decision |
| 채택 | 양 teacher 합의 + human spot-check 통과 line만 |

Requires human decision: teacher 원문 보존 예외. 현 원칙은 payload/raw text 운영 산출물 저장 금지 — 학습 전용 접근통제 저장소 제한 보존 시 retention/접근자/redaction 별도 승인 필요.

### C2. 합성 데이터

PaddleOCR 공식 synthesis 후보 목록: Text_renderer, SynthText, TextRecognitionDataGenerator, SynthText3D, UnrealText, SynthTIGER ([공식 data synthesis 문서](https://www.paddleocr.ai/latest/en/data_anno_synth/data_synthesis.html)). StyleText는 최신 목록에서 미확인 — 사용 전 재확인. KoTDG는 후보 검토 가능하나 성능 개선 단정 금지. 합성 비중 채택은 real holdout 성능으로만 판단(§B3 경고 사례 참조).

### C3. privacy/storage

- [ ] raw OCR/provider payload를 gate output에 저장 금지 (스크립트 플래그: `raw_ocr_text_stored`/`raw_provider_payload_stored`/`absolute_paths_stored` = false)
- [ ] 원본 이미지 절대경로 저장 금지 (모델 경로는 `.name`만 기록됨 — 코드 확인)
- [ ] teacher payload 기본 저장 금지, 학습 label 최소화
- [ ] TODO(코드 개선): `gate_supplement_section_detector_metrics.py` 실패 요약이 예외 메시지 원문을 저장함(`:275`) — baseline gate처럼 error_type만 남기도록 정리

---

## 7. Gemma4 Vision Assist 설계

### 공식 검증 사항 (2026-06 기준)

- **Gemma 4는 공식 명칭** — 전 사이즈(E2B/E4B/12B Unified/26B A4B/31B) 이미지 입력 지원 ([model card](https://ai.google.dev/gemma/docs/core/model_card_4))
- 이미지 토큰 버짓 70~1120 설정 가능 — **OCR·문서 파싱엔 높은 버짓 권장**, 멀티모달 입력 시 **이미지를 텍스트 앞에** 배치 (model card)
- Gemma 4는 system role 네이티브 지원 명시 — 단 prompt-structure 문서와 상충 표기 존재(실측 확인 필요, unverifiable)
- Ollama: `/api/chat`의 message `images`(base64 배열) + `format`에 JSON Schema 전달 공식 지원 ([API 문서](https://github.com/ollama/ollama/blob/main/docs/api.md), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs))
- 로컬 Gemma용 hallucination 억제 공식 가이드는 **존재하지 않음** — temperature 낮춤+스키마 강제+보이는 텍스트만 지시가 공식 근거의 전부

### 현재 구현 (코드 확인)

| 항목 | 구현 상태 |
|---|---|
| 호출 게이트 | `_should_run_multimodal_fallback` — empty/low-confidence(0.80)만. **ingredient gap/field missing 트리거는 미구현 (TODO 티켓)** |
| 입력 | `/api/chat` + base64 이미지 + Pydantic JSON Schema(`format`) + `think:false` (`ollama_vision.py:403-439`). ROI 있으면 crop해 `source_region='yolo_roi'` |
| 추측 금지 | 시스템 프롬프트가 "보이는 텍스트만, 추론·조언 금지, 안 보이면 빈 값" 강제 + 출력 스키마 `extra='forbid'`, fragment 최대 30 |
| 저장 정책 | assist 결과 confidence=None, raw 미저장(메모리 전용), verification 입력 OCR 텍스트 4,000자 절단·미영속 |
| 어댑터 게이트 | `ENABLE_MULTIMODAL_LLM=true` 필수, production은 docs/17 §9 게이트#1 전까지 차단 (`config.py:984-1017`), local-only LLM 가드 재검증 |

### MLX fine-tuning 후순위 근거 (§1 재확인) + 파일럿 조건

- [ ] 단계 A/B 후에도 target 미달
- [ ] OCR failure taxonomy에서 VLM 복구 가능 케이스 비율 확인
- [ ] 후보/검증 전용 adapter contract 유지
- [ ] **PaddleOCR-only vs +assist를 같은 holdout에서 분리 비교** — 현재 structured eval 스크립트에 assist 경로가 **없음**(grep 0건). 비교 harness 구현이 선행 조건 (TODO)
- [ ] hallucination audit set 통과

---

## 8. PaddleOCR-VL / 대체 VLM 파일럿 (공식 검증 갱신)

| 항목 | 검증값 |
|---|---|
| 최신 버전 | **PaddleOCR-VL-1.6** (PaddleOCR 3.6.0, 2026-05-28; 0.9B VLM: NaViT-style 인코더 + ERNIE-4.5-0.3B). 2단계 구조: PP-DocLayoutV2 → VLM ([논문](https://arxiv.org/abs/2510.14528), [공식 사용 문서](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html)) |
| 서빙 매트릭스 | GPU: PaddlePaddle/Transformers CC≥7.0+CUDA≥11.8, vLLM CC≥8.0+CUDA≥12.6 (A100=CC 8.0 충족). CPU x64: PaddlePaddle/Transformers/llama.cpp만. **Apple Silicon: MLX-VLM 경로 공식 문서화 — 단 M4만 검증, M1~M3 미확인** |
| VRAM | 공식 최소 요구치 **없음**. 논문 벤치 측정값(A100 vLLM 40.1GB 등)은 고처리량 배치 중 사용량 — 우리 환경 소요는 실험값으로만 |
| hallucination | 논문의 'hallucination filtering'은 **학습 데이터 QA 단계** — 런타임 필터 공식 근거 없음. full pipeline 사용 권장(VLM 단독 호출은 공식 경로와 다름) |
| PP-OCR 대비 | 공식 1:1 비교표 없음(비교 대상은 일반 pipeline·MinerU2.5 등) — **우열은 우리 게이트 실측으로만 판단** |

검토 시점·비교 게이트·금지 조건은 초안 §8과 동일하게 유지하되, 비교는 §9.3 structured gate + latency + 메모리 + hallucination audit를 동일 holdout에서 수행한다.

---

## 9. 실행 Runbook (명령 전부 실CLI 교정)

### 9.0 순서 (현 게이트 상태 반영)

| 순서 | 담당 | 작업 | 게이트/통과 기준 |
|---:|---|---|---|
| 0 | 데이터/라벨링 | **PII 스크리닝 215건 해소** → GT/fixture/split 생성 | benchmark gate unblock |
| 1 | QA/eval | full-image 베이스라인 freeze (현 0.5598/0.5406 재확인) | scored_images·privacy 플래그 확인 |
| 2 | OCR 튜닝 | quick-win sweep (§A7) | no regression + 개선폭 기록 |
| 3 | YOLO | 섹션 검출기 재학습 → 게이트 재도전 (**현재 blocked: mAP50 0.2349 vs 0.70**) | §9.2 통과 |
| 4 | OCR 튜닝 | recognition finetune→export→gate (§B7) — A100 b32 후보(val ned 0.90132)부터 holdout 재평가 | ned≥0.90 + acc 하한 |
| 5 | backend | `LOCAL_OCR_TEXT_RECOGNITION_MODEL_DIR` 연결 + 스모크 | runtime smoke + redacted 출력 |
| 6 | VLM | assist 비교 harness 구현 → gated eval | hallucination audit |
| 7 | 팀 리드 | production default 심사 | Gate D |

### 9.2 detector gate

```bash
python backend/scripts/gate_supplement_section_detector_metrics.py \
  --summary <detector_eval_summary.json> \
  --output outputs/generated/ocr-eval/<run-id>/detector-gate.json
```

기본 임계(코드): `min_map50=0.70`, `min_ingredient_recall=0.85`, `min_supplement_facts_recall=0.85`, `min_key_class_recall=0.65`, KEY_CLASS 8종 전부 존재 필수.

YOLO 학습 참고(공식): 기본 epochs=100/imgsz=640/batch=16/patience=100, 작은 객체 데이터셋은 imgsz 1280 학습 권장, **val은 conf=0.001 기준**(추론 기본 0.25로 mAP 측정 금지), 클래스당 이미지 1.5k+/인스턴스 10k+ 권장 ([train](https://docs.ultralytics.com/modes/train/)/[val](https://docs.ultralytics.com/modes/val/)/[tips](https://docs.ultralytics.com/yolov5/tutorials/tips_for_best_training_results/)). SAHI 타일 추론은 작은 객체 보조 후보 ([guide](https://docs.ultralytics.com/guides/sahi-tiled-inference/)).

**Requires human decision (라이선스)**: ultralytics는 AGPL-3.0(Enterprise 듀얼). 공식 라이선스 페이지는 네트워크 서비스 제공 시 파생물 소스 공개 의무를 명시하고, 비공개 상용 배포에는 Enterprise 라이선스가 필요하다고 안내한다 ([license](https://www.ultralytics.com/license)). production 백엔드 채택 전 법무 확인 필요.

### 9.3 ROI/full fallback structured eval

§A7의 ② 명령 사용 (`--source-bundle/--splits/--output` 필수, `--eval-split holdout`, `--imgsz 1280 --conf 0.05 --iou 0.7 --crop-pad 12` 기본). 산출 요건:

- [ ] `field_match_ratio_macro/micro`, `ingredient_recall`, `roi_merge_stats` 포함
- [ ] `raw_ocr_text_stored=false`, `raw_provider_payload_stored=false`, `absolute_paths_stored=false`
- [ ] scored vs skipped 이미지 수 기록 (macro/micro 모집단 차이 해석용)

### 9.4 recognition export & gate — §B7 명령 사용

### 9.5 Gemma assist gated eval — **harness 구현 선행** (현 스크립트는 assist 미평가, env만 켜도 효과 없음). 구현 후 PaddleOCR-only와 동일 holdout 분리 비교.

### 9.6 rollback/fallback

| 실패 | 조치 |
|---|---|
| detector gate fail | 이전 detector 유지 + full-image fallback (현 상태) |
| quick-win regression | env 기본값 원복, sweep 결과만 보관 |
| rec gate fail | `LOCAL_OCR_TEXT_RECOGNITION_MODEL_DIR` unset → 기본 korean mobile rec |
| assist hallucination | `MULTIMODAL_OCR_ASSIST_POLICY=disabled` |
| production regression | `OCR_PRIMARY_PROVIDER` 원복, PaddleOCR shadow 강등 |

---

## 10. 팀 작업 분장

| 역할 | 책임 | 산출물 | 당면 과제 (§9.0) |
|---|---|---|---|
| YOLO | 섹션 검출기 재학습·게이트 | weights, redacted summary, boxes JSONL | mAP50 0.2349→0.70 격차 해소 (데이터 라벨 정밀도부터) |
| OCR 튜닝 | sweep, finetune, export, gate | sweep/gate JSON, inference dir | det thresh 3종 런타임 배선 티켓, b32 holdout 재평가 |
| 데이터/라벨링 | PII 스크리닝, GT, split, consensus | sanitized manifest, split report | **PII 215건 해소가 최우선 차단 해제** |
| backend | env wiring, assist adapter, 비교 harness | config PR, smoke 출력 | label_enhance·gap-trigger·assist-harness 구현 티켓 |
| QA/eval | holdout freeze, 게이트 실행, privacy 검증 | structured report, 결정 로그 | macro/micro 모집단 기록 표준화 |

---

## 11. 의사결정 Gate

### Gate A: Quick Wins 채택
- no regression(field_match·ingredient_recall) + OCR empty rate 감소 + latency/memory 예산 내.
- 공식 확인 불가 파라미터(use_dilation 등)는 experiment only.
- Requires human decision: target 미달 시 default 채택 최소 개선폭.

### Gate B: fine-tuned model promotion
- holdout 기준 `norm_edit_dis>=0.90` AND baseline 대비 acc·ned 개선 AND structured gate 통과.
- 학습 val 수치(예: b32 0.90132)로 승격 금지 — holdout 재평가 필수.
- checkpoint 직결 금지(inference export만).

### Gate C: Gemma assist enable
- 비교 harness 구현 + 같은 holdout에서 assist on/off 분리 측정 + hallucination audit 통과 + schema 위반 0 + final-answer 직접 저장 경로 부재 확인.

### Gate D: production default 전환 (전부 충족)
- [ ] detector gate 통과
- [ ] `field_match_ratio_macro>=0.85` AND `micro>=0.85`
- [ ] `ingredient_recall>=0.85`
- [ ] (rec finetune 사용 시) `norm_edit_dis>=0.90`
- [ ] privacy 플래그 전부 pass
- [ ] rollback env 문서화 + shadow/canary 무회귀
- [ ] production config 게이트 해소: `ENABLE_VISION_CLASSIFIER`·`OCR_ROI_PREPROCESSING_POLICY`는 docs/17 §9 게이트#2, multimodal은 게이트#1 (`config.py:984-1017`)

---

## References (공식 문서 — 2026-06-12 검증)

| 주제 | URL |
|---|---|
| PaddleOCR 릴리스 (3.7.0 / PP-OCRv6) | https://github.com/PaddlePaddle/PaddleOCR/releases |
| PaddleOCR 3.x OCR pipeline (det 파라미터·모델 목록) | https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html · https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.en.md |
| PaddleOCR 3.x text detection module (predict 파라미터 기본 None) | https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/text_detection.en.md |
| PaddleOCR 2.x 추론 인자 (use_dilation 등 레거시) | https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version2.x/ppocr/blog/inference_args.en.md |
| PaddleOCR recognition 학습·config | https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html · https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version2.x/ppocr/blog/config.en.md |
| PaddleOCR data synthesis | https://www.paddleocr.ai/latest/en/data_anno_synth/data_synthesis.html |
| Ultralytics train/val/predict/tips/SAHI | https://docs.ultralytics.com/modes/train/ · https://docs.ultralytics.com/modes/val/ · https://docs.ultralytics.com/modes/predict/ · https://docs.ultralytics.com/yolov5/tutorials/tips_for_best_training_results/ · https://docs.ultralytics.com/guides/sahi-tiled-inference/ |
| Ultralytics 라이선스 | https://www.ultralytics.com/license · https://www.gnu.org/licenses/agpl-3.0.en.html |
| Gemma 4 (공식) | https://ai.google.dev/gemma/docs · https://ai.google.dev/gemma/docs/core/model_card_4 · https://ai.google.dev/gemma/docs/releases · https://ai.google.dev/gemma/docs/core/prompt-structure |
| Gemma 비전 프롬프트/QLoRA FT | https://ai.google.dev/gemma/docs/capabilities/vision/image · https://ai.google.dev/gemma/docs/core/huggingface_vision_finetune_qlora |
| Ollama API·비전·structured output·gemma4 | https://github.com/ollama/ollama/blob/main/docs/api.md · https://docs.ollama.com/capabilities/vision · https://docs.ollama.com/capabilities/structured-outputs · https://ollama.com/library/gemma4 |
| MLX (mlx-lm LoRA 텍스트 전용) | https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md |
| PaddleOCR-VL | https://arxiv.org/abs/2510.14528 · https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html · https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL-Apple-Silicon.html · https://docs.vllm.ai/projects/recipes/en/latest/PaddlePaddle/PaddleOCR-VL.html |
| Google Cloud Vision OCR | https://cloud.google.com/vision/docs/ocr |

## Implementation TODOs / Requires human decision

- ✅ DONE(2026-06-13): det thresh 3종(`text_det_thresh`/`box_thresh`/`unclip_ratio`) 런타임 배선 (`config.py` `local_ocr_text_det_thresh`/`_box_thresh`/`_unclip_ratio` + `paddle.py:_predict_kwargs`, 기본 None=무변경, 공식 URL 주석, 단위 테스트 2건)
- TODO: `label_enhance` 전처리 모드 구현 (현 모드: none/autocontrast/grayscale_autocontrast)
- TODO: Gemma assist 비교 harness (structured eval에 assist 경로 추가)
- TODO: assist 트리거 확장(ingredient gap/field missing) 구현
- TODO: detector gate 실패 요약의 예외 원문 저장 제거(error_type만)
- TODO: macro/micro 모집단 비대칭 — scored/skipped 수를 게이트 출력에 항상 기록
- TODO: paddlepaddle 버전 드리프트(3.2.0/3.3.1/3.2.2) 한 쌍 고정 후 게이트 측정
- Requires human decision: quick-win default 채택 최소 개선폭 · teacher consensus epsilon · recognition acc 절대 하한 · teacher 원문 보존 예외 · **Ultralytics AGPL-3.0 vs Enterprise 라이선스**
