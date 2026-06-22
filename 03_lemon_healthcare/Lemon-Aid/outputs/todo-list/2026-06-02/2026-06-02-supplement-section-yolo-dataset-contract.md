# 2026-06-02 영양제 섹션 YOLO dataset contract 추가

> 작성 기준: 2026-06-02
> 범위: supplement section detector 학습 전 dataset YAML/validator/test 문서화

---

## 1. 배경

이전 단계에서 COCO/food/label-only YOLO 모델이 영양제 섹션 detector로 잘못 연결되지 않도록 runtime guard를 추가했다.

이번 단계는 실제 custom YOLO26 학습 전에 dataset 계약을 고정하는 작업이다. 목표 detector는 음식 객체 탐지가 아니라 영양제 라벨 내부 OCR 영역을 나누는 section detector다.

필수 섹션 class는 다음 4개로 고정했다.

- `supplement_facts`: 성분표/함량 표
- `precautions`: 주의사항, 경고, 알레르기/알러젠 문구
- `intake_method`: 섭취 방법, suggested use, directions, dosage
- `ingredients`: 기타 원료/성분 선언

---

## 2. 구현 내용

### Dataset YAML scaffold

- `data/supplement_images/section_yolo/dataset.yaml`을 추가했다.
- Ultralytics detect dataset 형식에 맞춰 `path`, `train`, `val`, `test`, `nc`, `names`를 repo-relative로 정의했다.
- 실제 학습 이미지와 YOLO label은 `data/supplement_images/processed/section_yolo/` 아래에 둘 것을 문서화했다.

### Validator

- `backend/scripts/validate_supplement_section_yolo_dataset.py`를 추가했다.
- 기본 검증은 class 계약만 확인한다.
- `--require-files`를 붙이면 split image directory, label directory, 이미지-라벨 pair, normalized bbox row까지 확인한다.
- COCO class, food YOLO class, label-only class, 누락된 필수 section class, 비연속 class id mapping을 실패 처리한다.
- CLI 출력은 raw OCR, provider payload, image path, label row를 출력하지 않는 safe summary로 제한했다.

### 테스트

- `backend/Nutrition-backend/tests/unit/scripts/test_validate_supplement_section_yolo_dataset.py`를 추가했다.
- contract-only 성공, COCO class 거부, `precautions` 누락 거부, 비연속 class id mapping 거부, image-label pair 검증, class id range 검증을 포함했다.

---

## 3. 검증 결과

```bash
cd backend
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_validate_supplement_section_yolo_dataset.py Nutrition-backend/tests/unit/vision/test_yolo_detector.py
.venv/bin/python -m ruff check scripts/validate_supplement_section_yolo_dataset.py Nutrition-backend/tests/unit/scripts/test_validate_supplement_section_yolo_dataset.py
.venv/bin/python scripts/validate_supplement_section_yolo_dataset.py ../data/supplement_images/section_yolo/dataset.yaml
```

결과:

```text
15 passed
All checks passed!
dataset contract ok: true
```

실제 annotation 파일까지 요구하는 검증은 아직 통과하지 않는다.

```bash
cd backend
.venv/bin/python scripts/validate_supplement_section_yolo_dataset.py ../data/supplement_images/section_yolo/dataset.yaml --require-files
```

현재 결과:

```text
Dataset root directory does not exist.
```

이는 아직 `processed/section_yolo/` 학습 이미지와 bbox label이 준비되지 않았기 때문에 정상적인 blocker다.

---

## 4. 다음 작업

1. `processed/section_yolo/images/{train,val,test}`와 `labels/{train,val,test}`를 준비한다.
2. 각 이미지에 `supplement_facts`, `precautions`, `intake_method`, `ingredients` bbox를 YOLO normalized format으로 라벨링한다.
3. `--require-files` 검증을 통과시킨다.
4. Ultralytics YOLO26 custom detector를 학습한다.
5. fixture 이미지로 bbox 품질, crop OCR, 전체 이미지 OCR fallback, Ollama/Gemma verification을 함께 확인한다.

---

## 5. 참고 공식 문서

- Ultralytics detect dataset: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics train mode: <https://docs.ultralytics.com/modes/train/>
- Ultralytics YOLO26: <https://docs.ultralytics.com/models/yolo26/>
