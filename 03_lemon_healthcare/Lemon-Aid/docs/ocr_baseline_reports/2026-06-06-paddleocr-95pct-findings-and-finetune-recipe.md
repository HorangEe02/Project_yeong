# PaddleOCR 영양제 라벨 텍스트 추출 — 베이스라인 결과, 무학습 개선, 95% Fine-tune 레시피

작성: 2026-06-06. 범위: CLOVA pseudo-GT 기반 PaddleOCR 텍스트 추출 정확도 측정 + 무학습 개선 + 실제 fine-tune를 위한 요건/레시피. 모든 수치는 redaction-safe(원문 미저장, 숫자 점수만).

---

## 0. Executive Summary

- **Gate #1 (OCR benchmark)** ✅ 통과 — `ready_for_teacher_ocr_eval`, 203 fixtures (holdout 52 / test 22 / train 129, leakage-safe).
- **PaddleOCR 베이스라인 (mobile, 203)**: `field_match_ratio` **0.560 macro / 0.552 micro** (운영자 선택 지표). LCS recall 0.514, ingredient_recall 0.541.
- **Gate #2 (95% target)** ❌ `continue_training_loop` — 미도달(정식 게이트 체인으로 확인).
- **무학습 개선 (detection 민감도 튜닝)**: `box_thresh=0.15, thresh=0.1, unclip=2.0` → field_match_ratio **0.560 → 0.586 (+0.026)**, LCS recall 0.514 → 0.556 (+0.041). 실질적이나 modest. 해상도 상향(4000px)·server detector는 **무효/미미**(아래 §3). 튜닝 후에도 Gate #2 미도달(holdout 52: precision 0.29 / recall 0.55 / f1 0.32) — 95%는 recognizer fine-tune 없이는 불가.
- **실제 recognizer fine-tune: CPU에서 end-to-end 실행 완료(smoke)** — 운영자 승인 후 외부 플러그인 설치 → PaddleX `build_trainer().train()` 2 epoch CPU 실행 → fine-tuned 가중치/inference 모델 산출. **단 재평가 결과 holdout 0.518→0.037로 대폭 하락**(2 epoch·합성·CPU → catastrophic forgetting + sim-to-real). 파이프라인은 검증됐으나 **quality 모델은 GPU + 실사진/혼합 라인데이터 + 다epoch 필요**(§5.1.0). §4 근거(파일:라인), §5 레시피.

---

## 1. 무엇이 완료되었나 (검증됨)

| 단계 | 결과 | 증거 |
|---|---|---|
| CLOVA→GT 채움 | **203/215 ready** | `clova-ground-truth.summary.json` (+ topup/topup2). 12 미복구: CLOVA `FAILURE`×4, ollama transient×1, no-ingredient×7 |
| Gate #1 | `ready_for_teacher_ocr_eval` | `reconciled/ocr-benchmark-gate.json` (203 fixtures, holdout 52/test 22/train 129) |
| 베이스라인 (mobile) | field_match 0.560 | `reconciled/paddleocr-baseline-mobile-v3.json` |
| Gate #2 (95%) | `continue_training_loop` | `reconciled/paddleocr-text-target-gate.json` |

**GAP-3 브리지 동작 확인**: standalone PaddleOCR(.venv-paddle, py3.12) → observations JSONL → `merge_paddleocr_text_observations_into_benchmark` → `build_paddleocr_text_extraction_eval_summary`(holdout) → `gate_paddleocr_text_extraction_target` (전부 py3.13 backend). collect 스크립트가 py3.13에서 paddle 실행 불가한 문제를 우회.

---

## 2. 지표(metric) 정의와 precision-cap

운영자 선택 = **`field_match_ratio`** (per-field 퍼지 일치). 각 GT 필드 단위(product/manufacturer, 성분 display-name, amount+unit, intake text)에 대해 PaddleOCR 텍스트와 rapidfuzz `partial_ratio ≥ 85`이면 일치. **precision-immune** — PaddleOCR가 라벨의 추가 텍스트를 더 읽어도 점수가 깎이지 않음 → 구조화-only GT에 올바른 프레이밍.

