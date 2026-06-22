# 2026-06-02 Supplement section annotation review guard 구현

> 작성 기준: 2026-06-02
> 범위: OCR layout 기반 YOLO section 후보를 human review 계약으로 고정하고, 검수 전 training export를 차단

---

## 1. 구현 배경

이전 단계에서 OCR layout의 semantic section bbox를 YOLO normalized label snapshot으로 변환했다.

하지만 해당 snapshot은 OCR layout에서 자동 생성한 후보이므로 바로 YOLO26 학습 데이터로 쓰면 안 된다. 특히 crop 기준 좌표인지 원본 이미지 기준 좌표인지가 검증되지 않은 상태라, 사람 검수 없이 export되면 잘못된 bbox가 학습될 수 있다.

이번 구현의 목적은 다음 두 가지다.

- OCR layout 후보를 `AnnotationTask`로 보낼 수 있는 안전한 task factory 제공
- `training_export_allowed=false` 또는 `human_review_required=true`인 후보 snapshot이 supplement section YOLO export로 들어가지 못하게 차단

---

## 2. 코드 변경

### `supplement_section_labels.py`

추가한 계약:

- `candidate_source="ocr_layout"`
- `coordinate_space="ocr_page"`
- `human_review_required=true`
- `training_export_allowed=false`
- `text_stored=false`

추가한 helper:

- `build_supplement_section_annotation_task`
  - `task_type="supplement_roi_box"`
  - `status="pending"`
  - `assignee_role="data_reviewer"`
  - `review_notes_code="ocr_layout_section_candidate"`
  - `label_snapshot`에는 raw OCR text, provider payload, media id, owner hash를 넣지 않음

보호 조건:

- `owner_subject_hash`는 64자 SHA-256 hex만 허용한다.
- raw owner subject(`issuer::subject`)는 거부한다.
- page size가 없거나 trainable section이 없으면 기존처럼 fail-closed 처리한다.

### `retraining.py`

`build_supplement_section_yolo_detection_export` 전에 다음 조건을 확인한다.

- `training_export_allowed is False`면 export 거부
- `human_review_required is True`면 export 거부
- `coordinate_space`가 존재하는데 `source_image`가 아니면 export 거부

따라서 OCR layout 후보는 review import에서 사람이 승인해도, 좌표계를 `source_image`로 확인하고 `training_export_allowed=true`로 바꾸기 전까지 학습 export로 넘어가지 않는다.

---

## 3. 검증 결과

```bash
cd backend
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/learning/test_supplement_section_labels.py Nutrition-backend/tests/unit/learning/test_retraining.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py
.venv/bin/python -m ruff check Nutrition-backend/src/learning/supplement_section_labels.py Nutrition-backend/src/learning/retraining.py Nutrition-backend/tests/unit/learning/test_supplement_section_labels.py Nutrition-backend/tests/unit/learning/test_retraining.py
```

결과:

```text
27 passed
All checks passed!
```

검증한 내용:

- OCR layout 후보 snapshot에는 raw OCR text가 저장되지 않는다.
- OCR layout 후보 snapshot은 `training_export_allowed=false` 상태로 생성된다.
- pending `AnnotationTask`는 sanitized label snapshot만 가진다.
- raw owner subject는 annotation task 생성에서 거부된다.
- unapproved candidate snapshot은 human_reviewed 상태로 manifest에 들어와도 supplement section YOLO export에서 거부된다.
- source image 좌표로 검수되지 않은 bbox는 export에서 거부된다.
- reviewer-approved snapshot은 기존 supplement section YOLO export bridge를 통과한다.

---

## 4. 확인한 한계

현재 `SupplementAnalysisRun`은 기본 intake 경로에서 image hash/metadata만 저장하고, `AnnotationTask.media_object_id`가 참조하는 `MediaObject`를 항상 만들지는 않는다.

따라서 분석 직후 자동으로 `AnnotationTask`를 DB에 insert하려면 먼저 아래 중 하나가 필요하다.

1. supplement analysis upload 단계에서 consent-gated `MediaObject`를 생성하고 analysis run과 연결
2. 기존 `LearningImageObject`를 annotation task source로 참조할 수 있도록 schema 확장
3. 별도 operator-only source map을 통해 task source를 안전하게 resolve하는 worker 경로 추가

원본 이미지를 찾을 수 없는 annotation task를 만들면 검수자가 bbox를 확인할 수 없으므로 이번 커밋에서는 service insert까지 진행하지 않았다.

---

## 5. 다음 작업

1. retained media source를 `SupplementAnalysisRun` 또는 `AnnotationTask`와 연결하는 schema/service 설계를 확정한다.
2. learning consent가 열린 경우에만 원본 이미지 source를 review queue에 연결한다.
3. `AnnotationTask` accepted snapshot을 `LearningDatasetItem`으로 승격하는 worker를 추가한다.
4. reviewer가 승인한 snapshot은 `coordinate_space="source_image"`, `human_review_required=false`, `training_export_allowed=true`로 저장한다.
5. materializer와 `--require-files` validator를 실제 image/label 파일로 통과시킨다.
6. YOLO26 custom supplement section detector 학습 후 crop OCR, 전체 이미지 OCR fallback, Ollama/Gemma vision verification을 비교한다.

---

## 6. 참고 공식 문서

- Ultralytics detect dataset: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics train mode: <https://docs.ultralytics.com/modes/train/>
- Ultralytics YOLO26: <https://docs.ultralytics.com/models/yolo26/>
- Ollama structured outputs: <https://docs.ollama.com/capabilities/structured-outputs>
- Ollama generate API: <https://docs.ollama.com/api/generate>
