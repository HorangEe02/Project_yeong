# A100 본학습 — 진행 상태 + 실행 절차 (2026-06-07)

CPU fine-tune로 방향성 검증 완료(실사진 학습 = recall +3~5pt, 무회귀). 95% 도달은 **A100 + 대규모 데이터**가 경로.
이 문서는 A100 본학습의 현재 진행 상태와, A100에서 그대로 실행할 절차다. (전체 가이드: `2026-06-06-a100-remote-paddleocr-finetune-guide.md`)

## 현재 차단점: 이 에이전트는 A100를 원격 실행할 수 없음
- `ssh 155.230.153.222` → **Permission denied (publickey,password,keyboard-interactive)**. 에이전트에 무비밀번호 SSH 미설정.
- 따라서 **실제 A100 학습은 사용자가 VS Code 원격 터미널(또는 직접 SSH)** 에서 실행해야 함. 에이전트는 데이터 준비/검증/명령만 제공.

## 데이터셋 옵션 (둘 중 택1)
| 옵션 | 위치 | 규모 | 비고 |
|---|---|---|---|
| **A (권장)** crawling **v1 (max-6)** | `…/datasets/supplement-paddleocr-rec-crawling/v1` | **train 115,442 / val 12,873 / dict 1,180** (128,315 crop) | **이미 빌드+count gate 통과**, 신규 CLOVA 비용 없음, 데이터 최다 → 95%에 유리 |
| B (가이드 기본) v2 (max-3) | `…/datasets/supplement-paddleocr-rec-crawling/v2` | train 70,778 / val 6,828 / dict 1,066 | 새 CLOVA 패스 필요(유료), Codex `run_a100_..._windows_training.ps1` 기본 카운트와 일치 |

> 권장: **옵션 A(v1, 128K)**. 더 많은 실사진 데이터 = 더 나은 recognizer. count gate 이미 통과:
> `validate_paddleocr_rec_dataset_counts.py --dataset-dir <v1> --expected-train-rows 115442 --expected-val-rows 12873 --expected-dict-rows 1180` → `status: passed`.
> Codex ps1을 쓰려면 v2(max-3)로 맞추거나, ps1의 기대 카운트를 v1 값으로 파라미터화.

## A100 실행 절차 (옵션 A / v1 기준)
1. **전송**(Mac→A100, git 아님 — teacher-text 포함):
   ```bash
   DS="outputs/generated/supplement-learning/2026-06-05/operator-review/datasets/supplement-paddleocr-rec-crawling/v1"
   scp -r "$DS" <user>@155.230.153.222:'C:/Users/lemon-aid/workspace/rec_dataset/v1'
   ```
2. **A100 환경**(PowerShell): py3.12 venv + `paddlepaddle-gpu==3.*`(CUDA에 맞는 인덱스) + `paddleocr==3.6.* paddlex==3.6.* rapidfuzz pillow matplotlib` + `paddlex --install PaddleOCR -y`. (패키징 우회: `repo_manager/repos/` 생성, `repo_apis/PaddleOCR_api/configs/korean_PP-OCRv5_mobile_rec.yaml` 복사 — 가이드 §4 참조.)
3. **count gate**(원문 미출력):
   ```powershell
   python ...\scripts\validate_paddleocr_rec_dataset_counts.py --dataset-dir <v1> `
     --expected-train-rows 115442 --expected-val-rows 12873 --expected-dict-rows 1180 `
     --summary-output count-gate.json   # status=passed 필수
   ```
4. **학습**(GPU, PaddleX — CPU에서 검증된 경로와 동일, device만 gpu):
   ```python
   from paddlex.utils.config import get_config; from paddlex import build_trainer
   cfg=get_config(r"...\configs\modules\text_recognition\korean_PP-OCRv5_mobile_rec.yaml", overrides=[
     "Global.dataset_dir=C:/Users/lemon-aid/workspace/rec_dataset/v1","Global.mode=train",
     "Global.device=gpu:0","Global.output=output/supplement_rec_crawling_v1",
     "Train.epochs_iters=100","Train.batch_size=128","Train.eval_interval=1","Train.save_interval=1"])
   build_trainer(cfg).train()
   ```
   (A100 80GB면 batch 256까지. 멀티-GPU는 Windows 미지원 → 단일 GPU.)
5. **모델 회수 + 재평가**(Mac, 누수 없는 holdout — CPU 평가와 동일 방식):
   ```bash
   ./.venv-paddle/bin/python scripts/paddleocr_clova_eval.py --bundle-dir <BUNDLE> \
     --rec-model-dir <회수한 best_accuracy/inference> \
     --det-box-thresh 0.15 --det-thresh 0.1 --det-unclip-ratio 2.0 \
     --output <eval.json> --observations-output <obs.jsonl> --apply
   # merge → build_paddleocr_text_extraction_eval_summary --eval-split holdout → gate_paddleocr_text_extraction_target --min-fixtures 30
   ```
   **목표**: holdout `field_match_ratio`/recall이 CPU 결과(holdout recall 0.527)를 넘어 **95% 게이트 통과**.

## 기준선 (A100 결과 비교용)
- baseline(mobile, det-튜닝): holdout recall 0.493 / field_match(전체) 0.560.
- CPU fine-tune(realphoto 20ep): holdout recall **0.527** / field_match 0.568. (95% 미달)
- A100 목표: ≥0.95 (95% 게이트 `paddleocr_target_reached=true`).

## 다음 행동
1. (사용자) A100 SSH 키를 에이전트에 등록하거나, VS Code 원격에서 위 절차 실행.
2. v1(128K) 전송 → 학습 → 회수 → Mac에서 재평가/게이트.
3. 게이트 통과 시 모델 promotion(별도 baseline-comparison 게이트) 후 서빙 `--rec-model-dir`/`text_recognition_model_dir` 적용.
