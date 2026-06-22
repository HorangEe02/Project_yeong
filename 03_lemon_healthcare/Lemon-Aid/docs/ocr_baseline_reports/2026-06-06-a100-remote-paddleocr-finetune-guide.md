# A100 원격 PaddleOCR 한국어 recognizer 본학습 가이드

이 머신(Apple Silicon, CPU-only)에서는 데이터셋/검증 산출물 준비와 회수 후 평가만 수행한다. 실제 본학습은
VS Code로 연결된 **NVIDIA A100 Windows 서버**에서 실행한다.

공식 근거:
- PaddleOCR 설치 및 학습 의존성 구성: https://www.paddleocr.ai/latest/en/version3.x/installation.html
- PaddleOCR 한국어 PP-OCRv5 recognizer 모델 목록: https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html
- PaddleOCR 3.x OCR pipeline `text_recognition_model_dir` 설정: https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html
- PaddleOCR recognition 학습/평가/export 포맷: https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html
- PaddleOCR/PaddlePaddle GPU 설치와 CUDA/driver 요구사항: https://www.paddleocr.ai/latest/en/version3.x/paddlepaddle_installation.html
- PaddlePaddle Windows pip 설치: Windows는 single GPU training/inference를 지원하고 NCCL/distributed training은 지원하지 않는다. https://www.paddlepaddle.org.cn/documentation/docs/install/pip/windows-pip_en.html
- Korean PP-OCRv5 학습 config 원본: https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/configs/rec/PP-OCRv5/multi_language/korean_PP-OCRv5_mobile_rec.yml

> 데이터셋은 CLOVA teacher 텍스트를 포함하므로 git 금지 대상이다. 전송은 `scp`/`rsync`/사설 오브젝트 스토리지로만 수행하고, 학습 후 Mac에는 `best_accuracy/inference/` 모델만 회수한다.

---

## 0. 이번 실행 기준

| 지표 | 이전 realphoto | 신규 crawling-scale |
|---|---:|---:|
| 제품 | 129 | 342 |
| 소스 이미지 | 129 | 885 상세페이지 |
| crop | 5,846 | 77,606 (약 13배) |
| train / val | 5,101 / 745 | 70,778 / 6,828 |
| dict 문자 | 656 | 1,066 |

이번 run은 위 신규 수치가 hard gate다. 로컬에 남아 있는 다른 crawling 산출물이 더 크더라도 이번 학습 기준으로 사용하지 않는다.

대상 private 산출물:
- dataset root: `outputs/generated/supplement-learning/2026-06-05/operator-review/datasets/supplement-paddleocr-rec-crawling/v2/`
- train labels: `rec/rec_gt_train.txt`
- val labels: `rec/rec_gt_val.txt`
- dict: `dict.txt`

현재 로컬 legacy crawling artifact와 기존 run plan은 이번 표보다 큰 기준이므로 이번 실행에서 제외한다. 신규 v2는 `--max-images-per-product 3` 기준으로 다시 생성해야 하며, dry-run의 source count가 `products_with_detail_images=342`, `detail_images_at_cap=885`인지 먼저 확인한다.

legacy artifact를 파일명 기준으로 단순 downsample해서 v2로 쓰면 이번 hard gate와 일치하지 않는다. v2는 아래 builder로 재생성하고, 생성 후 `validate_paddleocr_rec_dataset_counts.py`를 통과한 산출물만 A100로 전송한다.

---

## 0.1 2026-06-07 실행 상태