정식 게이트(`gate_paddleocr_text_extraction_target`)는 별도로 `normalized_text_precision/recall/f1 ≥ 0.95`(LCS)를 요구하는데, **GT가 구조화 필드만 저장(원문 미저장, redaction)** 이라 `precision = matched/hypothesis_chars`가 구조적으로 0.3 부근으로 상한. 따라서 3-지표 게이트는 GT 형태상 통과 불가이고, 의미 있는 신호는 **recall / field_match_ratio**. (LCS recall 0.514, precision 0.311 측정.)

---

## 3. 무학습(no-training) 개선 — 실측

| 레버 | 결과 | 판정 |
|---|---|---|
| **해상도 상향 (2048→4000px)** | 동일 10장에서 field_match 0.655→0.552 (오히려 하락), 속도 ~5s/img | ❌ mobile 모델은 ~2048 최적, 고해상도 역효과 |
| **server detector (PP-OCRv5_server_det @3072)** | 5장에서 field_match +0.06, **ingredient_recall 동일(0.818)**, ~1min/img | ⚠️ 한계적·느림. recognizer가 천장(같은 mobile rec) |
| **detection 민감도 튜닝 (box/thr/unclip)** | 20장 샘플: default 0.600 → `box0.15/thr0.1/unclip2.0` 0.667. **full 203: 0.560 → 0.586 (+0.026)**, LCS recall +0.041. unclip 과대(3.0)는 역효과 | ✅ 최선의 무학습 레버(modest) |

**채택**: `--det-box-thresh 0.15 --det-thresh 0.1 --det-unclip-ratio 2.0` (eval 스크립트에 opt-in 인자로 추가, default None=기존 동작 보존). full 203 결과: `reconciled/paddleocr-tuned-det-mobile.json`. 튜닝 observations로 Gate #2 재실행 → 여전히 `continue_training_loop`(holdout 52: precision 0.2914 / recall 0.5465 / f1 0.3238), `reconciled/paddleocr-text-target-gate.tuned.json`.

> 핵심 한계: recognizer(`korean_PP-OCRv5_mobile_rec`)가 천장. detection 튜닝은 "탐지되지 않던 텍스트"를 더 잡아 recall을 올리지만, **잘못 인식된 글자**는 못 고침. PP-OCRv5에 한국어 *server* recognizer가 없어 모델 교체로는 한계.

---

## 4. 실제 fine-tune 불가 — 근거 (이 머신 기준)

세 가지 독립 블로커, 모두 코드/환경 증거:

1. **GPU 없음.** `run_paddleocr_finetune_plan.py --execute`는 로컬 PaddleOCR 체크아웃의 `tools/train.py`로 `subprocess` 실행(=GPU 학습). 이 머신은 CPU-only Apple Silicon, PaddleOCR 학습 레포 없음.
2. **라인단위 학습데이터 없음.** `build_paddleocr_finetune_run_plan.py:247`이 **materialized dataset 디렉터리**를 요구 — 라벨 파일은 `잘린 텍스트라인 이미지\t전사` 형식(`:300,:322,:337`)이며 각 이미지가 실제 파일로 resolve돼야 함. 우리는 **구조화 필드 GT만** 보유(라인 bbox·라인 전사 없음). → plan JSON 생성 자체가 실패(`PaddleOCRFinetunePlanError: Materialized dataset directory does not exist`).
3. **개선후보 0건.** `build_paddleocr_improvement_candidates`가 203행에서 0 candidate(`unsupported_schema_version`/teacher-disagreement 신호 부재). 파이프라인이 **teacher OCR observations(원문 포함)** 를 학습 신호로 설계 — 우리는 redaction으로 teacher 원문을 저장하지 않음.

**결론**: 실제 recognizer fine-tune로 95% 도달은 (a) CUDA GPU + PaddleOCR 학습 체크아웃, (b) 라인단위 학습쌍(크롭+전사) 확보가 선행돼야 하며, 현 머신/데이터/정책으로는 불가.

---

## 5. Fine-tune 레시피 (향후 GPU 환경에서 실행)

