# 2026-06-02 현재 작업 최종 정리 및 GitHub 게시 요약

> 작성 기준: 2026-06-02
> 대상 브랜치: `docs/docs-2026-05-31-backend-ocr-security`
> 팀 remote: `origin` (`Lemon-Aid-KDT/Lemon-sin.git`)

---

## 1. 이번 섹션에서 완료한 핵심 작업

### OCR 주의사항 누락 보완

- `Warning`, `Allergy Information`, `Contains soy and milk`처럼 heading이 짧거나 없는 주의사항 문구를 `precautions` layout evidence로 분류하도록 보완했다.
- LLM parser가 주의사항을 놓치더라도 OCR layout에서 확인된 `precautions`를 structured result로 승격하는 fallback을 추가했다.
- raw OCR text, provider payload, image path, source ref는 API/operator output에 노출하지 않는 기준을 유지했다.

### 성분 후보 오탐 제거

- `1회 제공량(26g)`, `Serving Size`, `Amount Per Serving` 계열이 성분명으로 분리되는 문제를 보완했다.
- 줄 깨짐, 괄호 공백, 앞뒤 텍스트 혼합 케이스를 회귀 테스트로 추가했다.
- 실제 성분명과 함량이 있는 row는 유지하고 serving-size metadata만 성분 후보에서 제외하도록 처리했다.

### YOLO26 영양제 섹션 detector 준비

- 영양제 섹션 taxonomy를 `supplement_facts`, `precautions`, `intake_method`, `ingredients`로 고정했다.
- Ultralytics dataset 계약을 `data/supplement_images/section_yolo/dataset.yaml`로 추가했다.
- 모델 class name guard를 추가해 COCO/food/default model이 영양제 섹션 detector로 잘못 사용되지 않도록 했다.
- privacy-reviewed annotation을 YOLO detection export로 변환하는 bridge와 materializer를 추가했다.
- OCR layout bbox를 YOLO normalized label 후보 snapshot으로 변환하는 helper를 추가했다.

### Ollama/Gemma 검증 및 개인화 설명 준비

- OCR 텍스트와 이미지/ROI를 직접 대조하는 structured verification 계약을 추가했다.
- `match | partial | mismatch | uncertain` 상태와 필수 섹션 누락을 backend warning으로 연결할 수 있게 했다.
- `include_profile_context`, `include_medical_context`가 켜진 경우에만 사용자 건강/의료 DB의 sanitized bucket을 설명 context에 포함하도록 했다.
- 원문 질환명, 약명, 용량, raw OCR/provider payload는 LLM context와 저장 payload에 직접 넣지 않는 원칙을 유지했다.

---

## 2. 현재 Git 상태 기준

- 현재 브랜치 HEAD는 `cc5c819 feat(learning): derive supplement section YOLO labels from OCR layout`이다.
- 해당 commit은 `origin/docs/docs-2026-05-31-backend-ocr-security`에 push 완료된 상태다.
- 현재 요청에서는 오늘 날짜 Todo 문서만 추가 커밋 대상으로 삼는다.
- 아래 untracked 파일/폴더는 이번 문서 커밋 범위에서 제외한다.

제외 대상:

- `.omc_probe_1780240220778875000.txt`
- `data/nutrition_reference/crawling-image/`
- `data/nutrition_reference/sample-image/`
- `frontend/public/`
- `frontend/src/app/tech/`
- `mobile/assets/app_icon/Mascot_AppIcon_Rebuild_Assets/`
- `mobile/scripts/select_naver_gallery_samples.py`
- `mobile/uiux/LemonAid_Mascot_AppIcon_Rebuild_Assets/`
- `mobile/uiux/logo/`
- `outputs/todo-list/2026-05-31/*`

---

## 3. 검증 완료 이력

최근 코드 변경 기준으로 수행한 검증:

```bash
cd backend
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/learning/test_supplement_section_labels.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/learning/test_supplement_section_labels.py Nutrition-backend/tests/unit/learning/test_retraining.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py
.venv/bin/python -m ruff check Nutrition-backend/src/learning/supplement_section_labels.py Nutrition-backend/tests/unit/learning/test_supplement_section_labels.py
```

결과:

```text
5 passed
22 passed
All checks passed!
```

이번 문서 커밋 전 검증 기준:

```bash
git diff --check
git diff --cached --check
detect-secrets scan <이번 커밋 대상 문서>
```

---

## 4. 아직 남은 핵심 작업

1. OCR layout 기반 section bbox 후보 snapshot을 `AnnotationTask` operator review queue에 연결한다.
2. 후보 snapshot은 바로 학습 데이터로 쓰지 않고, 사람이 검수한 후에만 `LearningDatasetItem` 또는 training export로 넘긴다.
3. `training_export_allowed=false` 같은 안전 플래그를 둬서 후보 snapshot이 실수로 학습 export에 들어가지 않도록 한다.
4. operator-only source map을 준비해 실제 image/label dataset을 materialize한다.
5. `--require-files` validator를 통과한 뒤 YOLO26 custom detector를 학습한다.
6. detector bbox crop OCR, 전체 이미지 OCR fallback, Ollama/Gemma vision verification을 실제 이미지로 비교한다.
7. 사용자 DB 기반 복용 권장, 경고, 의사 상담 안내 설명을 모바일 Chat/설명 UI와 연결한다.

---

## 5. 참고 공식 문서

- Ultralytics detect dataset: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics train mode: <https://docs.ultralytics.com/modes/train/>
- Ultralytics YOLO26: <https://docs.ultralytics.com/models/yolo26/>
- Ultralytics predict mode: <https://docs.ultralytics.com/modes/predict/>
- Ollama structured outputs: <https://docs.ollama.com/capabilities/structured-outputs>
- Ollama generate API: <https://docs.ollama.com/api/generate>
