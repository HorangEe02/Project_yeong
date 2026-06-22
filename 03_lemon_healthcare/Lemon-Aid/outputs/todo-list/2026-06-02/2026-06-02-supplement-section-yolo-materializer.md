# 2026-06-02 영양제 섹션 YOLO dataset materializer 추가

> 작성 기준: 2026-06-02
> 범위: supplement section YOLO export artifact를 Ultralytics detect dataset 파일 구조로 변환

---

## 1. 배경

이전 단계에서 다음 두 가지를 추가했다.

- `data/supplement_images/section_yolo/dataset.yaml`: 섹션 detector dataset 계약
- `supplement_section_yolo_detection`: privacy-reviewed annotation manifest를 semantic section label 기반 export로 변환

하지만 실제 YOLO26 학습 전에는 export artifact를 다음 구조로 materialize해야 한다.

```text
processed/section_yolo/
├── images/{train,val,test}/
└── labels/{train,val,test}/
```

Ultralytics detect dataset은 이미지별 `*.txt` label 파일을 요구하며, 각 행은 `class x_center y_center width height` normalized xywh 형식이어야 한다.

---

## 2. 구현 내용

### Materializer script

`backend/scripts/materialize_supplement_section_yolo_dataset.py`를 추가했다.

입력:

- `--export`: `supplement-section-yolo-detect-export-v1` artifact
- `--source-map`: operator-only private source map
- `--dataset-yaml`: Ultralytics dataset YAML

처리:

- private `source_ref`를 source map으로 로컬 이미지에 연결한다.
- 이미지 파일명은 source ref 자체가 아니라 SHA-256 digest prefix로 만든다.
- split별 `images/{split}`에 이미지를 복사한다.
- split별 `labels/{split}`에 YOLO normalized label txt를 생성한다.
- 생성 후 기존 dataset validator의 `require_files=True`와 같은 수준으로 검증한다.

안전 제한:

- stdout summary에 source ref를 출력하지 않는다.
- stdout summary에 로컬 source path를 출력하지 않는다.
- stdout summary에 raw label row를 출력하지 않는다.
- raw OCR, provider payload, object URI, image bytes를 입력/출력 계약에 포함하지 않는다.
- `holdout` split은 train/val/test로 임의 매핑하지 않고 실패 처리한다.

---

## 3. 검증 결과

```bash
cd backend
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_materialize_supplement_section_yolo_dataset.py Nutrition-backend/tests/unit/scripts/test_validate_supplement_section_yolo_dataset.py Nutrition-backend/tests/unit/learning/test_retraining.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py
.venv/bin/python -m ruff check scripts/materialize_supplement_section_yolo_dataset.py Nutrition-backend/tests/unit/scripts/test_materialize_supplement_section_yolo_dataset.py
git diff --check
```

결과:

```text
27 passed
All checks passed!
```

검증한 케이스:

- export artifact + source map으로 `images/*`, `labels/*` 생성
- 생성된 label txt가 `class x_center y_center width height` 형식인지 검증
- CLI stdout이 source ref/source path를 노출하지 않는지 검증
- source map 누락 시 실패
- `holdout` split을 임의 materialize하지 않고 실패

---

## 4. 남은 작업

1. 실제 human-reviewed section bbox annotation을 준비한다.
2. operator-only source map을 생성하는 trusted resolver를 연결한다.
3. materializer를 실제 export artifact에 실행한다.
4. `validate_supplement_section_yolo_dataset.py --require-files`를 실제 데이터에서 통과시킨다.
5. Ultralytics YOLO26 custom detector를 학습한다.
6. fixture 이미지에서 bbox crop OCR과 전체 이미지 OCR fallback을 비교한다.
7. Ollama/Gemma vision verification과 text-to-text 사용자 맞춤 권장/경고 설명까지 end-to-end smoke를 진행한다.

---

## 5. 참고 공식 문서

- Ultralytics detect dataset: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics train mode: <https://docs.ultralytics.com/modes/train/>
