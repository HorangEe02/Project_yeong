# 2026-06-02 AnnotationTask Dataset Promotion 구현 요약

## 목적

- OCR layout 기반 section 후보는 검수 전에는 YOLO 학습 데이터로 사용할 수 없다.
- reviewer가 source image 좌표 기준으로 승인한 `AnnotationTask`를 실제 training manifest가 읽는 `LearningDatasetItem`으로 승격하는 operator 단계를 추가했다.
- 이 단계가 있어야 `supplement_section_yolo_detection` export와 materializer가 reviewer-approved bbox만 사용해 YOLO26 custom supplement section detector 학습으로 이어질 수 있다.

## 구현 내용

### Public validation helper

- `src.learning.retraining.validate_supplement_section_training_label_snapshot` 추가
- 검증 기준:
  - raw OCR/provider payload/path/URL/secret-like value 금지
  - `training_export_allowed=false`이면 거부
  - `human_review_required=true`이면 거부
  - `coordinate_space`가 있으면 `source_image`만 허용
  - `supplement_facts`, `precautions`, `intake_method`, `ingredients`로 normalize 가능한 bbox만 허용

### Operator promotion CLI

- 신규 파일: `backend/scripts/promote_annotation_tasks_to_dataset.py`
- 입력:
  - `--dataset-version-id`
  - `--split train|val|test|holdout`
  - `--limit`
- 처리:
  - accepted `supplement_roi_box` task만 조회
  - target dataset은 `supplement_roi_detection`만 허용
  - `media_object_id` 또는 `learning_image_object_id` 중 정확히 하나의 live source가 있어야 함
  - label snapshot을 deterministic JSON으로 정규화하고 SHA-256 `label_hash` 생성
  - 중복 dataset item이 있으면 skip
  - 생성 dataset item은 `source_domain=supplement`, `task_type=yolo_detection`, `label_status=human_reviewed`로 저장

### Privacy 출력 기준

- CLI summary는 다음 값을 출력하지 않는다.
  - source id/source ref
  - owner hash
  - label snapshot 또는 bbox label
  - raw OCR/provider payload
  - local image path/object URI
- summary에는 count와 flag만 남긴다.

## 테스트

- `test_promote_annotation_tasks_to_dataset.py` 추가
- 검증 항목:
  - accepted learning image task promotion
  - accepted media task promotion
  - unapproved OCR-page candidate rejection
  - duplicate item skip
  - missing/ambiguous source skip
  - CLI stdout redaction

## 실행한 검증

```bash
cd backend && .venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/scripts/test_promote_annotation_tasks_to_dataset.py \
  Nutrition-backend/tests/unit/scripts/test_import_annotation_review.py \
  Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py \
  Nutrition-backend/tests/unit/learning/test_retraining.py
```

- 결과: `30 passed`

```bash
cd backend && .venv/bin/python -m ruff check \
  Nutrition-backend/src/learning/retraining.py \
  scripts/promote_annotation_tasks_to_dataset.py \
  Nutrition-backend/tests/unit/scripts/test_promote_annotation_tasks_to_dataset.py
```

- 결과: `All checks passed!`

## 다음 작업

- 실제 reviewer JSONL import 후 promotion CLI를 operator 환경에서 dry-run/runbook 형태로 연결한다.
- promoted dataset item을 `export_training_manifest.py --export-kind supplement_section_yolo_detection`로 export한다.
- materializer로 image/label 디렉터리를 만들고 dataset validator `--require-files`를 통과시킨다.
- 이후 Ultralytics YOLO26 custom model 학습, crop OCR, Gemma/Ollama verification을 이어간다.