현재 기준 확인된 상태:
- Mac v2 dataset 생성 완료: `products_used=342`, `detail_images_processed=885`, `failed_image_count=0`, `crop_count=77,606`, `train_rows=70,778`, `val_rows=6,828`, `dict_size=1,066`.
- Mac count gate 통과: train 70,778 / val 6,828 / dict 1,066.
- Mac readiness preflight 통과: `status=ready_for_a100_transfer`.
- count-only JSON privacy check 통과: finding 0.
- A100 실제 작업 루트: `G:\lemon-aid\paddleocr_rec_work`.
- A100 Python env: `G:\lemon-aid\paddleocr_rec_work\.venv-paddle`, PaddlePaddle GPU 3.2.2, PaddleOCR package 3.6.0, PaddleOCR checkout `1e5aa0ad31`.
- A100 CUDA preflight 통과: A100 80GB 1장 인식, `paddle.utils.run_check()` 성공, Driver API 12.4 / Runtime API 11.8.
- A100 dataset gate 통과: train 70,778 / val 6,828 / dict 1,066.
- smoke 1 epoch 통과: `output\supplement_rec_crawling_v2_smoke\latest.pdparams`, `latest.pdopt`, `latest.states` 생성. `best_accuracy`는 768 iters smoke가 config의 eval interval 1,000에 도달하지 않아 생성되지 않는 것이 정상이다.
- smoke memory: max reserved 23,930 MB, max allocated 16,031 MB.
- full 100 epoch run 시작됨: log `G:\lemon-aid\paddleocr_rec_work\full.v2.combined.log`. 2026-06-07 13:45 KST 기준 epoch 1/100, global_step 150, ETA 약 1일. 2026-06-07 13:50 KST `nvidia-smi`에서 새 Python GPU process가 31,374 MiB를 사용 중인 것을 확인했다. 이후 VS Code GPU 화면에는 다른 `train_single_model.py`/`pro-vision` 프로세스도 함께 보여 이 run을 clean 기준으로 재사용하지 않는다.

Mac 적용은 full run 완료, export, `best_accuracy/inference/` 회수, holdout gate 통과 후에만 진행한다.

## 0.2 clean venv restart 기준

사용자가 선택한 재시작 방식은 병행 유지다. 따라서 기존 GPU 프로세스는 중단하지 않고, 새 venv와 새 output suffix로 다시 실행한다.

고정값:
- workspace root: `G:\lemon-aid\paddleocr_rec_work`
- dataset version: `v2`
- clean venv: `G:\lemon-aid\paddleocr_rec_work\.venv-paddle-rec-v2-clean`
- run suffix: `v2_clean`
- smoke output: `output\supplement_rec_crawling_v2_clean_smoke`
- full output: `output\supplement_rec_crawling_v2_clean`
- full log: `G:\lemon-aid\paddleocr_rec_work\full.v2_clean.combined.log`

운영 스크립트는 dataset 경로와 output suffix를 분리한다. `DatasetVersion=v2`는 `rec_dataset\v2` count gate에만 사용하고, `RunSuffix=v2_clean`은 log/checkpoint/export 경로에만 사용한다.

---

## 1. Codex SSH preflight

Codex에서 직접 학습을 운영하려면 Mac shell에서 무비밀번호 SSH가 먼저 열려야 한다.

```bash
ssh 155.230.153.222 nvidia-smi
```

필수 확인:
- GPU: A100 40GB 또는 80GB가 보여야 한다.
- driver/CUDA: 설치된 PaddlePaddle GPU wheel과 호환되어야 한다.
- 현재 GPU 메모리 사용량: smoke/full run 시작 전에 불필요한 기존 학습 프로세스를 정리한다.
- 2026-06-07 확인 결과: 원격 기본 Python은 `G:\anaconda3\python.exe`, `C:\Users\lemon-aid\workspace`는 없고 `G:\lemon-aid`가 실제 작업 드라이브다. 기존 conda env에는 `paddle`/`paddleocr`가 없으므로 새 격리 venv를 만든다.

Codex에서 SSH 인증이 실패하면, 연결된 VS Code 원격 터미널에서 아래 A100 명령을 직접 실행한다. Codex는 문서/명령/평가 기준만 관리한다.

---

## 2. 신규 v2 dataset 생성

Mac에서 CLOVA teacher crop dataset을 다시 만들 때는 `--max-images-per-product 3`을 사용한다. `--apply` 전 dry-run은 원문 label text를 만들거나 출력하지 않는다.

```bash
PYTHONPATH=backend/Nutrition-backend backend/.venv/bin/python backend/scripts/build_crawling_realphoto_rec_dataset.py \
  --crawl-root data/nutrition_reference/crawling-image \
  --splits outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/ocr-benchmark-splits.assignment.json \
  --output-dir outputs/generated/supplement-learning/2026-06-05/operator-review/datasets/supplement-paddleocr-rec-crawling/v2 \
  --max-images-per-product 3
```

dry-run 기준:
- `eligible_product_count`: 343
- `products_with_detail_images`: 342
- `detail_images_at_cap`: 885

위 source count가 맞고 CLOVA 호출/teacher label 저장 승인이 있을 때만 `--apply`를 붙인다.

