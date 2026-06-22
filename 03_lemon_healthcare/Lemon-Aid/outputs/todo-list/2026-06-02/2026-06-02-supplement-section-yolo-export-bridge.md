# 2026-06-02 영양제 섹션 YOLO export bridge 추가

> 작성 기준: 2026-06-02
> 범위: privacy-reviewed annotation manifest에서 supplement section YOLO 학습 export 생성

---

## 1. 배경

직전 단계에서 `data/supplement_images/section_yolo/dataset.yaml`과 dataset validator를 추가했다.

그러나 기존 generic `yolo_detection` export는 숫자 `class_id`만 검증하므로, 다음을 보장하지 못한다.

- `0`번 class가 실제로 `supplement_facts`인지
- `1`번 class가 실제로 `precautions`인지
- `supplement_label` 같은 전체 라벨 bbox가 섹션 detector 학습 입력으로 잘못 들어오지 않는지
- 알레르기/주의사항 bbox가 `precautions`로 canonical mapping되는지

이번 단계는 DB에 저장된 privacy-reviewed annotation manifest를 custom YOLO26 학습 계약으로 연결하는 bridge를 추가한 작업이다.

---

## 2. 구현 내용

### Section 전용 export schema

- `supplement-section-yolo-detect-export-v1` schema를 추가했다.
- class order를 다음 순서로 고정했다.
  - `0: supplement_facts`
  - `1: precautions`
  - `2: intake_method`
  - `3: ingredients`
- bbox는 `label`, `class_name`, `section_type` 중 하나의 semantic section label을 필수로 요구한다.
- `warning`, `allergy_warning` 같은 alias는 `precautions`로 canonical mapping된다.
- 숫자 `class_id`만 있는 bbox는 section export에서 거부한다.
- `supplement_label` 같은 전체 라벨 bbox는 section detector 학습 입력으로 거부한다.

### Operator export CLI

`backend/scripts/export_training_manifest.py`에 다음 export kind를 추가했다.

```text
supplement_section_yolo_detection
```

사용 예시:

```bash
cd backend
.venv/bin/python scripts/export_training_manifest.py \
  --dataset-version-id <privacy-approved-dataset-version-id> \
  --export-kind supplement_section_yolo_detection \
  --output ../outputs/generated/training/supplement-section-yolo-export.json
```

stdout summary에는 source ref, OCR text, provider payload, image path, bbox label detail을 출력하지 않는다.

---

## 3. 검증 결과

```bash
cd backend
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/learning/test_retraining.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py
.venv/bin/python -m ruff check Nutrition-backend/src/learning/retraining.py scripts/export_training_manifest.py Nutrition-backend/tests/unit/learning/test_retraining.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py
```

결과:

```text
17 passed
All checks passed!
```

검증한 케이스:

- semantic section label이 class id로 매핑됨
- `allergy_warning`이 `precautions`로 매핑됨
- 숫자 class id만 있는 bbox가 거부됨
- `supplement_label` 전체 라벨 bbox가 거부됨
- operator summary에 private source ref와 section label detail이 출력되지 않음

---

## 4. 남은 작업

1. 실제 human-reviewed annotation item에 semantic section label을 저장한다.
2. `supplement_section_yolo_detection` export artifact를 생성한다.
3. trusted worker에서 private source ref를 임시 이미지 파일로 resolve한다.
4. export artifact를 `processed/section_yolo/images|labels` 구조로 materialize한다.
5. `validate_supplement_section_yolo_dataset.py --require-files`를 통과시킨다.
6. Ultralytics YOLO26 custom detector를 학습하고 fixture 이미지로 bbox/OCR/Gemma verification을 확인한다.

---

## 5. 참고 공식 문서

- Ultralytics detect dataset: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics train mode: <https://docs.ultralytics.com/modes/train/>
- Ultralytics YOLO26: <https://docs.ultralytics.com/models/yolo26/>