### 5.1 학습데이터(라인 크롭+전사) 확보 — 택1 (가장 큰 선결과제)
- **(A) 합성 데이터 (추천 1순위, 라벨링 0)**: 한국어 영양제 라벨 텍스트라인을 폰트·배경·노이즈 다양화로 렌더 → 크롭+전사 자동 생성. 성분명/용량 lexicon(DB 카탈로그)로 어휘 커버. PaddleOCR `tools/train.py` rec 학습에 바로 사용.
- **(B) detector-crop + teacher-text 약지도**: PaddleOCR detector로 라인 크롭 → CLOVA OCR 재호출하여 라인별 전사 확보(원문은 **학습용으로만 보존**, redaction 정책 예외 결정 필요) → 크롭\t전사 데이터셋.
- **(C) 수작업 라인 주석**: Label Studio로 라인 bbox+전사(소량, 정밀). 203장×다수 라인 → 큰 공수.

### 5.1.0 ✅ 실제 학습 실행됨 (이 머신, CPU smoke) — 그리고 왜 quality는 아직 아닌지
운영자 승인으로 외부 PaddleOCR 학습 플러그인(`paddlex --install PaddleOCR`)을 설치하고, PaddleX `build_trainer().train()`로 **CPU에서 실제 recognizer fine-tune를 실행**했다(py3.12). 산출물: `datasets/supplement-paddleocr-rec/v1/_train/best_accuracy/{best_accuracy.pdparams, inference/}` + epoch1/2/latest 체크포인트. 학습 로그: `best_epoch=2, norm_edit_dis=0.243, acc=0.0`.

**재평가 (holdout n=25, field_match_ratio):** baseline rec **0.518 → fine-tuned 0.037** (대폭 하락). 원인: (1) 2 epoch·CPU·합성 600줄뿐 → 사전학습 가중치의 실사진 인식 능력이 catastrophic forgetting으로 붕괴, (2) sim-to-real 격차(렌더 텍스트 vs 라벨 사진). 즉 **"학습 실행"은 end-to-end 검증 완료(파이프라인 동작 OK)이나, 유의미한 모델은 아님.** quality 모델 요건: 더 많은 epoch + 실사진/혼합 라인-크롭 데이터 + 적절한 LR/freeze 전략 + GPU(§5.1 데이터, §5.3 HP).

PaddleX 패키징 갭 2건도 우회 적용함: `repo_manager/repos/` 디렉터리 생성, `repo_apis/PaddleOCR_api/configs/korean_PP-OCRv5_mobile_rec.yaml` 배치(클론된 repo config 복사).

### 5.1.1 ✅ 생성됨 (이 머신, CPU) — 데이터셋 + 검증된 plan
무학습으로 갈 수 있는 끝까지 진행함:
- **합성 rec 데이터셋 생성**: `build_synthetic_paddleocr_rec_dataset.py`(신규) → `datasets/supplement-paddleocr-rec/v1/` (train 600 / val 100, vocab 332; PaddleOCR rec 포맷 `rec/rec_gt_{train,val}.txt` + 크롭 PNG). 합성 텍스트는 우리가 author한 것(원문 OCR 아님 → redaction 무관).
- **검증된 fine-tune run plan**: `build_paddleocr_finetune_run_plan.py`가 위 데이터셋에 대해 `status: ok`(validated_not_executed)로 plan 생성 → `reconciled/paddleocr-finetune-run-plan.recognition.json`. 정확한 학습 커맨드 내장:
  `python3 -m paddle.distributed.launch --gpus 1 tools/train.py -c configs/rec/PP-OCRv5/korean_PP-OCRv5_mobile_rec.yml -o Global.pretrained_model=... Global.epoch_num=100 Optimizer.lr.learning_rate=0.0005 ...`
- **남은 단계(GPU 필요)**: PaddleOCR 학습 체크아웃 준비 후
  `run_paddleocr_finetune_plan.py --plan <plan> --paddleocr-root <PaddleOCR_checkout> --execute --timeout-seconds <N>`
- 주의: 합성-only는 sim-to-real 격차 존재. 실사용 정확도↑를 위해 실제 라벨 사진 라인-크롭(§5.1-B/C)을 혼합 권장.