```bash
PYTHONPATH=backend/Nutrition-backend backend/.venv/bin/python backend/scripts/build_crawling_realphoto_rec_dataset.py \
  --crawl-root data/nutrition_reference/crawling-image \
  --splits outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/ocr-benchmark-splits.assignment.json \
  --output-dir outputs/generated/supplement-learning/2026-06-05/operator-review/datasets/supplement-paddleocr-rec-crawling/v2 \
  --max-images-per-product 3 \
  --apply
```

생성 후 다음 count-only gate가 정확히 통과해야 한다.

```bash
backend/.venv/bin/python backend/scripts/validate_paddleocr_rec_dataset_counts.py \
  --dataset-dir outputs/generated/supplement-learning/2026-06-05/operator-review/datasets/supplement-paddleocr-rec-crawling/v2 \
  --summary-output outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/paddleocr-rec-crawling-v2-count-gate.json
```

기대값은 train 70,778 / val 6,828 / dict 1,066이다. 하나라도 다르면 A100 학습을 시작하지 않는다.

전체 readiness preflight:

```bash
backend/.venv/bin/python backend/scripts/preflight_a100_paddleocr_training_readiness.py \
  --crawl-root data/nutrition_reference/crawling-image \
  --splits outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/ocr-benchmark-splits.assignment.json \
  --dataset-dir outputs/generated/supplement-learning/2026-06-05/operator-review/datasets/supplement-paddleocr-rec-crawling/v2 \
  --summary-output outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/a100-paddleocr-training-readiness.v2.json
```

`status=ready_for_a100_transfer`가 아니면 A100 전송과 학습을 시작하지 않는다. `blocked_by_dataset_count_gate`는 v2 dataset이 아직 생성되지 않았거나 count가 맞지 않는 상태다.

---

## 3. 데이터 전송

Mac에서 dataset과 repo 또는 필요한 scripts만 A100 작업 디렉터리로 전송한다. Windows OpenSSH 환경에서는 대상 경로를 `/c/Users/lemon-aid/...` 또는 VS Code 터미널에서 보이는 실제 경로로 맞춘다.

```bash
DS="outputs/generated/supplement-learning/2026-06-05/operator-review/datasets/supplement-paddleocr-rec-crawling/v2"
scp -r "$DS" 155.230.153.222:'G:/lemon-aid/paddleocr_rec_work/rec_dataset/v2'
scp backend/scripts/validate_paddleocr_rec_dataset_counts.py \
  backend/scripts/run_a100_paddleocr_windows_training.ps1 \
  backend/scripts/start_a100_paddleocr_windows_background.ps1 \
  backend/scripts/watch_a100_paddleocr_windows_early_stop.ps1 \
  155.230.153.222:'G:/lemon-aid/paddleocr_rec_work/Lemon-Aid/backend/scripts/'
```

대용량 전송이 불안정하면 `tar`로 묶어서 전송한다. 단, dataset tarball도 git에 추가하지 않는다.

---

## 4. Windows A100 환경 구성

PowerShell 기준:

```powershell
$ROOT="G:\lemon-aid\paddleocr_rec_work"
$VENV="$ROOT\.venv-paddle-rec-v2-clean"
New-Item -ItemType Directory -Force $ROOT, "$ROOT\Lemon-Aid\backend\scripts", "$ROOT\rec_dataset" | Out-Null
G:\anaconda3\python.exe -m venv $VENV
& "$VENV\Scripts\Activate.ps1"
python -m pip install -U pip setuptools
python -m pip install paddlepaddle-gpu==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
python -c "import paddle; print('cuda', paddle.is_compiled_with_cuda()); print('gpus', paddle.device.cuda.device_count())"
python -c "import paddle; paddle.utils.run_check()"
```

PaddleOCR 학습 checkout 준비:

```powershell
git clone https://github.com/PaddlePaddle/PaddleOCR.git
cd PaddleOCR
git rev-parse --short HEAD
python -m pip install -r requirements.txt
python -m pip install paddleocr
```

사내/폐쇄망이면 미리 받은 PaddleOCR checkout을 복사해서 사용한다.

---

## 5. Dataset hard gate

학습 전에 반드시 count-only gate를 통과해야 한다. 원문 label text는 출력하지 않는다.

PowerShell:

