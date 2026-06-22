# 2026-06-02 YOLO26 모델 준비 상태 점검

> 작성 기준: 2026-06-02
> 목적: 영양제 OCR/YOLO/Ollama 파이프라인에서 custom supplement section detector 준비 상태를 분리 확인

---

## 1. 점검 명령

```bash
find . -path './.git' -prune -o -type f \( -name '*.pt' -o -name '*.onnx' -o -name '*yolo*.yaml' -o -name '*dataset*.yaml' -o -name 'classes.yaml' \) -print
```

```bash
find data backend mobile -path '*/__pycache__' -prune -o -type d \( -iname '*yolo*' -o -iname '*label*' -o -iname '*annotation*' -o -iname '*cvat*' -o -iname '*supplement*' -o -iname '*nutrition*' \) -print
```

```bash
find data backend mobile -path '*/__pycache__' -prune -o -type f \( -name '*.txt' -o -name '*.json' -o -name '*.jsonl' -o -name '*.csv' -o -name '*.yaml' -o -name '*.yml' \) -print | rg -i 'yolo|cvat|label|annotation|bbox|supplement|nutrition|meal_vision'
```

---

## 2. 확인 결과

### 확인된 모델/데이터

- `data/meal_vision/classes.yaml`
- `data/meal_vision/dataset.yaml`
- `runs/food_yolo/exp01_yolov8n_baseline_pc1_b48_w8_cache_disk_det_true/weights/best.pt`
- `data/supplement_images/manifests/classes.json`
- `data/supplement_images/manifests/taxonomy.json`
- `data/supplement_images/splits/train.csv`
- `data/supplement_images/splits/val.csv`
- `data/supplement_images/splits/test.csv`
- `backend/Nutrition-backend/tests/fixtures/supplement_labels/manifest.json`

### 해석

- 현재 `.pt` 가중치는 음식 YOLO 실험용으로 확인되며, 영양제 성분표/주의사항/섭취방법 섹션 bbox 전용 detector로 볼 근거가 없다.
- `data/supplement_images`에는 taxonomy/split/fixture 자료가 있지만, YOLO detection 학습용 bbox label 파일과 custom `.pt` 산출물은 확인되지 않았다.
- `backend/.venv/lib/python3.13/site-packages/ultralytics/cfg/models/26/*.yaml`은 Ultralytics package 내부 모델 구조 config이며, 프로젝트 영양제 detector 산출물이 아니다.

---

## 3. 다음 구현 기준

### Readiness guard

- backend vision runtime은 model class names를 읽어 `supplement_facts`, `precautions`, `intake_method`, `ingredients` 같은 허용 섹션 label로 normalize되는지 확인해야 한다.
- class names가 COCO/food 계열이면 영양제 섹션 detector로 사용하지 않고 `vision_status=failed` 또는 명확한 readiness warning을 반환한다.
- class names를 확인할 수 없는 모델은 production supplement section detector로 간주하지 않는다.

### Dataset contract

- 최소 class:
  - `supplement_facts`
  - `precautions`
  - `intake_method`
  - `ingredients`
- 권장 class:
  - `supplement_label`
  - `supplement_bottle`
  - `brand_front`
  - `nutrition_table`
- dataset YAML은 repo-relative path를 사용하고, train/val/test split을 명시한다.

### 검증 기준

- bbox detector가 성분표, 섭취방법, 주의사항 영역을 각각 검출한다.
- 각 bbox crop에 OCR을 수행하고, 비어 있는 필수 섹션은 전체 이미지 OCR fallback으로 보완한다.
- Ollama/Gemma vision verification이 OCR 추출값을 이미지와 대조해 `match | partial | mismatch | uncertain`으로 반환한다.
- UI에는 내부 기술 카드 대신 영양제명, 상세 성분 및 함량, 섭취 방법, 섭취 시 주의사항 4개 정보 카드와 LED 상태만 노출한다.

---

## 4. 현재 결론

현재 구현은 OCR layout anchor와 LLM/parser fallback을 보강한 상태다.

하지만 영양제 섹션 전용 YOLO26 detector는 아직 준비된 산출물이 확인되지 않았으므로, 다음 단계는 모델 준비 상태를 fail-closed로 드러내는 readiness guard와 dataset contract 추가다.
