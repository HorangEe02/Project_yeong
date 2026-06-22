# 2026-06-02 OCR/YOLO 학습 파이프라인 현재 상태 및 다음 인계

> 작성 기준: 2026-06-02
> 범위: 영양제 OCR 주의사항 누락 보완, YOLO26 섹션 detector 준비, Ollama/Gemma 검증 계약, 다음 구현 blocker

---

## 1. 현재까지 완료한 작업

### OCR 주의사항/알레르기 문구 보완

- 단수 `Warning`, `Allergy Information`, `Contains <allergen>` 계열 OCR row를 `precautions` layout evidence로 분류하도록 보완했다.
- LLM parser가 주의사항을 놓쳐도 OCR layout evidence가 있으면 structured `precautions` 배열로 승격하는 fallback을 추가했다.
- `1회 제공량(26g)`, `Serving Size`, `Amount Per Serving` 계열 문구가 성분 후보로 들어오는 오탐을 막는 회귀 테스트를 추가했다.

### Ollama/Gemma 검증 계약

- OCR 텍스트와 이미지/ROI를 직접 대조하는 structured verification 계약을 추가했다.
- 결과 상태는 `match | partial | mismatch | uncertain`로 정리하고, 필수 섹션 누락은 backend warning으로 연결하는 방향을 잡았다.
- 공식 근거는 Ollama structured outputs와 generate API의 JSON schema/images 입력 계약을 기준으로 삼았다.

### Supplement section YOLO26 준비

- backend runtime에서 COCO/food/default model을 영양제 섹션 detector로 오인하지 않도록 class-name guard를 추가했다.
- `data/supplement_images/section_yolo/dataset.yaml`로 Ultralytics detect dataset 계약을 고정했다.
- 허용 class는 `supplement_facts`, `precautions`, `intake_method`, `ingredients` 중심의 section label이다.
- `supplement_section_yolo_detection` export kind를 추가해 privacy-reviewed annotation manifest만 YOLO 학습 export로 변환하도록 제한했다.
- `materialize_supplement_section_yolo_dataset.py`를 추가해 export artifact와 operator-only source map을 실제 `images/{split}` / `labels/{split}` 구조로 변환한다.

---

## 2. 현재 상태 판단

- 현재 repo에 있는 `.pt` 가중치는 음식 YOLO 실험 가중치이며, 영양제 섹션 detector로 간주하면 안 된다.
- 지금 완료된 것은 custom YOLO26 detector 학습 전 단계인 데이터셋 계약, annotation export bridge, materializer, validator다.
- 실제 "성분표/주의사항/섭취방법 bbox를 YOLO26으로 안정 검출"하려면 human-reviewed bbox annotation이 먼저 필요하다.

---

## 3. 다음 섹션 실행 순서

1. 영양제 라벨 이미지에 대해 사람이 검수한 section bbox annotation을 준비한다.
2. private source path/source ref는 operator-only source map으로만 연결한다.
3. `supplement_section_yolo_detection` export artifact를 생성한다.
4. materializer로 Ultralytics detect dataset 파일 구조를 만든다.
5. `validate_supplement_section_yolo_dataset.py --require-files`를 실제 데이터로 통과시킨다.
6. Ultralytics YOLO26 custom detector를 학습한다.
7. bbox crop OCR과 전체 이미지 OCR fallback을 비교한다.
8. Ollama/Gemma vision verification과 text-to-text 사용자 맞춤 권장/경고 설명까지 end-to-end smoke를 진행한다.

---

## 4. 안전 규칙

- raw OCR, provider payload, object URI, local image path, source ref는 API 응답과 operator stdout에 노출하지 않는다.
- 사용자 건강정보는 동의가 있을 때만 sanitized summary bucket으로 LLM 설명에 사용한다.
- food YOLO model, COCO default model, label-only model을 supplement section detector로 대체하지 않는다.
- "YOLO26 학습 완료"와 "YOLO26 학습 준비 pipeline 완료"를 명확히 구분한다.

---

## 5. 검증 명령

```bash
cd backend
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_materialize_supplement_section_yolo_dataset.py Nutrition-backend/tests/unit/scripts/test_validate_supplement_section_yolo_dataset.py Nutrition-backend/tests/unit/learning/test_retraining.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py
.venv/bin/python -m ruff check scripts/materialize_supplement_section_yolo_dataset.py Nutrition-backend/tests/unit/scripts/test_materialize_supplement_section_yolo_dataset.py
git diff --check
git diff --cached --check
detect-secrets scan
```

마지막 검증 결과 기준:

```text
27 passed
All checks passed!
```

---

## 6. 참고 공식 문서

- Ultralytics YOLO26: <https://docs.ultralytics.com/models/yolo26/>
- Ultralytics detect dataset: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics train mode: <https://docs.ultralytics.com/modes/train/>
- Ollama structured outputs: <https://docs.ollama.com/capabilities/structured-outputs>
- Ollama generate API: <https://docs.ollama.com/api/generate>
