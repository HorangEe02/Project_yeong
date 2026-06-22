# 2026-06-02 AnnotationTask learning image source 연결 구현

> 작성 기준: 2026-06-02
> 범위: consent-gated learning image source를 supplement section annotation queue에 연결

---

## 1. 구현 목적

OCR layout에서 나온 영양제 섹션 후보 bbox를 바로 YOLO26 학습에 넣지 않고, 사람이 원본 이미지 기준으로 검수할 수 있는 `AnnotationTask`로 먼저 보낸다.

기존에는 `AnnotationTask`가 `media_object_id`만 참조할 수 있었다. 하지만 supplement analysis flow에서 실제로 저장 가능한 원본 이미지 source는 learning consent gate를 통과한 `LearningImageObject`이므로, 이번 구현에서 `AnnotationTask.learning_image_object_id`를 추가했다.

---

## 2. 코드 변경

### DB migration

추가 파일:

- `backend/alembic/versions/0026_add_annotation_task_learning_image_source.py`

추가 내용:

- `annotation_tasks.learning_image_object_id` nullable UUID column
- `learning_image_objects.id` FK, `ondelete="SET NULL"`
- `ix_annotation_tasks_learning_image_object_id` index

### ORM

수정 파일:

- `backend/Nutrition-backend/src/models/db/retraining.py`

변경 내용:

- `AnnotationTask.learning_image_object_id` 추가
- annotation task index 목록에 learning image source index 추가
- docstring에 source lineage 의미 추가

### OCR section task factory

수정 파일:

- `backend/Nutrition-backend/src/learning/supplement_section_labels.py`

변경 내용:

- `build_supplement_section_annotation_task(...)`가 `media_object_id` 또는 `learning_image_object_id` 중 하나를 받도록 확장
- 둘 다 없거나 둘 다 있으면 `SupplementSectionLabelCandidateError`로 거부
- source id는 model column에만 저장하고 `label_snapshot`에는 넣지 않음

### supplement analysis service

수정 파일:

- `backend/Nutrition-backend/src/services/supplement_image_analysis.py`

변경 내용:

- learning consent gate가 열려 `LearningImageObject`가 생성 또는 재사용된 경우에만 annotation task enqueue 시도
- OCR layout이 safe section candidate를 만들 수 있을 때만 pending task 생성
- 같은 `learning_image_object_id`, `task_type`, `review_notes_code`에 active task가 있으면 중복 생성하지 않음
- enqueue 실패는 optional learning path로 처리하고 분석 결과 자체는 실패시키지 않음
- 결과 dataclass에 `annotation_task_created` flag 추가

### privacy scrubber

수정 파일:

- `backend/Nutrition-backend/src/services/privacy.py`

변경 내용:

- revoke/delete-all에서 `AnnotationTask.learning_image_object_id`도 `None`으로 scrub
- 기존처럼 label snapshot, reviewer hash, review note도 제거

---

## 3. 개인정보/보안 규칙

이번 구현에서도 아래 값은 annotation snapshot에 저장하지 않는다.

- raw OCR text
- provider payload
- object URI
- image path
- owner subject
- owner hash
- source id

`learning_image_object_id`는 DB column으로만 보관한다. reviewer task source resolution은 backend/operator-only path에서 처리해야 한다.

---

## 4. 검증 결과

```bash
cd backend
.venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/learning/test_supplement_section_labels.py \
  Nutrition-backend/tests/unit/learning/test_retraining.py \
  Nutrition-backend/tests/unit/db/test_models.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_privacy.py
.venv/bin/python -m ruff check \
  Nutrition-backend/src/models/db/retraining.py \
  Nutrition-backend/src/learning/supplement_section_labels.py \
  Nutrition-backend/src/services/privacy.py \
  Nutrition-backend/src/services/supplement_image_analysis.py \
  Nutrition-backend/tests/unit/learning/test_supplement_section_labels.py \
  Nutrition-backend/tests/unit/learning/test_retraining.py \
  Nutrition-backend/tests/unit/db/test_models.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_privacy.py
```

결과:

```text
76 passed
All checks passed!
```

검증한 내용:

- OCR layout 후보 task가 learning image source를 참조할 수 있다.
- source id는 label snapshot에 저장되지 않는다.
- source가 없거나 ambiguous하면 task factory가 거부한다.
- active annotation task가 이미 있으면 중복 생성하지 않는다.
- delete-all/revoke scrubber가 `learning_image_object_id`까지 제거한다.

---

## 5. 다음 작업

1. reviewer가 accepted 처리한 `AnnotationTask`를 `LearningDatasetItem`으로 승격하는 worker를 추가한다.
2. accepted snapshot은 `coordinate_space="source_image"`, `human_review_required=false`, `training_export_allowed=true`인 경우에만 승격한다.
3. 승격된 dataset item을 기존 supplement section YOLO export bridge에 연결한다.
4. materializer로 실제 `images/labels` directory를 생성한 뒤 `--require-files` validator를 통과시킨다.
5. YOLO26 custom detector 학습 후 crop OCR, full-image fallback OCR, Ollama/Gemma vision verification을 비교한다.

---

## 6. 참고 공식 문서

- SQLAlchemy ORM mapped columns and foreign keys: <https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html>
- Alembic operation directives: <https://alembic.sqlalchemy.org/en/latest/api/operations.html>
- Ultralytics object detection dataset format: <https://docs.ultralytics.com/datasets/detect/>
- Ollama structured outputs: <https://docs.ollama.com/capabilities/structured-outputs>
