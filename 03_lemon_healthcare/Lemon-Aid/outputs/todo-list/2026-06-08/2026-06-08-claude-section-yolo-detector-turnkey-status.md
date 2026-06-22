# 2026-06-08 Claude Section YOLO Detector Turnkey Status

## Summary

Claude 섹션에서 진행된 작업은 "성분표 섹션 검출기" 학습 직전 단계까지 검증된 상태다. Label Studio 수동 박스 export를 기반으로 Stage 3 변환 체인이 통과했고, A100 서버에는 YOLO 학습용 데이터셋이 전송되어 있다.

현재 목표는 recognizer 재학습이 아니라 section detector 기반 ROI-first 평가로 0.90 target에 접근하는 것이다. 병목 후보는 OCR recognizer보다 crop/ROI/detection/GT 평가 구조 쪽으로 보고 있다.

## Verified Inputs

- Label Studio export: `/Users/yeong/Downloads/project-3-at-2026-06-08-07-16-825104e9.json`
- 총 task: 307
- reviewed task: 307
- box 포함 task: 305
- 총 box: 3,530
- class 수: 8

| Label | Count |
| --- | ---: |
| ingredient_amounts | 1,280 |
| supplement_facts | 880 |
| product_identity | 491 |
| functional_claims | 352 |
| precautions | 230 |
| intake_method | 142 |
| allergen_warning | 139 |
| other_ingredients | 16 |

Claude 화면의 중간 요약에는 `303 tasks / 3,507 boxes`가 보였지만, 로컬 JSON 재검사 기준 최종 확인값은 `305 tasks with boxes / 3,530 boxes`다.

## Completed Pipeline

검증된 체인:

```text
Label Studio export
-> convert
-> extract reviewed annotations
-> inject_v2_split_into_promote_template
-> strict preflight
-> promote
-> materialize YOLO dataset
-> validate
-> section YOLO dataset gate
```

최종 gate summary:

| Gate Item | Value |
| --- | --- |
| strict preflight | ready |
| materialize | ok |
| validate | ok |
| gate status | ready_for_section_yolo_training_dataset |
| training_allowed_now | true |
| train / val / test | 216 / 32 / 57 |
| image_count / label_count | 305 / 305 |

관련 커밋:

- `a7716c2a` - Stage 3 체인 real boxes 검증 및 partial gate block 기록
- `084cdb6f` - split-carry fix 및 real-box 기준 YOLO gate pass 기록

## A100 Current State

원격 확인 시각: `2026-06-08 17:08 KST`

- Dataset path: `G:\lemon-aid\section_dataset_v2`
- `dataset.yaml` 존재
- split count:
  - train images/labels: 216 / 216
  - val images/labels: 32 / 32
  - test images/labels: 57 / 57
- `train.err`: 0 bytes
- top-level `G:\lemon-aid\train_log.txt`는 YOLO 학습 로그를 계속 갱신 중이다.
- GPU 상태는 매우 혼잡하다.
  - A100 80GB 중 약 72.7GB 사용
  - GPU util 100%
  - 여러 Python 학습 프로세스가 동시에 VRAM을 사용 중

주의: A100에 공간이 없어서 막힌 상태로 보이지는 않는다. 현재 주요 제약은 디스크보다 GPU/VRAM 경합과 실행 큐/동시 학습 부하다.

## Risks And Cautions

- raw image, Label Studio 원본 export, crop dataset, teacher OCR payload, provider payload는 git에 올리지 않는다.
- `outputs/generated/...` 아래에는 현재 많은 생성물이 dirty 상태이므로, 커밋 전 반드시 staging 대상을 좁혀야 한다.
- split-carry가 핵심 안전장치다. 이후 큰 export에도 `v2_split -> promote-template split` 전달을 유지해야 product-level leakage를 막을 수 있다.
- 현재 `promote-template.jsonl.summary.json` 같은 일부 중간 summary는 split injection 전 상태를 반영할 수 있다. 최종 판단은 strict preflight, materialize, validate, gate summary를 함께 확인한다.
- A100은 공유 GPU 환경이라 학습이 느리거나 대기/경합 상태가 생길 수 있다. 로그 tail과 `best.pt` 생성 여부를 기준으로 판단한다.

## Todo

1. A100에서 section detector 학습 로그를 모니터링한다.
   - 확인 대상: `G:\lemon-aid\train_log.txt`, `G:\lemon-aid\train_err.txt`, 관련 YOLO run directory, `best.pt`.
   - 실패 기준: traceback, CUDA OOM, dataset path error, label count mismatch, no-label warning.

2. 학습 완료 후 최소 산출물만 Mac으로 회수한다.
   - 회수 대상: `best.pt`, `results.csv`, `args.yaml`, 필요한 경우 `confusion_matrix`/metrics image.
   - 회수 제외: 원본 이미지, 전체 라벨셋, teacher/provider payload.

3. detector 기반 ROI-first holdout 평가를 실행한다.
   - `best.pt`로 holdout 52장에 대해 section box 추론.
   - 추론 box에서 ROI crop 생성.
   - 기존 PaddleOCR recognizer 또는 현재 best recognizer로 crop OCR 실행.
   - full-image baseline과 detector-ROI-first 결과를 같은 metric contract로 비교.

4. 0.90 target gate를 다시 계산한다.
   - field-level F1/recall, LCS recall, formal gate JSON 생성.
   - 0.90 미달이면 실패 원인을 section miss, wrong class, crop boundary, OCR residual, GT/eval mismatch로 분해한다.

5. 실패 분석용 샘플셋을 만든다.
   - false negative section
   - wrong label section
   - ingredient_amounts crop under/over-boundary
   - OCR text는 원문 노출 없이 redacted/sanitized summary로만 저장한다.

6. 필요 시 학습 데이터 보강 루프를 진행한다.
   - 현재 305장/3,530 boxes는 trainable set이다.
   - 0.90에 못 미치면 `ingredient_amounts`, `intake_method`, `other_ingredients` 중심으로 추가 annotation 또는 label quality audit를 우선한다.

7. Git 정리 전 private artifact 방지 점검을 수행한다.
   - `.gitignore`와 `git status --short` 확인.
   - commit 대상은 scripts/docs/sanitized summaries만 허용.
   - raw exports, images, labels, OCR payload는 stage하지 않는다.

## Official References

- Ultralytics train mode: https://docs.ultralytics.com/modes/train/
- Ultralytics detection dataset YAML: https://docs.ultralytics.com/datasets/detect/
- Label Studio export annotations: https://labelstud.io/guide/export.html
- PaddleOCR text recognition training/export: https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html