```powershell
$ROOT="G:\lemon-aid\paddleocr_rec_work"
$DS="$ROOT\rec_dataset\v2"
python "$ROOT\Lemon-Aid\backend\scripts\validate_paddleocr_rec_dataset_counts.py" `
  --dataset-dir $DS `
  --summary-output "$ROOT\paddleocr-rec-crawling-v2-count-gate.json"
```

이 gate가 실패하면 학습을 시작하지 않는다. 기존 로컬 128k crop 계열 산출물과 혼용하지 않는다.

PaddleOCR recognition 데이터 포맷도 확인한다:

```powershell
python -c "from pathlib import Path; ds=Path(r'G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2'); assert (ds/'rec/rec_gt_train.txt').is_file(); assert (ds/'rec/rec_gt_val.txt').is_file(); assert (ds/'dict.txt').is_file(); print('dataset_files_ok')"
```

권장 운영 스크립트:

```powershell
cd G:\lemon-aid\paddleocr_rec_work\Lemon-Aid
powershell -ExecutionPolicy Bypass -File backend\scripts\run_a100_paddleocr_windows_training.ps1 -Mode preflight -DatasetVersion v2 -RunSuffix v2_clean
powershell -ExecutionPolicy Bypass -File backend\scripts\run_a100_paddleocr_windows_training.ps1 -Mode dataset -DatasetVersion v2 -RunSuffix v2_clean
powershell -ExecutionPolicy Bypass -File backend\scripts\run_a100_paddleocr_windows_training.ps1 -Mode smoke -DatasetVersion v2 -RunSuffix v2_clean
powershell -ExecutionPolicy Bypass -File backend\scripts\start_a100_paddleocr_windows_background.ps1 -Mode full -DatasetVersion v2 -RunSuffix v2_clean
powershell -ExecutionPolicy Bypass -File backend\scripts\start_a100_paddleocr_windows_background.ps1 -Mode early-stop -RunSuffix v2_clean -EarlyStopPatienceEpochs 5 -EarlyStopPollSeconds 60
powershell -ExecutionPolicy Bypass -File backend\scripts\run_a100_paddleocr_windows_training.ps1 -Mode export -DatasetVersion v2 -RunSuffix v2_clean
```

`preflight`는 dataset이 없어도 `nvidia-smi`와 `paddle.utils.run_check()`만 확인한다. `dataset`, `smoke`, `full`은 train/val/dict line count가 각각 70,778 / 6,828 / 1,066이 아니면 즉시 중단한다.
A100 운영 스크립트도 기본적으로 `backend/scripts/validate_paddleocr_rec_dataset_counts.py`를 호출해 Mac과 같은 count-only gate JSON을 남긴다.
`full`은 SSH 세션보다 오래 실행되므로 `start_a100_paddleocr_windows_background.ps1`가 `Win32_Process.Create`로 detached process를 만들고, `G:\lemon-aid\paddleocr_rec_work\full.v2_clean.combined.log`에 stdout/stderr를 함께 남긴다.
`early-stop`은 공식 PaddleOCR 학습 loop를 직접 수정하지 않고 `train.log`의 eval metric만 감시한다. 최신 평가 epoch와 `best_epoch` 차이가 `EarlyStopPatienceEpochs` 이상이면 `RunSuffix`와 clean venv 경로가 모두 일치하는 `tools\train.py` 프로세스만 종료한다. 보수 기본값은 5 epoch이며, 더 공격적으로 멈추려면 3으로 낮춘다.

---

## 6. Windows single-GPU smoke 학습

Windows PaddlePaddle는 distributed/NCCL 경로가 아니라 single GPU direct train으로 실행한다. 공식 문서의 Windows 조건에 맞춰 `num_workers=0`을 명시한다.

PowerShell:

```powershell
cd G:\lemon-aid\paddleocr_rec_work\PaddleOCR
$env:CUDA_VISIBLE_DEVICES="0"
python tools\train.py `
  -c configs\rec\PP-OCRv5\multi_language\korean_PP-OCRv5_mobile_rec.yml `
  -o "Global.pretrained_model=pretrain\korean_PP-OCRv5_mobile_rec_pretrained" `
     "Global.save_model_dir=output\supplement_rec_crawling_v2_clean_smoke" `
     Global.epoch_num=1 `
     "Global.character_dict_path=G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2\dict.txt" `
     Global.use_space_char=True `
     Optimizer.lr.learning_rate=0.0005 `
     "Train.dataset.data_dir=G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2" `
     "Train.dataset.label_file_list=['G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2\rec\rec_gt_train.txt']" `
     "Eval.dataset.data_dir=G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2" `
     "Eval.dataset.label_file_list=['G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2\rec\rec_gt_val.txt']" `
     Train.loader.batch_size_per_card=128 `
     Train.loader.num_workers=0 `
     Eval.loader.num_workers=0
```

