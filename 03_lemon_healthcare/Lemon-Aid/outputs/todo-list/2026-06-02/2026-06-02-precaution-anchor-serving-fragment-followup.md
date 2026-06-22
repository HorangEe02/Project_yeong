# 2026-06-02 Precaution Anchor / Serving Fragment Follow-up

> 작성 기준: 2026-06-02
> 범위: 영양제 OCR layout parser, 주의사항/알레르기 ROI anchor, serving-size OCR fragment 회귀 테스트

---

## 1. 추가 확인한 문제

앞선 섹션 ROI 구현으로 `precautions` bbox crop을 OCR에 넘기는 흐름은 생겼지만, crop OCR 텍스트가 항상 `Warnings` 복수형 heading으로 시작한다고 볼 수 없었다.

실제 영양제 라벨은 다음처럼 더 다양한 표현을 쓴다.

- `Warning:`
- `Allergy Information`
- `Allergen Information`
- `Contains soy and milk`

따라서 YOLO가 주의사항 bbox를 제대로 찾아도 layout parser가 anchor를 못 잡으면 `precautions` section evidence가 약해질 수 있다.

---

## 2. 반영 내용

`backend/Nutrition-backend/src/parsing/layout_parser.py`를 보강했다.

- `precautions` section keyword에 단수 `Warning` 추가
- `Allergy Information`, `Allergen Information`, `Allergy Warning`, `Allergen Warning` 추가
- heading 없이 `Contains <allergen>` 문장으로 시작하는 ROI도 `precautions`로 분류
- 한국어 `함유` + 주요 알레르기 원재료 키워드 조합도 주의사항 후보로 분류

이 로직은 OCR row classification만 수행하며, 의료 판단이나 상담 문장을 생성하지 않는다.

---

## 3. Serving-size 회귀 보강

`1회 제공량(26g)` 오탐은 기본 케이스가 이미 막혀 있었지만, 실제 OCR은 줄 깨짐과 앞뒤 텍스트가 섞일 수 있다.

추가 테스트:

- `1회 제공량 (26 g)`
- `1회제공량( 26 g )`
- `제품명 ABC 1회 제공량(26g)`
- `총 내용량 26g`
- `1회 제공량\n(26g)`
- `1회\n제공량(26g)`
- `회 제공량(26g)`
- `제공량(26g)`

반대로 `비타민 C 26g` 같은 실제 성분명 + 함량은 계속 유지한다.

---

## 4. 검증

통과한 focused 검증:

```bash
cd backend && .venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py::test_parse_label_layout_detects_allergen_contains_roi_without_heading \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py::test_analyze_supplement_image_preserves_multi_roi_precaution_layout \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py::TestExtractIngredientDeclarationCandidates::test_ocr_pattern_ignores_serving_size_headers \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py::TestExtractIngredientDeclarationCandidates::test_ocr_pattern_ignores_split_serving_size_fragments
```

결과: `4 passed`

통과한 관련 회귀:

```bash
cd backend && .venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py \
  Nutrition-backend/tests/unit/vision/test_yolo_detector.py
```

결과: `55 passed`

정적 검사:

```bash
cd backend && .venv/bin/python -m ruff check \
  Nutrition-backend/src/parsing/layout_parser.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py
```

결과: `All checks passed`

---

## 5. 남은 조건

이번 변경은 OCR/layout 단계의 anchor 보강이다. 실제 이미지에서 bbox 품질까지 완료 판정하려면 영양제 섹션 custom YOLO26 `.pt` 모델이 필요하다.

공식 참고:

- Ultralytics YOLO26 model usage: <https://docs.ultralytics.com/models/yolo26/>
- Ultralytics Predict mode: <https://docs.ultralytics.com/modes/predict/>
- Ollama structured outputs: <https://docs.ollama.com/capabilities/structured-outputs>