### 5.2 데이터셋 → 학습 → 게이트 (스크립트 존재, GPU 필요)
```
# 1) 개선 후보 → 주석 태스크 → 데이터셋 (teacher observations 또는 합성 라벨 입력 필요)
build_paddleocr_improvement_candidates.py --benchmark-manifest <merged> --output <cand>
create_paddleocr_annotation_tasks_from_improvement_candidates.py ...
promote_paddleocr_annotation_tasks_to_dataset.py ...           # → dataset-version-id(UUID)
export_training_manifest.py --dataset-version-id <uuid> --output <export>
materialize_paddleocr_dataset.py --export <export> --source-map <map> --output-dir <datasets/.../v1>
# 2) 학습 계획 → 실행 (GPU)
build_paddleocr_finetune_run_plan.py --dataset-dir <datasets/.../v1> --task recognition \
  --dataset-version-id <uuid> --base-model korean_PP-OCRv5_mobile_rec \
  --config-ref <rec.yml> --pretrained-model-ref <pretrain> --save-model-ref <out> \
  --epochs 100 --learning-rate 5e-4 --batch-size-per-card 64 --gpus 1 --output <plan> --summary <sum>
register_paddleocr_finetune_run_from_plan.py --plan <plan> ...
run_paddleocr_finetune_plan.py --plan <plan> --execute        # tools/train.py subprocess (GPU)
# 3) 재평가 → baseline 대비 게이트
run_paddleocr_eval_from_finetune_plan.py --plan <plan> ... --output <ft-metrics>
gate_paddleocr_finetune_against_baseline.py --task recognition \
  --finetuned-metrics <ft-metrics> --baseline-metrics <baseline> --output <cmp>
# 4) 95% 타깃 게이트 (현 브리지 그대로)
build_paddleocr_text_extraction_eval_summary.py --benchmark-manifest <merged-ft> --eval-split holdout ...
gate_paddleocr_text_extraction_target.py --eval-summary <ft-eval-summary> --min-fixtures 30 ...
```

### 5.3 권장 하이퍼파라미터(출발점)
- base: `korean_PP-OCRv5_mobile_rec` (pretrained) fine-tune. epochs 100, lr 5e-4 (cosine), batch 64/card, 합성:실데이터 혼합 시 합성 비중↑.
- 평가는 항상 **holdout 52** + `field_match_ratio` + LCS recall 병기.

---

## 6. 이번 작업으로 변경/추가된 코드·산출물

**코드(ruff clean, type hints, Google docstrings):**
- `backend/scripts/finalize_supplement_ocr_ground_truth_bundle_summary.py` (신규) — GAP-1 해소: 채워진 todo.jsonl에서 ready 행만 스코프한 bundle summary 발행(ready==template).
- `backend/scripts/paddleocr_clova_eval.py` (개선) — 프로젝트 일치 metric(LCS P/R/F1) + 운영자 metric `field_match_ratio` + `--profile`(mobile/server) + **opt-in detection 튜닝 인자**(`--det-box-thresh/--det-thresh/--det-unclip-ratio`, default None=기존 동작) + observation JSONL(게이트 브리지).
- `backend/scripts/gate_supplement_ocr_benchmark.py` — `--required-expected-section` override 옵션(기본 정책 불변).
- `backend/scripts/build_clova_ground_truth.py` — ready 행 `decision:approved` 보정.
- `backend/scripts/build_synthetic_paddleocr_rec_dataset.py` (신규) — 합성 한국어 rec 학습 데이터셋 생성(라인 크롭+전사), GPU fine-tune용.

