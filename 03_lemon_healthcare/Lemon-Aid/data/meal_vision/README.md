# data/meal_vision

식단 인식(dev-guide 16) 트랙의 데이터 자원 디렉토리.

## 파일 구성

| 파일 | 단계 | 역할 |
|------|------|------|
| `mock_predictions.json` | MVP | image hash → YOLO detection + GCV hint mock. `MockYoloV8MealDetector`와 `MockGoogleVisionMealHintAdapter`가 룩업한다. |
| `classes.yaml` | MVP/Beta | YOLO 클래스 정의. MVP는 15~20종, Beta v1에서 50종으로 확장. |
| `dataset.yaml` | Beta | YOLOv8 fine-tuning 데이터셋 설정. MVP에서는 placeholder. |

## MVP에서의 사용

`mock_predictions.json`은 다음 경로에 있는 sample 이미지의 가짜 추론 결과를 담는다.
실제 추론을 수행하지 않으며, 이미지 hash를 키로 사용해 미리 정의된 결과를 그대로 반환한다.

- 이미지 hash 계산은 `MockYoloV8MealDetector`에서 정의 (예: SHA-256 prefix 16자).
- `class_name_ko`는 `classes.yaml`의 `names`에 정의된 항목과 일치해야 한다.

## Beta 진입 시 변경 사항 (Phase B)

1. AI Hub 한국음식 데이터셋 다운로드 → `ml/data/raw/`
2. AI Hub JSON annotation을 YOLO format(txt)으로 변환 → `ml/data/processed/`
3. `classes.yaml`을 50종으로 확장, `dataset.yaml`의 `names`와 동기화
4. `mock_predictions.json`은 비교/회귀 테스트 fixture로 유지하되, 운영 경로에서는 실 모델 추론으로 교체

## 데이터 라이선스·출처 주의

AI Hub 음식 데이터셋은 별도 이용 약관이 있다. 학습 결과물의 재배포 조건을 확인하고
원본 이미지는 `_archive/` 또는 `ml/data/raw/` 같은 gitignored 경로에 두며 커밋하지 않는다.

## 참조

- [`/docs/dev-guides/16-meal-recognition.md`](../../docs/dev-guides/16-meal-recognition.md)
- [`/docs/superpowers/plans/2026-05-11-meal-recognition-gcv-yolov8.md`](../../docs/superpowers/plans/2026-05-11-meal-recognition-gcv-yolov8.md)