Smoke pass 기준:
- return code 0
- `output\supplement_rec_crawling_v2_clean_smoke\latest.pdparams` 또는 `best_accuracy\` checkpoint 생성
- GPU 메모리 OOM 없음

Smoke가 OOM이면 batch를 64로 낮춘다. 경로/config 오류면 full run 전에 중단하고 문서에 원인을 기록한다.

---

## 7. Windows single-GPU full 학습

```powershell
cd G:\lemon-aid\paddleocr_rec_work\PaddleOCR
$env:CUDA_VISIBLE_DEVICES="0"
python tools\train.py `
  -c configs\rec\PP-OCRv5\multi_language\korean_PP-OCRv5_mobile_rec.yml `
  -o "Global.pretrained_model=pretrain\korean_PP-OCRv5_mobile_rec_pretrained" `
     "Global.save_model_dir=output\supplement_rec_crawling_v2_clean" `
     Global.epoch_num=100 `
     "Global.character_dict_path=G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2\dict.txt" `
     Global.use_space_char=True `
     Optimizer.lr.learning_rate=0.0005 `
     "Train.dataset.data_dir=G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2" `
     "Train.dataset.label_file_list=['G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2\rec\rec_gt_train.txt']" `
     "Eval.dataset.data_dir=G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2" `
     "Eval.dataset.label_file_list=['G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2\rec\rec_gt_val.txt']" `
     Train.loader.batch_size_per_card=128 `
     Train.loader.num_workers=0 `
     Eval.loader.num_workers=0
```

Linux/WSL/Docker에서만 distributed command를 사용한다:

```bash
CUDA_VISIBLE_DEVICES=0 python3 -m paddle.distributed.launch --gpus 0 tools/train.py \
  -c configs/rec/PP-OCRv5/multi_language/korean_PP-OCRv5_mobile_rec.yml \
  -o Global.pretrained_model=pretrain/korean_PP-OCRv5_mobile_rec_pretrained \
     Global.save_model_dir=output/supplement_rec_crawling_v2_clean \
     Global.epoch_num=100 \
     Global.character_dict_path=/workspace/rec_dataset/v2/dict.txt \
     Global.use_space_char=True \
     Optimizer.lr.learning_rate=0.0005 \
     Train.dataset.data_dir=/workspace/rec_dataset/v2 \
     "Train.dataset.label_file_list=['/workspace/rec_dataset/v2/rec/rec_gt_train.txt']" \
     Eval.dataset.data_dir=/workspace/rec_dataset/v2 \
     "Eval.dataset.label_file_list=['/workspace/rec_dataset/v2/rec/rec_gt_val.txt']" \
     Train.loader.batch_size_per_card=128
```

---

## 8. Export and Mac 회수

PaddleOCR inference export가 필요한 경우:

주의: PaddleOCR training checkpoint는 `best_accuracy/` 디렉터리가 아니라 `best_accuracy.pdparams`, `best_accuracy.pdopt`, `best_accuracy.states` 파일 prefix로 저장된다. Export의 `Global.pretrained_model`에는 공식 문서처럼 suffix 없는 `...\best_accuracy` prefix를 넣고, precheck도 `best_accuracy.pdparams` 존재 여부를 확인한다.

```powershell
python tools\export_model.py `
  -c configs\rec\PP-OCRv5\multi_language\korean_PP-OCRv5_mobile_rec.yml `
  -o "Global.pretrained_model=output\supplement_rec_crawling_v2_clean\best_accuracy" `
     "Global.character_dict_path=G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2\dict.txt" `
     "Global.save_inference_dir=output\supplement_rec_crawling_v2_clean\best_accuracy\inference"
```

Mac으로는 inference 모델만 회수한다.

```bash
scp -r 155.230.153.222:'G:/lemon-aid/paddleocr_rec_work/PaddleOCR/output/supplement_rec_crawling_v2_clean/best_accuracy/inference' \
  outputs/generated/supplement-learning/2026-06-05/operator-review/models/supplement_rec_crawling_v2_clean_best_accuracy_inference
