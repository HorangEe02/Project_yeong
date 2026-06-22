# Plan B. ROI 및 촬영 품질 학습 구현 기록

작성일: 2026-05-17

## 목적

Plan B의 v1 목표는 OCR 실행 전에 이미지가 분석 가능한지, 그리고 자동 crop을 적용해도 되는지 판단하는 것이다. 이번 구현은 새 YOLO 모델 학습을 바로 진행하지 않고, 다음 기반을 먼저 만든다.

- deterministic `ImageQualityReport`
- 기존 `BoundingBox` runtime 계약을 유지하는 ROI 품질 integration
- consent-gated ROI training manifest exporter
- product/hash/session split leakage validator
- Ultralytics detection dataset `data.yaml` 및 YOLO label line 생성
- ROI crop 전후 OCR/parser metric 비교용 redacted benchmark harness

## 공식 기준

- Ultralytics train mode: https://docs.ultralytics.com/modes/train/
- Ultralytics detection dataset format: https://docs.ultralytics.com/datasets/detect/
- Ultralytics predict results: https://docs.ultralytics.com/modes/predict/
- OpenCV thresholding primitives: https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html
- OpenCV geometric transforms: https://docs.opencv.org/4.x/da/d6e/tutorial_py_geometric_transformations.html

I cannot find the official documentation for this specific query: supplement-label-specific blur/glare/minimum-text-size thresholds. 따라서 이번 구현의 blur/glare/low-light threshold는 학습 성능 기준이나 제품 차단 기준이 아니라 fixture calibration 전 warning-only heuristic이다.

## 구현된 파일

- `backend/Nutrition-backend/src/models/schemas/image_quality.py`
  - `ImageQualityReport`, `QualityIssue`, `DetectedROI`, `ROITrainingManifestItem`, `ROITrainingManifest` 추가
  - reason code: `blurred_text`, `glare_or_reflection`, `low_light`, `low_contrast`, `too_small_text`, `partial_table`, `cover_only`, `multi_product`, `unsupported_layout`, `roi_not_found`
  - runtime `BoundingBox`는 변경하지 않고, 세분 annotation label은 training manifest에만 둔다.

- `backend/Nutrition-backend/src/services/supplement_image_quality.py`
  - Pillow 기반 deterministic analyzer 추가
  - luminance mean, luminance stddev, glare pixel ratio, edge strength proxy, ROI area ratio, ROI minimum dimension 계산
  - raw image, OCR text, EXIF, 파일명 없이 numeric evidence와 bbox metadata만 반환

- `backend/Nutrition-backend/src/services/supplement_image_analysis.py`
  - OCR pipeline에서 image quality report 생성
  - `roi_not_found`는 원본 OCR fallback 및 review warning으로 degrade
  - `multi_product`, `cover_only`, `partial_table`, `too_small_text`가 있으면 `crop_before_primary`라도 자동 crop을 적용하지 않고 원본 OCR로 degrade
  - preview `parsed_snapshot.image_quality_report`에 redacted report 저장

- `backend/Nutrition-backend/src/vision/base.py`
  - 기존 `detect_label_region()` 계약은 유지
  - 후보 ROI metadata가 필요한 경우를 위해 default `detect_label_regions()` 추가

- `backend/Nutrition-backend/src/vision/yolo.py`
  - YOLO runner의 candidate list를 quality analyzer로 전달할 수 있도록 `detect_label_regions()` 구현

- `backend/Nutrition-backend/src/learning/roi_manifest.py`
  - `evaluate_image_learning_gate()` 통과 시에만 manifest 생성
  - raw image/OCR/credential/user identifier key 차단
  - product group, split group, image hash leakage validator 추가
  - Ultralytics `data.yaml` 및 normalized YOLO label line 생성

- `backend/scripts/export_roi_training_manifest.py`
  - redacted JSON input을 받아 gated ROI manifest, `data.yaml`, YOLO label file export
  - original image/crop copy는 아직 수행하지 않는다. v1은 consent/split/annotation metadata 기반만 확정한다.

- `backend/scripts/evaluate_roi_ocr_impact.py`
  - raw OCR text 없이 original image OCR vs ROI crop OCR의 downstream metric delta 계산
  - metric은 field exact match, numeric exact match, unit exact match, parser success 중심

## Phase별 완료 상태

### B0. Taxonomy and Schemas

완료.

- 품질 상태: `acceptable`, `needs_review`, `retake_recommended`, `blocked`
- 품질 issue 및 evidence schema 추가
- runtime ROI와 training annotation label 분리

### B1. Deterministic Quality Analyzer

완료.

- blur proxy, brightness, contrast, glare ratio, ROI area ratio, ROI size 계산
- threshold는 warning-only heuristic
- 성분/함량 추정은 수행하지 않음

### B2. ROI Runtime Integration

완료.

- `YoloLabelDetector -> select_best_label_region -> crop_image_to_bounding_box` 흐름 유지
- 후보 ROI 목록은 품질 판단 metadata로만 사용
- risky ROI는 자동 crop 대신 원본 OCR fallback
- `crop_before_primary` 설정 gate 유지

### B3. Consent-Gated Dataset Export

완료.

- image learning gate 통과 시에만 manifest export
- forbidden raw field 검사
- manifest에는 bbox, quality issue, hash, split group만 포함

### B4. Annotation and Split Validation

부분 완료.

- class map version은 schema tuple로 고정
- split leakage validator 구현
- annotation guideline 자체 문서는 별도 후속 문서로 분리 필요

### B5. YOLO Dataset Conversion and Training Runbook

부분 완료.

- `data.yaml` 및 YOLO label file 생성 구현
- 실제 training command, model artifact checksum 기록 자동화는 후속 단계

### B6. ROI Impact Benchmark

부분 완료.

- redacted metric manifest evaluator 구현
- 실제 OCR provider를 호출하는 benchmark runner는 후속 fixture 고정 후 진행

## 테스트 범위

- image quality analyzer reason code
- ROI fallback warning
- multi-product candidate에서 자동 crop degrade
- consent gate 미통과 시 manifest export 차단
- product/hash split leakage 탐지
- Ultralytics `data.yaml` 및 YOLO label line 생성
- ROI impact metric delta 계산
- raw OCR/image field 차단

## 남은 작업

- fixture 기반 blur/glare/low-light threshold calibration
- annotation guideline 문서화
- 실제 image/crop object export는 storage retention policy 확정 후 추가
- Ultralytics training runbook과 artifact checksum 기록 자동화
- ROI crop 전후 Google Vision/PaddleOCR/parser 결과 비교 fixture 고정
