# 2026-06-02 YOLO26 모델 계약 Guard 구현 요약

> 작성 기준: 2026-06-02
> 범위: backend supplement YOLO ROI runtime/readiness guard

---

## 1. 문제

현재 목표는 음식 YOLO가 아니라 영양제/보충제 이미지에서 성분표, 성분 함량, 섭취 방법, 섭취 시 주의사항을 bbox로 나누고 각 영역을 OCR하는 것이다.

기존 runner는 Ultralytics prediction 결과의 bbox class만 필터링했다. 이 구조에서는 다음 문제가 남는다.

- `yolo26n.pt` 같은 COCO pretrained model이 설정되어도 inference 전에는 영양제 모델이 아니라는 사실이 명확히 드러나지 않는다.
- 음식 YOLO 실험 가중치가 supplement ROI detector로 잘못 연결되어도, 결과가 비어 있는 warning처럼 보일 수 있다.
- `supplement_label`/`supplement_bottle`만 가진 label-only 모델은 전체 라벨 crop에는 쓸 수 있지만, 이번 목표의 섹션 OCR에는 충분하지 않다.

---

## 2. 구현 내용

### Vision taxonomy

- `VISION_SECTION_LABELS`를 추가했다.
- 섹션 label은 다음 4개다.
  - `supplement_facts`
  - `precautions`
  - `intake_method`
  - `ingredients`
- `normalize_vision_label_set()`을 추가해 readiness 응답에서 configured label을 canonical form으로만 노출한다.

### Ultralytics runner

- `model.names`를 읽어 모델 class names가 supplement ROI taxonomy로 normalize되는지 확인한다.
- 모델 class names가 configured `VISION_ROI_ALLOWED_CLASSES`와 교집합을 갖는지 확인한다.
- 모델 class names가 최소 하나 이상의 section ROI class를 포함하지 않으면 inference 전에 `VisionError`로 fail-closed 처리한다.
- class-name metadata가 없는 모델도 inference 전에 거부한다.

### Readiness

- `/ready`의 `vision` payload에 다음 safe metadata를 추가했다.
  - `supplement_yolo_contract`
  - `supplement_yolo_allowed_labels`
  - `supplement_yolo_required_section_labels`
- raw model path, local source path, image path, OCR text, provider payload는 readiness 응답에 포함하지 않는다.

---

## 3. 회귀 테스트

추가/수정된 테스트:

- COCO class names(`person`, `bicycle`)가 supplement detector로 사용되지 않는지 검증
- `supplement_label`, `supplement_bottle`만 가진 label-only model이 section detector로 통과하지 않는지 검증
- class-name metadata가 없는 모델이 prediction 전에 거부되는지 검증
- section label model이 정상 bbox metadata를 반환하는지 검증
- `/ready`가 supplement YOLO 계약을 안전하게 노출하고 secret/path를 노출하지 않는지 검증

검증 명령:

```bash
cd backend
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/vision/test_yolo_detector.py Nutrition-backend/tests/unit/test_health.py Nutrition-backend/tests/unit/test_config.py Nutrition-backend/tests/unit/ocr/test_ocr_factory.py
.venv/bin/python -m ruff check Nutrition-backend/src/vision/taxonomy.py Nutrition-backend/src/vision/ultralytics_runner.py Nutrition-backend/src/readiness.py Nutrition-backend/tests/unit/vision/test_yolo_detector.py Nutrition-backend/tests/unit/test_health.py
```

결과:

```text
104 passed
All checks passed!
```

---

## 4. 남은 작업

이번 작업은 default COCO/food/label-only 모델을 잘못 쓰는 것을 막는 guard다.

아직 실제 영양제 섹션 YOLO26 `.pt`가 준비된 것은 아니다. 다음 단계는 다음 순서로 진행해야 한다.

1. supplement section detector dataset YAML과 bbox label contract를 repo-relative로 정의한다.
2. `supplement_facts`, `precautions`, `intake_method`, `ingredients` class가 포함된 custom YOLO26 detector를 학습한다.
3. fixture 이미지로 bbox 품질을 확인한다.
4. 각 bbox crop OCR과 전체 이미지 OCR fallback을 비교한다.
5. Ollama/Gemma vision verification으로 OCR 결과가 이미지 근거와 맞는지 확인한다.

---

## 5. 참고 공식 문서

- Ultralytics YOLO26: <https://docs.ultralytics.com/models/yolo26/>
- Ultralytics Predict mode: <https://docs.ultralytics.com/modes/predict/>
- Ultralytics Model.names reference: <https://docs.ultralytics.com/reference/engine/model/>
