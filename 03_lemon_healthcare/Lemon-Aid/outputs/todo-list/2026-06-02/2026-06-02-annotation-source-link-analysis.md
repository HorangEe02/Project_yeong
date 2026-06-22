# 2026-06-02 Annotation source 연결 분석 및 다음 구현 기준

> 작성 기준: 2026-06-02
> 범위: supplement section YOLO 후보를 실제 검수 queue에 넣기 전 원본 이미지 source 연결 구조 확인

---

## 1. 이번 섹션에서 확인한 내용

OCR layout 기반 `supplement_facts`, `precautions`, `intake_method`, `ingredients` 후보 bbox는 이미 sanitized `AnnotationTask` 후보로 만들 수 있다.

하지만 실제 DB insert는 보류했다. 이유는 검수자가 원본 이미지를 볼 수 있는 source reference가 아직 안전하게 연결되지 않았기 때문이다.

현재 확인한 저장 구조는 아래와 같다.

- `MediaObjectStore`
  - `delete_object` 전용 인터페이스다.
  - `put_image` 또는 `get_image`가 없다.
  - 따라서 supplement 분석 직후 새 `MediaObject`를 생성하는 경로가 현재 코드에 없다.

- `LearningImageObjectStore`
  - `put_image`, `get_image`, `delete_image`를 모두 제공한다.
  - `maybe_store_learning_image_object(...)`가 learning consent gate를 통과한 이미지에 대해서만 저장한다.
  - 저장 row는 `learning_image_objects`이며, raw image bytes는 DB에 저장하지 않고 private object reference만 저장한다.

- `LearningDatasetItem`
  - `media_object_id`와 `learning_image_object_id`를 모두 가질 수 있다.
  - 이미 학습 데이터 lineage에서 두 source 계열을 모두 고려하도록 설계되어 있다.

- `AnnotationTask`
  - 현재는 `media_object_id`만 가진다.
  - `learning_image_object_id`가 없어서, 기존 learning image object를 검수 task source로 직접 참조할 수 없다.

---

## 2. 왜 바로 수정하지 않았는가

검수 task는 bbox 후보만으로는 충분하지 않다. reviewer가 원본 이미지 위에서 bbox를 확인하고 좌표계를 `source_image` 기준으로 확정해야 한다.

따라서 source가 없는 task를 생성하면 아래 문제가 생긴다.

- reviewer가 어떤 이미지의 bbox인지 확인할 수 없다.
- OCR page 좌표와 원본 이미지 좌표를 혼동할 수 있다.
- 잘못된 bbox가 `human_reviewed`로 승격될 위험이 생긴다.
- 이후 YOLO26 학습 데이터가 오염될 수 있다.

이번 단계에서는 자동 OCR 후보 snapshot에 아래 guard를 붙였다.

- `candidate_source="ocr_layout"`
- `coordinate_space="ocr_page"`
- `human_review_required=true`
- `training_export_allowed=false`

이 후보는 사람이 원본 이미지 기준으로 승인하기 전까지 training export로 넘어갈 수 없다.

---

## 3. 다음 구현 선택지

### 선택지 A: `MediaObjectStore`에 write path 추가

supplement analysis upload 단계에서 `MediaObject`를 생성하고 `AnnotationTask.media_object_id`와 연결한다.

장점:

- `AnnotationTask` 기존 schema를 크게 바꾸지 않아도 된다.
- backend-only media table의 RLS/read policy와 맞출 수 있다.

주의점:

- `MediaObjectStore`가 현재 deletion-only이므로 `put_image` 계약, storage key, metadata scrubber, retention 정책을 새로 설계해야 한다.
- `SupplementAnalysisRun`과 `MediaObject` 연결 컬럼 또는 evidence 연결 흐름을 정리해야 한다.

### 선택지 B: `AnnotationTask.learning_image_object_id` 추가

기존 consent-gated `LearningImageObject`를 annotation source로 참조할 수 있도록 `AnnotationTask` schema를 확장한다.

장점:

- 이미 존재하는 `LearningImageObjectStore.put_image`와 learning consent gate를 재사용할 수 있다.
- `LearningDatasetItem`이 이미 `learning_image_object_id`를 지원하므로 downstream lineage와 자연스럽게 이어진다.

주의점:

- migration, ORM, privacy revoke/delete-all scrubber, tests를 함께 수정해야 한다.
- `media_object_id`와 `learning_image_object_id` 중 최소 하나가 있는지 Python/service guard를 둬야 한다.
- task snapshot에는 source id를 넣지 않고 모델 컬럼으로만 보관해야 한다.

### 현재 판단

다음 구현에서는 선택지 B가 더 작고 일관적이다.

이미 supplement analysis flow는 `maybe_store_learning_image_object(...)`를 호출하고 있고, 이 함수는 owner hash, analysis id, image hash, retention, consent snapshot을 기준으로 중복 저장도 방지한다.

따라서 다음 단계는 `AnnotationTask.learning_image_object_id`를 추가한 뒤, learning image object가 생성 또는 재사용된 경우에만 pending review task를 생성하는 방향이 가장 안전하다.

---

## 4. 다음 작업 순서

1. Alembic migration으로 `annotation_tasks.learning_image_object_id` nullable FK를 추가한다.
2. `AnnotationTask` ORM과 privacy scrubber에 `learning_image_object_id`를 추가한다.
3. `build_supplement_section_annotation_task(...)`가 `media_object_id` 또는 `learning_image_object_id` 중 하나를 받도록 확장한다.
4. 두 source id가 모두 없으면 task 생성 자체를 거부한다.
5. label snapshot에는 raw OCR text, provider payload, object URI, image path, source id를 넣지 않는다.
6. `maybe_store_learning_image_object(...)` 결과가 있을 때만 supplement analysis service에서 pending task를 enqueue한다.
7. 같은 learning image object와 task type에 대해 중복 pending task가 생기지 않도록 조회 guard를 둔다.
8. human-reviewed task를 `LearningDatasetItem`으로 승격하는 worker에서 `learning_image_object_id` lineage를 유지한다.

---

## 5. 검증 기준

다음 구현 후 최소 검증:

```bash
cd backend
.venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/learning/test_supplement_section_labels.py \
  Nutrition-backend/tests/unit/learning/test_retraining.py \
  Nutrition-backend/tests/unit/services/test_privacy.py
.venv/bin/python -m ruff check \
  Nutrition-backend/src/models/db/retraining.py \
  Nutrition-backend/src/services/privacy.py \
  Nutrition-backend/src/learning/supplement_section_labels.py
```

추가로 service enqueue까지 구현하면 supplement image analysis service test를 포함한다.

```bash
cd backend
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py
```

---

## 6. 남은 blocker

- 실제 human-reviewed section bbox annotation은 아직 없다.
- `data/supplement_images/section_yolo/dataset.yaml`은 class 계약만 준비된 상태다.
- 실제 YOLO26 custom supplement section detector 학습은 annotation image/label materialize 이후 진행해야 한다.
- crop OCR, full-image OCR fallback, Ollama/Gemma vision verification live smoke는 custom detector가 준비된 뒤 비교한다.

---

## 7. 개인정보/보안 규칙

- raw OCR text와 provider payload는 annotation snapshot에 저장하지 않는다.
- object URI, source image path, owner subject, owner hash는 snapshot과 operator-facing output에 노출하지 않는다.
- consent gate가 닫혀 있으면 learning image object와 annotation task를 만들지 않는다.
- delete-all/revoke flow에서는 dataset item과 annotation task의 source id와 label snapshot을 scrub한다.
