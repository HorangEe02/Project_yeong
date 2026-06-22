# 2026-06-02 다음 작업 TODO

## 1. Annotation Review 승인 결과를 Dataset Item으로 승격

- 현재 `import_annotation_review.py`는 review 결과를 `AnnotationTask.status`와 `label_snapshot`에 반영한다.
- `export_training_manifest.py`는 `LearningDatasetItem`만 읽기 때문에 accepted `AnnotationTask`를 training dataset item으로 승격하는 단계가 아직 필요하다.
- 다음 구현 방향:
  - accepted `supplement_roi_box` task만 조회한다.
  - `coordinate_space=source_image`, `human_review_required=false`, `training_export_allowed=true` snapshot만 허용한다.
  - source는 `media_object_id` 또는 `learning_image_object_id` 중 하나만 허용한다.
  - 생성되는 `LearningDatasetItem.task_type`은 export 계약에 맞춰 `yolo_detection`으로 저장한다.
  - operator summary에는 source id, owner hash, raw label text를 출력하지 않는다.

## 2. Human-reviewed Supplement Section Annotation 준비

- OCR layout 후보는 training export에 바로 쓰면 안 된다.
- reviewer가 실제 원본 이미지 좌표 기준으로 bbox를 검수해야 한다.
- 검수 대상 label은 다음 4개 section class로 제한한다.
  - `supplement_facts`
  - `precautions`
  - `intake_method`
  - `ingredients`

## 3. YOLO26 Custom Supplement Detector 학습

- 현재 repo에서 확인된 `.pt`는 음식 YOLO 실험 모델이며 supplement section detector로 사용할 수 없다.
- human-reviewed image/label 파일이 준비되면 `data/supplement_images/section_yolo/dataset.yaml` 기준으로 Ultralytics YOLO26 학습을 진행한다.
- 학습 전 validator는 class contract와 file-level annotation 검증을 모두 통과해야 한다.

## 4. Crop OCR 및 Gemma/Ollama Verification 연결

- YOLO section bbox별 crop OCR을 수행해 `supplement_facts`, `precautions`, `intake_method`, `ingredients`를 분리 추출한다.
- 전체 이미지 OCR fallback은 필수 section이 비었을 때만 사용한다.
- Ollama/Gemma vision verification은 OCR 텍스트가 실제 이미지 ROI에 존재하는지 structured output으로 검증한다.
- text-to-text LLM 설명은 사용자 건강 프로필/질환/복약 context를 opt-in gate 뒤에만 사용한다.

## 5. 모바일 결과 UI 후속

- 기술 카드 중심 UI는 최종 사용자에게 노출하지 않는다.
- 결과 화면은 영양제명, 상세 성분 및 함량, 섭취 방법, 섭취 시 주의사항 4개 정보 카드 중심으로 유지한다.
- 누락 section은 해당 카드 내부에서 재촬영 안내를 보여준다.
- 멀티비타민처럼 성분이 여러 개인 경우 checkbox 기반 선택/편집 UI가 필요하다.

## 6. 계속 지켜야 할 Git/보안 규칙

- 팀 repo root와 remote를 확인한 뒤 stage/commit/push한다.
- `origin`만 push 대상으로 사용하고 `personal` remote는 사용하지 않는다.
- commit message는 Conventional Commits 형식으로 작성한다.
- body에는 `Why`, `Constraint`, `Tested`를 포함한다.
- raw OCR, provider payload, image path, object URI, owner hash, secrets는 문서/로그/API 응답에 포함하지 않는다.
