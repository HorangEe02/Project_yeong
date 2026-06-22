# 2026-06-02 OCR layout 기반 supplement section YOLO 후보 snapshot 추가

> 작성 기준: 2026-06-02
> 범위: OCR layout section bbox를 YOLO26 학습 후보 label snapshot으로 변환

---

## 1. 배경

이전 단계에서 supplement section YOLO26 학습을 위한 dataset YAML, export bridge, materializer를 추가했다.

아직 빠져 있던 연결점은 다음과 같았다.

- OCR provider가 이미 word/cell bbox를 가지고 있음
- layout parser가 `Supplement Facts`, `Warning`, `Suggested Use`, `Other Ingredients` 같은 섹션을 잡고 있음
- 하지만 이 bbox가 YOLO 학습 후보 snapshot으로 변환되지 않아 human-reviewed annotation 흐름에 바로 연결하기 어려웠음

---

## 2. 구현 내용

새 파일:

- `backend/Nutrition-backend/src/learning/supplement_section_labels.py`

추가 함수:

- `page_dimensions_from_ocr_result`
  - OCR page width/height를 추출한다.
  - page size가 없는 경우 추정하지 않고 omit한다.

- `build_supplement_section_yolo_label_snapshot`
  - `LabelLayout.sections`를 순회한다.
  - trainable section만 YOLO section label로 매핑한다.
  - absolute `LabelBox`를 page width/height 기준 normalized xywh로 변환한다.
  - raw OCR text, provider payload, image path, source ref, user id는 snapshot에 넣지 않는다.

섹션 매핑:

```text
daily_intake -> supplement_facts
nutrition_function_info -> supplement_facts
intake_method -> intake_method
precautions -> precautions
ingredients -> ingredients
```

생성 snapshot:

```json
{
  "schema_version": "supplement-section-yolo-label-candidates-v1",
  "text_stored": false,
  "boxes": [
    {
      "label": "precautions",
      "x_center": 0.485,
      "y_center": 0.775,
      "width": 0.73,
      "height": 0.05
    }
  ]
}
```

---

## 3. 안전 기준

- OCR text는 테스트 fixture 내부에만 존재하고, label snapshot에는 저장하지 않는다.
- page size가 없으면 임의 canvas를 추정하지 않고 fail-closed 처리한다.
- `storage_method`, `functionality`, `unknown`처럼 YOLO section class가 아닌 layout section은 export하지 않는다.
- 후보 snapshot은 바로 학습 데이터가 아니라 human review 전 후보다.
- 실제 `LearningDatasetItem.label_status`가 `human_reviewed`가 되기 전까지 training export에는 포함하지 않는다.

---

## 4. 검증 결과

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

검증한 내용:

- OCR layout bbox가 YOLO normalized xywh로 변환됨
- snapshot에 OCR text가 포함되지 않음
- snapshot이 `validate_sanitized_label_snapshot`을 통과함
- 기존 `build_dataset_export_manifest`와 `build_supplement_section_yolo_detection_export`에 연결됨
- page size가 없으면 실패함
- trainable section이 없으면 실패함

---

## 5. 남은 작업

1. 실제 OCR layout 결과에서 후보 snapshot을 생성하는 operator review queue 연결
2. 사람 검수 후 `LearningDatasetItem` 생성/갱신 경로 연결
3. real source map을 사용해 materializer 실행
4. 실제 이미지/label 파일 기준 `--require-files` validator 통과
5. YOLO26 custom detector 학습
6. detector bbox crop OCR과 전체 이미지 OCR fallback 비교
7. Ollama/Gemma vision verification과 사용자 DB 기반 text-to-text 권장/경고 설명 연결

---

## 6. 참고 공식 문서

- Ultralytics detect dataset: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics YOLO26: <https://docs.ultralytics.com/models/yolo26/>
- Ollama structured outputs: <https://docs.ollama.com/capabilities/structured-outputs>
- Ollama generate API: <https://docs.ollama.com/api/generate>