**Fine-tune 산출물(GPU 직전까지 완료):**
- `outputs/.../datasets/supplement-paddleocr-rec/v1/` — 합성 rec 데이터셋(train 600 / val 100) + 실제 학습된(2ep CPU smoke) 모델 `_train/`.
- **`outputs/.../datasets/supplement-paddleocr-rec-realphoto/v1/`** — ⭐ **실사진 라인-크롭 데이터셋**(CLOVA teacher-box): 129 이미지(train 스플릿만) → **crop 5,846**(train 5,101 / val 745, dict 656). holdout+test 제외(누수 방지). `check_dataset` 통과. `RUN_ON_GPU.md` 런북 동봉.
- `reconciled/paddleocr-finetune-run-plan.recognition.json` (합성) + **`...realphoto.json`(실사진, status: ok)** — 검증된 fine-tune run plan, 학습 커맨드 내장. GPU에서 `run_paddleocr_finetune_plan.py --execute`만 남음(운영자 결정: 학습 보류).
- 신규 스크립트: `build_clova_realphoto_rec_dataset.py`(CLOVA teacher-box → 실사진 크롭, ruff clean). eval 스크립트에 `--rec-model-dir`(fine-tuned 모델 재평가용) 추가.
- ⭐⭐ **스케일 데이터셋(크롤링 상세페이지)**: `datasets/supplement-paddleocr-rec-crawling/v1/` — `crawling-image/*/*/상세페이지`에서 CLOVA teacher-box로 **제품 342개 · 상세 1,420장(제품당 최대 6) → crop 128,315**(train 115,442 / val 12,873, dict 1,180자). 벤치마크 holdout+test **제품 44개 제외**(product_dir_hash 매칭, 누수 안전). `check_dataset` 통과. 검증된 plan `...crawling.json`(status ok) + `RUN_ON_GPU.md` 동봉. (이전 realphoto 5,846 crop 대비 **~22×**.)
- 신규 스크립트: `build_crawling_realphoto_rec_dataset.py` — 상세페이지 순회 + tall 수직 타일링 + per-box CLOVA + fail-closed 누수제외 + datasets/ 가드 + per-image 격리 + seeded 제품단위 split + 비용 캡(ruff clean, 스모크 1장→57 crop).

**산출물(`outputs/.../operator-review/reconciled/`):**
- `ocr-ground-truth-bundle-summary.finalized.json`, `ocr-ground-truth-preflight.json`, `ocr-benchmark-manifest.jsonl`(+summary), `ocr-benchmark-splits.assignment.json`(+summary), `ocr-benchmark-gate.json`(Gate #1) — 전부 GREEN 경로.
- `paddleocr-baseline-mobile-v3.json`(베이스라인), `paddleocr-observations-mobile-v3.jsonl`, `ocr-benchmark-merged.full.jsonl`, `paddleocr-eval-summary.holdout.json`, `paddleocr-text-target-gate.json`(Gate #2).
- `paddleocr-tuned-det-mobile.json` + `paddleocr-observations-tuned.jsonl` (무학습 튜닝 결과) + 튜닝 Gate #2 재실행 산출물.

---

## 6.1 적대적 코드리뷰 + 하드닝 (이번 세션)
신규/변경 스크립트 5개를 다중 리뷰어로 적대적 검토 → 검증된 결함 8건 전부 수정(ruff clean, gate 14 tests pass, Gate #1 여전히 GREEN 재확인):
- finalize: `--required-expected-section` 추가 — ready 카운트가 strict 정책에서 benchmark fixture 수를 초과하지 않도록 builder와 동일 필터 적용.
- paddleocr_clova_eval: per-row 실패 격리(`failed_images` 카운트) — 이미지 1장 오류가 전체 eval을 중단시키지 않음.
- build_clova_realphoto: 누수 가드 **fail-closed**(train(+test) allow-list, splits 누락 fixture는 학습 제외) + 출력 경로 `datasets/` 하위 강제 가드 + seeded train/val shuffle.
- build_synthetic: vocab harvest에서 holdout/test fixture 제외(`--splits`) — 어휘 단위 누수 차단.
- build_clova_ground_truth: 실패 요약에서 **절대경로 누출 제거**(error type만 저장), `output`은 basename만, 입력 JSONL per-line 격리(`malformed_input_lines`).

## 7. 다음 단계 (권장)
1. (무학습) 튜닝 detection 파라미터를 기본 운영값으로 채택, field_match_ratio 개선분 반영.
2. (학습) §5.1-(A) 합성 한국어 라벨 라인 생성 파이프라인 구축 → §5.2 체인으로 GPU 환경에서 fine-tune → 95% 게이트 재평가.
3. (정책) teacher 원문 보존(§5.1-B) 또는 합성 전용(§5.1-A) 중 데이터 확보 경로를 운영자가 확정.
