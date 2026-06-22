# Plan C. PaddleOCR Fine-Tuning 상세 설계/구현 플랜

- 작성일: 2026-05-17
- 작성 위치: `yeong-Lemon-Aid/Brand-New-update`
- 대상 코드: `yeong-Lemon-Aid/backend/Nutrition-backend`, `yeong-Lemon-Aid/backend/scripts`
- 상태: v1 구현 기준 문서

## 1. 결론

Plan C의 목표는 PaddleOCR 기본 모델이 영양제 라벨의 한영 혼합 텍스트, 숫자, 단위, 작은 표 글자를 반복적으로 잘못 인식할 때 재현 가능한 fine-tuning 데이터셋과 평가 gate를 만드는 것이다. v1은 API 서버에서 학습을 실행하지 않는다. backend runtime은 PaddleOCR inference provider로 남기고, 학습은 consent-gated offline dataset export, runbook, benchmark/promotion report로 분리한다.

권장 순서는 recognition-first다. 영양제 라벨에서는 `mg`, `mcg`, `µg`, `IU`, `%DV`, `0/O`, `1/l/I` 같은 숫자/단위/문자 혼동이 downstream parser 실패로 바로 이어지므로, 사람이 확인한 `line crop 또는 word crop -> transcript` 데이터부터 학습 후보로 만든다. Detection fine-tuning은 baseline badcase에서 `detection_miss`가 주요 원인으로 확인된 뒤 진행한다.

## 2. 공식 문서 기준

확인한 공식 문서:

- PaddleOCR Text Recognition Module: https://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html
- PaddleOCR Text Detection Module: https://www.paddleocr.ai/main/en/version3.x/module_usage/text_detection.html
- PaddleOCR OCR Dataset Docs: https://www.paddleocr.ai/main/en/datasets/ocr_datasets.html
- PaddleOCR Fine-Tuning Reference: https://www.paddleocr.ai/v3.0.3/en/version2.x/ppocr/model_train/finetune.html

공식 문서 기준 반영:

- recognition module 문서는 dataset/pretrained model 준비, training, evaluation, export 흐름을 제공한다.
- detection module 문서는 `Train.dataset.label_file_list`, `Eval.dataset.label_file_list`, train/eval/export command 흐름을 제공한다.
- OCR dataset 문서는 detection label format을 `image_path<TAB>json.dumps(annotation list)`, recognition label format을 `image_path<TAB>transcript`로 설명한다.
- export 후 생성되는 inference model directory를 PaddleOCR API에 연결할 수 있다.

명시적 한계:

- I cannot find the official documentation for this specific query: supplement-label-specific PaddleOCR confidence threshold.
- I cannot find the official documentation for this specific query: expected PaddleOCR accuracy on Korean and English supplement labels photographed by smartphones.
- 따라서 Plan C는 성능 claim이 아니라 데이터셋 품질, 누수 차단, 재현성, downstream metric 기반 승격 판단을 목표로 한다.

## 3. 구현된 v1 범위

### C0. Badcase Taxonomy

- failure category를 `detection_miss`, `recognition_error`, `layout_association_error`, `parser_error`, `input_quality_error`로 고정한다.
- fine-tuning dataset에는 `recognition_error`와 검증된 `detection_miss`를 우선 포함한다.
- parser correction으로 해결할 문제를 OCR 모델 학습 데이터에 섞지 않기 위해 badcase category를 manifest metadata로 남긴다.

### C1-C3. Dataset Manifest, Export, Split Validation

추가된 manifest schema:

- `sample_id`
- `source_image_id`
- `crop_id`
- `image_path`
- `product_group_id`
- `image_hash`
- `split_group`
- `split`
- `task_type`
- `language_mix`
- `field_type`
- `human_verified`
- `consent_scope`
- `transcript_hash`
- `verified_transcript`
- `boxes`
- `session_group_id`
- `augmented_source_id`

핵심 정책:

- `human_verified=false` sample은 train/export에서 차단한다.
- transcript에는 tab, newline, control character를 허용하지 않는다.
- product group, image hash, split group, session group, augmented source가 train/val/test를 넘으면 실패한다.
- metadata sidecar에는 transcript text를 저장하지 않고 `transcript_hash`, box count, point count만 남긴다.
- raw image, raw OCR text, provider raw payload, filename, EXIF/GPS, user id, credential field는 manifest에서 차단한다.

### C4. Fine-Tuning Runbook

Recognition 1차 runbook 입력:

```bash
python3 tools/train.py \
  -c configs/rec/PP-OCRv5/<recognition-config>.yml \
  -o Global.pretrained_model=<pretrained_model_path> \
     Train.dataset.data_dir=<dataset_root> \
     Train.dataset.label_file_list='[<dataset_root>/rec/train.txt]' \
     Eval.dataset.data_dir=<dataset_root> \
     Eval.dataset.label_file_list='[<dataset_root>/rec/val.txt]' \
     Global.seed=<seed>
```

Detection 1차 runbook 입력:

