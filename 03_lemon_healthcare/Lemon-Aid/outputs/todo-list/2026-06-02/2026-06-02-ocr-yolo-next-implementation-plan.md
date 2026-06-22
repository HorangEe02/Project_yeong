# 2026-06-02 OCR/YOLO 다음 구현 계획

> 작성 기준: 2026-06-02
> 목표: 주의사항/알레르기 문구 누락 방지, serving-size 성분 후보 오탐 제거, 수정 전후 테스트 기준 고정

---

## 1. 구현 순서

### 1. Vision taxonomy 확장

`backend/Nutrition-backend/src/vision/taxonomy.py`에 section-level ROI label을 추가한다.

- `supplement_facts`
- `intake_method`
- `precautions`
- `ingredients`

alias 후보:

- `warning`, `warnings`, `caution`, `allergy_warning`, `allergen_warning` -> `precautions`
- `directions`, `suggested_use`, `usage`, `dosage` -> `intake_method`
- `supplement_facts_panel`, `nutrition_facts`, `facts` -> `supplement_facts`
- `other_ingredients`, `ingredient_list` -> `ingredients`

### 2. ROI allowed classes 기본값 보완

`backend/Nutrition-backend/src/config.py`의 default allowed labels에 section ROI를 포함한다. 단, 실제 section ROI는 custom-trained Ultralytics model이 해당 class를 반환할 때만 의미가 있으므로 기본 모델 `yolov8n.pt` 또는 `yolo26n.pt`만으로 주의사항 검출이 자동 해결된다고 표현하지 않는다.

### 3. 다중 ROI OCR page 보존

`_merge_ocr_results()`에서 여러 OCR 결과의 `pages`를 버리지 않고 합친다. 텍스트만 합치면 LLM 입력은 나아지지만, layout parser가 `Warnings`, `Caution`, `Suggested Use` 같은 anchor를 섹션으로 승격하기 어렵다.

### 4. ROI 우선순위 정렬

선택된 단일 ROI만 우선하는 방식에서 벗어나 section label priority를 적용한다.

우선순위:

1. `supplement_facts`
2. `precautions`
3. `intake_method`
4. `ingredients`
5. `supplement_label`
6. `supplement_bottle`, `blister_pack`

### 5. Serving-size heading filter 강화

`supplement_parser.py`에서 다음 문구는 성분 후보에서 제외한다.

- `1회 제공량`
- `1회제공량`
- `회 제공량`
- `회제공량`
- `제공량`
- `Serving Size`
- `Amount Per Serving`
- `Servings Per Container`

`비타민 C 26g`처럼 실제 성분명과 함량이 있는 정상 케이스는 계속 유지한다.

---

## 2. 테스트 계획

### Backend unit

- `vision/taxonomy` label normalize 테스트
  - `warning`, `allergy_warning`이 `precautions`로 정규화되는지 확인
  - `suggested_use`가 `intake_method`로 정규화되는지 확인

- `supplement_image_analysis` 다중 ROI OCR 테스트
  - 성분표 ROI와 주의사항 ROI를 fake vision adapter가 반환
  - fake OCR adapter가 각 crop에서 서로 다른 page를 반환
  - merge 후 parser 입력 text에 warning 문장이 포함되는지 확인
  - preview label sections에 `precautions`가 남는지 확인

- `supplement_parser` serving-size 오탐 테스트
  - `1회 제공량(26g)` 계열은 성분 후보 0개
  - `비타민 C 26g` 계열은 성분 후보 1개

### 검증 명령

```bash
cd backend
.venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py \
  Nutrition-backend/tests/unit/vision/test_yolo_detector.py
```

```bash
cd backend
.venv/bin/python -m ruff check \
  Nutrition-backend/src/services/supplement_image_analysis.py \
  Nutrition-backend/src/services/supplement_parser.py \
  Nutrition-backend/src/vision/taxonomy.py \
  Nutrition-backend/src/config.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py \
  Nutrition-backend/tests/unit/vision/test_yolo_detector.py
```

```bash
git diff --check
git diff --cached --check
```

---

## 3. 제외할 것

- raw OCR/provider payload 저장
- 원본 이미지 경로/API 응답 노출
- custom-trained YOLO model 없이 section ROI가 자동 검출된다고 단정
- serving-size header를 성분 후보로 저장
- 기존 사용자 분석 결과를 강제 재분류하거나 삭제

---

## 4. 다음 섹션 시작 프롬프트

```text
Lemon-Aid repo에서 OCR/YOLO 주의사항 누락과 serving-size 성분 후보 오탐을 수정해줘.

기준 문서:
- outputs/todo-list/2026-06-02/2026-06-02-ocr-yolo-precaution-analysis.md
- outputs/todo-list/2026-06-02/2026-06-02-ocr-yolo-next-implementation-plan.md

구현 순서:
1. vision taxonomy에 supplement_facts/intake_method/precautions/ingredients section ROI label과 aliases 추가
2. ROI allowed classes 기본값 보완
3. 다중 ROI OCR merge 시 pages 보존
4. section ROI 우선순위 기반 ordering 적용
5. supplement parser에서 1회 제공량/Serving Size/Amount Per Serving 계열을 성분 후보에서 제외
6. unit test와 ruff 실행

주의:
- raw OCR/provider payload, 이미지 로컬 경로, secret은 API 응답/문서/커밋에 포함하지 말 것
- custom YOLO model 없이 section ROI가 자동 검출된다고 단정하지 말 것
- 기존 untracked 데이터셋/이미지 폴더는 건드리지 말 것
```
