# 2026-06-02 OCR/YOLO 섹션 ROI 구현 요약

> 작성 기준: 2026-06-02
> 범위: 영양제 라벨 OCR, Ultralytics YOLO ROI taxonomy, 주의사항/섭취방법 OCR 라우팅, serving-size 성분 후보 오탐 제거

---

## 1. 작업 배경

영양제 라벨 이미지에 `Supplement Facts`, `Suggested Use`, `Warning/Caution`, `Other ingredients`가 보여도 결과 화면에서 주의사항이 비거나, `1회 제공량(26g)` 같은 제공량 행이 성분 후보로 오탐되는 문제가 있었다.

원인 분석 결과, Ultralytics runner의 `model.predict(...)` 사용 방식보다 우리 서비스의 ROI taxonomy와 OCR merge 계약이 더 큰 원인이었다. 공식 문서 기준으로 Ultralytics Python API는 `YOLO(...).predict(...)`와 결과의 `boxes` 접근을 지원한다.

- Ultralytics Predict mode: <https://docs.ultralytics.com/modes/predict/>
- Ultralytics Python usage: <https://docs.ultralytics.com/usage/python/>

---

## 2. 구현 내용

### 2.1 Vision taxonomy 확장

`backend/Nutrition-backend/src/vision/taxonomy.py`에 섹션 단위 ROI label을 추가했다.

- `supplement_facts`
- `precautions`
- `intake_method`
- `ingredients`

또한 custom YOLO 모델이 반환할 수 있는 alias를 정규화한다.

- `warning`, `caution`, `allergy_warning`, `allergen_warning` -> `precautions`
- `suggested_use`, `directions`, `usage`, `dosage` -> `intake_method`
- `supplement_facts_panel`, `nutrition_facts`, `facts` -> `supplement_facts`
- `other_ingredients`, `ingredient_list` -> `ingredients`

### 2.2 ROI allowlist 기본값 보완

`backend/Nutrition-backend/src/config.py`의 기본 `vision_roi_allowed_classes`에 섹션 ROI를 포함했다.

이 변경은 custom-trained supplement section model이 해당 class를 반환할 때 OCR 라우팅이 가능하도록 하는 기반이다. 기본 범용 YOLO 모델만으로 주의사항 텍스트가 자동 검출된다고 단정하지 않는다.

### 2.3 다중 ROI OCR 순서와 page 보존

`backend/Nutrition-backend/src/services/supplement_image_analysis.py`에서 OCR ROI 후보를 section priority로 정렬하도록 변경했다.

우선순위:

1. `supplement_facts`
2. `precautions`
3. `intake_method`
4. `ingredients`
5. `supplement_label`
6. `supplement_bottle`
7. `blister_pack`

또한 여러 crop OCR 결과를 합칠 때 `OCRResult.pages`를 보존하도록 수정했다. 텍스트만 합치면 LLM 입력은 늘어나지만, layout parser가 `Warnings`, `Caution`, `Suggested Use` 같은 섹션 anchor를 놓칠 수 있기 때문이다.

### 2.4 Serving-size 오탐 제거

`backend/Nutrition-backend/src/services/supplement_parser.py`에서 다음 heading은 성분 후보에서 제외했다.

- `1회 제공량`
- `1회제공량`
- `회 제공량`
- `회제공량`
- `제공량`
- `Serving Size`
- `Amount Per Serving`
- `Servings Per Container`

반대로 `비타민 C 26g`처럼 실제 성분명과 함량이 있는 문장은 계속 성분 후보로 유지한다.

### 2.5 주의사항 layout fallback

OCR layout parser가 `precautions` 섹션을 만들었지만 LLM structured parser가 `precautions` 배열을 비워두는 경우를 보완했다.

`LabelLayout.sections[].section_type == "precautions"`인 섹션에서 bare heading(`Warning`, `주의사항`)을 제외한 실제 문장만 sanitized preview precaution으로 승격한다.

- section anchor가 `Warning`이면 본문 문장에 `warning` 단어가 없어도 `severity=warning` fallback 적용
- pregnancy/allergy/medication/children 키워드는 보수적인 UI category로만 태깅
- fallback으로 채운 주의사항은 `requires_review=True`, `low_confidence_fields=["precautions"]` 유지
- raw OCR text/provider payload는 parsed snapshot에 저장하지 않음

---

## 3. 테스트 보강

추가/수정한 테스트:

- `test_vision_taxonomy_normalizes_section_roi_aliases`
  - section ROI alias가 내부 표준 label로 정규화되는지 확인
- `test_analyze_supplement_image_preserves_multi_roi_precaution_layout`
  - fake YOLO가 성분표/주의사항/섭취방법 ROI를 반환할 때 OCR crop 순서, parser 입력, layout page 보존을 확인
  - 단수 `Warning`과 `Allergy Information` row도 `precautions` evidence로 유지되는지 확인
- `test_parse_label_layout_detects_allergen_contains_roi_without_heading`
  - heading 없이 `Contains soy and milk`로 시작하는 allergen-only ROI가 `precautions` section으로 분류되는지 확인
- `test_ocr_pattern_ignores_serving_size_headers`
  - `1회 제공량(26g)` 계열이 성분 후보가 되지 않는지 확인
- `test_ocr_pattern_ignores_split_serving_size_fragments`
  - `1회 제공량\n(26g)`, `1회\n제공량(26g)` 같은 OCR fragment가 성분 후보가 되지 않는지 확인
- `test_ocr_pattern_keeps_real_amount_candidate`
  - 정상 성분명 + 함량 문장은 유지되는지 확인
- `test_parse_supplement_analysis_ocr_text_promotes_layout_precautions`
  - OCR layout의 visible warning rows가 structured `precautions`로 승격되는지 확인

---

## 4. 현재 의미

이번 구현으로 backend는 custom YOLO section detector가 `precautions`, `intake_method`, `supplement_facts` 같은 class를 반환할 때 해당 영역을 OCR로 넘길 준비가 됐다.

추가로 `backend/pyproject.toml`의 setuptools package discovery를 `Nutrition-backend/src`의 `src*` 패키지로 고정해 `pip install '.[vision]'`가 flat-layout package 탐색에서 실패하지 않도록 정리했다. backend vision extra 설치 후 `torch`, `ultralytics`, `cv2` import와 공식 YOLO26n 모델 로드 smoke를 통과했다.

다만 실제 이미지에서 주의사항을 자동 검출하려면 다음 조건이 필요하다.

- backend venv에 `ultralytics`, `torch`, OpenCV 계열 runtime 설치
- 영양제 라벨 섹션을 학습한 custom `.pt` 모델
- 해당 모델 class names가 이번 taxonomy alias와 맞거나 alias로 정규화 가능

현재 repo에서 확인한 `.pt`는 음식 YOLO 실험 weight뿐이며, 영양제 섹션 detector weight는 아직 확인되지 않았다.

추가로, custom YOLO model이 아직 없어도 OCR layout에 주의사항 섹션이 이미 보이는 경우에는 모바일 결과 카드가 빈 값으로 남지 않도록 parser fallback을 보완했다.
