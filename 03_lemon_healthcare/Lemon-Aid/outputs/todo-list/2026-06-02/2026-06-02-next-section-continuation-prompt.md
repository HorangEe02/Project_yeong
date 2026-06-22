# 2026-06-02 다음 섹션 이어서 작업 프롬프트

아래 프롬프트는 다음 Codex 섹션에서 그대로 이어서 사용할 수 있도록 작성했다.

---

## 이어서 진행할 작업

현재 Lemon-Aid repo에서 OCR layout 기반 supplement section YOLO 후보 snapshot까지 구현되어 있다.

repo:

```text
/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid
```

실제 Git root:

```text
/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid
```

현재 브랜치:

```text
docs/docs-2026-05-31-backend-ocr-security
```

remote:

```text
origin = https://github.com/Lemon-Aid-KDT/Lemon-sin.git
```

`personal` remote는 사용하지 않는다.

---

## 완료된 구현

- OCR layout parser에서 주의사항/알레르기 문구를 `precautions` evidence로 분류한다.
- `1회 제공량(26g)` / `Serving Size` / `Amount Per Serving` 계열은 성분 후보에서 제외한다.
- supplement section YOLO class 계약은 아래 4개로 고정했다.

```text
0: supplement_facts
1: precautions
2: intake_method
3: ingredients
```

- `data/supplement_images/section_yolo/dataset.yaml`과 validator를 추가했다.
- Ultralytics runner는 model class names가 위 section taxonomy를 만족하지 않으면 fail-closed 처리한다.
- privacy-reviewed annotation manifest를 `supplement_section_yolo_detection` export로 변환하는 bridge를 추가했다.
- export artifact와 operator-only source map을 실제 `images/{split}`, `labels/{split}` 구조로 변환하는 materializer를 추가했다.
- `build_supplement_section_yolo_label_snapshot`은 OCR layout absolute bbox를 raw OCR text 없이 normalized YOLO label 후보 snapshot으로 변환한다.

---

## 다음 구현 순서

1. `AnnotationTask` 모델을 사용해 OCR layout 기반 section bbox 후보를 operator review queue에 넣는다.
2. `task_type='supplement_roi_box'`, `status='pending'`, `assignee_role='data_reviewer'`로 생성한다.
3. `label_snapshot`에는 bbox, schema version, `text_stored=false`, `candidate_source='ocr_layout'`, `training_export_allowed=false`, `human_review_required=true`만 넣는다.
4. raw OCR, provider payload, image path, source ref, owner hash, user id는 snapshot에 넣지 않는다.
5. 후보 snapshot이 실수로 학습 export에 들어가지 않도록 `training_export_allowed=false`면 export bridge가 거부하도록 guard를 추가한다.
6. 사람이 검수한 snapshot만 `training_export_allowed=true`로 바꾸고 `LearningDatasetItem.label_status='human_reviewed'`가 된 뒤 export되도록 한다.
7. 단위 테스트는 `test_supplement_section_labels.py`와 `test_retraining.py`에 추가한다.

---

## 검증 명령

```bash
cd backend
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/learning/test_supplement_section_labels.py Nutrition-backend/tests/unit/learning/test_retraining.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py
.venv/bin/python -m ruff check Nutrition-backend/src/learning/supplement_section_labels.py Nutrition-backend/src/learning/retraining.py Nutrition-backend/tests/unit/learning/test_supplement_section_labels.py Nutrition-backend/tests/unit/learning/test_retraining.py
cd ..
git diff --check
git diff --cached --check
```

가능하면 커밋 전 `detect-secrets scan`을 변경 파일 대상으로 실행한다.

---

## 지켜야 할 규칙

- 코드 수정 전 root cause와 현재 모델/서비스 흐름을 먼저 확인한다.
- `apply_patch`로만 파일을 직접 수정한다.
- repo source와 별개인 generated/untracked 파일은 건드리지 않는다.
- raw OCR/provider payload, object URI, local image path, owner hash, secret은 API 응답, log, Todo 문서, operator output에 넣지 않는다.
- commit message는 Conventional Commits 형식으로 작성한다.
- commit body에는 `Why`, `Constraint`, `Tested`를 포함한다.
- commit footer에는 `Co-authored-by: OmX <omx@oh-my-codex.dev>`를 포함한다.

---

## 참고 공식 문서

- Ultralytics detect dataset: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics train mode: <https://docs.ultralytics.com/modes/train/>
- Ultralytics YOLO26: <https://docs.ultralytics.com/models/yolo26/>
- Ultralytics predict mode: <https://docs.ultralytics.com/modes/predict/>
- Ollama structured outputs: <https://docs.ollama.com/capabilities/structured-outputs>
- Ollama generate API: <https://docs.ollama.com/api/generate>