```

회수 금지:
- `rec_gt_train.txt`, `rec_gt_val.txt`의 원문 label text를 공개 repo에 추가
- crop image dataset
- provider raw payload
- `.env`, API key, Windows user profile dump

---

## 9. Holdout 평가와 gate

평가는 Mac에서 수행한다. `--rec-model-dir`로 회수한 fine-tuned recognizer를 주입하면 된다.

```bash
./.venv-paddle/bin/python backend/scripts/paddleocr_clova_eval.py \
  --bundle-dir outputs/generated/supplement-learning/2026-06-05/operator-review/ocr-ground-truth-review-bundle \
  --rec-model-dir outputs/generated/supplement-learning/2026-06-05/operator-review/models/supplement_rec_crawling_v2_clean_best_accuracy_inference \
  --det-box-thresh 0.15 --det-thresh 0.1 --det-unclip-ratio 2.0 \
  --output outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/paddleocr-finetuned-crawling-eval.holdout.json \
  --observations-output outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/paddleocr-finetuned-crawling-observations.holdout.jsonl \
  --apply

PYTHONPATH=backend/Nutrition-backend .venv/bin/python backend/scripts/merge_paddleocr_text_observations_into_benchmark.py \
  --benchmark-manifest outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/ocr-benchmark-splits.assignment.json \
  --observations outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/paddleocr-finetuned-crawling-observations.holdout.jsonl \
  --output outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/ocr-benchmark-merged.finetuned-crawling.jsonl

PYTHONPATH=backend/Nutrition-backend .venv/bin/python backend/scripts/build_paddleocr_text_extraction_eval_summary.py \
  --benchmark-manifest outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/ocr-benchmark-merged.finetuned-crawling.jsonl \
  --eval-split holdout --provider paddleocr_local \
  --leakage-check-passed --privacy-review-cleared \
  --output outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/paddleocr-eval-summary.finetuned-crawling.holdout.json

PYTHONPATH=backend/Nutrition-backend .venv/bin/python backend/scripts/gate_paddleocr_text_extraction_target.py \
  --eval-summary outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/paddleocr-eval-summary.finetuned-crawling.holdout.json \
  --min-fixtures 30 \
  --output outputs/generated/supplement-learning/2026-06-05/operator-review/reconciled/paddleocr-text-target-gate.finetuned-crawling.json
```

판정:
- 우선 운영 지표: holdout `field_match_ratio`
- 보조 지표: LCS recall/F1
- 기존 baseline/tuned-det 결과보다 악화되면 backend 적용 금지
- 95% 미달이면 epoch, batch, label noise filtering, ingredient lexicon 보정, dataset expansion을 별도 실험으로 분리한다.

---

## 10. Mac backend 적용

평가만 할 때는 `paddleocr_clova_eval.py --rec-model-dir`로 충분하다.

서비스 fallback provider에 적용할 때는 다음 runtime 설정을 사용한다.

```bash
ENABLE_LOCAL_OCR=true
OCR_PRIMARY_PROVIDER=paddleocr
LOCAL_OCR_LANGUAGE=korean
LOCAL_OCR_MODEL_PROFILE=mobile
LOCAL_OCR_TEXT_RECOGNITION_MODEL_DIR=outputs/generated/supplement-learning/2026-06-05/operator-review/models/supplement_rec_crawling_v2_clean_best_accuracy_inference
```

backend adapter는 이 값을 PaddleOCR 3.x의 `text_recognition_model_dir`로 전달한다. 모델 회수 후에는 먼저 단위 테스트와 holdout gate를 통과시킨 뒤 앱 플로우에 적용한다.

---

## 11. Cleanup

A100에서 학습 후 필요 없어진 private dataset과 teacher label 파일은 운영자 판단에 따라 삭제한다.

```powershell
# 확인 후 수동 삭제. repo에는 절대 추가하지 않는다.
Get-ChildItem G:\lemon-aid\paddleocr_rec_work\rec_dataset\v2
Get-ChildItem G:\lemon-aid\paddleocr_rec_work\PaddleOCR\output\supplement_rec_crawling_v2_clean
```

학습 결과 보고에는 count, metric, checkpoint 존재 여부, digest만 남긴다. raw label text, crop image path, provider payload, secret은 남기지 않는다.