```bash
python3 tools/train.py \
  -c configs/det/PP-OCRv5/<detection-config>.yml \
  -o Global.pretrained_model=<pretrained_model_path> \
     Train.dataset.data_dir=<dataset_root> \
     Train.dataset.label_file_list='[<dataset_root>/det/train.txt]' \
     Eval.dataset.data_dir=<dataset_root> \
     Eval.dataset.label_file_list='[<dataset_root>/det/val.txt]' \
     Global.seed=<seed>
```

Export 기준:

```bash
python3 tools/export_model.py \
  -c <config_path> \
  -o Global.pretrained_model=<best_accuracy.pdparams> \
     Global.save_inference_dir=<save_inference_dir>
```

runbook artifact에는 command, config snapshot, PaddleOCR version, pretrained model path, dataset checksum, model checksum, seed를 기록한다.

### C5. Evaluation and Promotion Gate

Promotion candidate 조건:

- baseline과 candidate가 같은 `frozen_test_split_id`를 사용한다.
- primary metric: `numeric_exact_rate`, `unit_exact_rate`, `line_exact_rate`, `parser_success_rate`, `field_exact_rate`.
- primary metric 중 하나 이상 개선되어야 한다.
- 어떤 primary metric도 baseline보다 낮아지면 안 된다.
- raw OCR text는 evaluation report에 저장하지 않는다.

### C6. Runtime Model Injection

추가 설정:

```dotenv
LOCAL_OCR_TEXT_RECOGNITION_MODEL_DIR=
LOCAL_OCR_TEXT_DETECTION_MODEL_DIR=
LOCAL_OCR_TEXT_RECOGNITION_MODEL_NAME=
LOCAL_OCR_TEXT_DETECTION_MODEL_NAME=
```

`PaddleOCRAdapter`는 설정값이 있을 때만 PaddleOCR 3.x parameter인 `text_recognition_model_dir`, `text_detection_model_dir`, `text_recognition_model_name`, `text_detection_model_name`으로 전달한다. Deprecated `rec_model_dir`, `det_model_dir`는 사용하지 않는다.

운영 요청에서는 기본 모델과 fine-tuned 모델을 동시에 실행하지 않는다. Shadow 비교는 별도 benchmark job에서 수행한다.

## 4. 구현 파일

- `backend/Nutrition-backend/src/models/schemas/paddleocr_finetuning.py`
  - fine-tuning manifest, sample, detection box schema
- `backend/Nutrition-backend/src/learning/paddleocr_finetuning.py`
  - consent-gated manifest build, raw field rejection, split validation, label render, distribution report, promotion gate
- `backend/scripts/export_paddleocr_finetuning_dataset.py`
  - redacted input manifest를 PaddleOCR recognition/detection label file과 metadata sidecar로 export
- `backend/Nutrition-backend/src/config.py`
  - fine-tuned PaddleOCR model dir/name settings
- `backend/Nutrition-backend/src/ocr/providers/paddle.py`
  - fine-tuned model settings를 PaddleOCR initializer에 연결

## 5. 테스트 기준

필수 테스트:

- raw image/OCR/provider payload/user id/filename/EXIF/GPS field 차단
- `human_verified=false` sample의 train export 차단
- transcript tab/newline/control character 차단
- recognition label file format: `relative_image_path<TAB>transcript`
- detection label file format: `relative_image_path<TAB>json boxes`
- product/hash/session/augmented-source split leakage 탐지
- promotion gate의 improvement/no-regression 조건
- fine-tuned model settings가 PaddleOCR 공식 3.x parameter로 전달되는지 검증

권장 실행:

```bash
cd yeong-Lemon-Aid/backend
python -m pytest -o addopts='' \
  Nutrition-backend/tests/unit/learning/test_paddleocr_finetuning.py \
  Nutrition-backend/tests/unit/scripts/test_export_paddleocr_finetuning_dataset.py \
  Nutrition-backend/tests/unit/ocr/test_paddle_provider.py \
  Nutrition-backend/tests/unit/test_config.py \
  -q
```

품질 확인:

```bash
python -m ruff check \
  Nutrition-backend/src/models/schemas/paddleocr_finetuning.py \
  Nutrition-backend/src/learning/paddleocr_finetuning.py \
  scripts/export_paddleocr_finetuning_dataset.py
python -m black --check \
  Nutrition-backend/src/models/schemas/paddleocr_finetuning.py \
  Nutrition-backend/src/learning/paddleocr_finetuning.py \
  scripts/export_paddleocr_finetuning_dataset.py
python -m mypy \
  Nutrition-backend/src/models/schemas/paddleocr_finetuning.py \
  Nutrition-backend/src/learning/paddleocr_finetuning.py \
  scripts/export_paddleocr_finetuning_dataset.py
```

## 6. 남은 작업

- 실제 PaddleOCR repository checkout 기준 config file path를 팀 환경에 맞게 고정한다.
- `RUN_PADDLEOCR_TRAINING_SMOKE=1` gated training smoke는 GPU/CPU 학습 환경이 준비된 뒤 별도 추가한다.
- frozen fixture benchmark와 artifact checksum 저장 위치를 `outputs/paddleocr-finetuning/` 아래로 표준화한다.
- detection fine-tuning은 C0 badcase report에서 detection miss 비중이 충분히 확인된 뒤 실행한다.
