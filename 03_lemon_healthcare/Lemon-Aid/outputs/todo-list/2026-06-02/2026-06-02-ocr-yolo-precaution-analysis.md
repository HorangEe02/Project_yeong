# 2026-06-02 OCR/YOLO 주의사항 누락 원인 분석

> 작성 기준: 2026-06-02
> 범위: 영양제 라벨 OCR, YOLO ROI, Ollama parser 입력 전처리, 모바일 결과 표시 전 데이터 계약

---

## 1. 현재 확인한 문제

사용자가 올린 영양제 라벨 이미지에는 다음 정보가 함께 존재한다.

- Supplement Facts 영역
- Suggested Adult Use / 섭취 방법 영역
- Warning / Caution / 알레르기·주의사항 영역
- Other ingredients 영역

그러나 앱 결과 화면에서는 성분 후보가 비어 있거나 일부 성분만 표시되고, 주의사항 카드에는 "확인할 수 없음" 상태가 표시된다. 또한 `1회 제공량(26g)` 같은 섭취량/제공량 문구가 성분 후보처럼 분리되어 `회 제공량` 후보로 들어갈 수 있는 문제를 재현했다.

---

## 2. 코드 확인 결과

### 2.1 YOLO ROI taxonomy 범위가 좁음

현재 backend vision taxonomy는 다음 수준의 object label 중심으로 구성되어 있다.

- `supplement_bottle`
- `supplement_label`
- `blister_pack`

즉 YOLO 모델이 `warning`, `caution`, `precautions`, `supplement_facts`, `directions` 같은 세부 라벨 영역을 반환해도 normalize/allowlist 단계에서 버려질 수 있다. 이 상태에서는 주의사항만 별도 ROI로 잘라 OCR하는 흐름이 안정적으로 작동하기 어렵다.

### 2.2 OCR ROI는 다중 입력을 만들 수 있으나 섹션 정보 보존이 약함

`supplement_image_analysis.py`는 `crop_before_primary` 정책일 때 여러 label region을 crop OCR 입력으로 만들고 마지막에 full image fallback을 붙인다. 다만 현재 구조에서는 crop OCR 결과를 merge할 때 여러 결과의 `pages`가 보존되지 않는 흐름이 있어, OCR 텍스트는 합쳐져도 layout 기반 `precautions` 섹션 감지가 약해질 수 있다.

### 2.3 단일 ROI 중심 선택이 주의사항 누락을 유발할 수 있음

현재 `select_best_label_region()`은 대표 ROI를 하나 고르고, 이후 OCR 후보 순서도 이 selected region을 우선한다. 성분표와 주의사항이 서로 다른 위치에 있으면 전체 이미지 fallback이 실패하거나 OCR 품질이 낮을 때 주의사항 영역이 누락될 수 있다.

### 2.4 `1회 제공량(26g)` 오탐은 parser fallback 문제

`INGREDIENT_AMOUNT_PATTERN`이 숫자 뒤의 한글 부분부터 다시 매칭하면서 `1회 제공량(26g)`을 `회 제공량` + `26g` 형태로 잘못 인식할 수 있다. 이는 YOLO 문제가 아니라 OCR fallback 성분 후보 추출 단계의 heading filter 누락 문제다.

---

## 3. 공식 문서 기준

Ultralytics 공식 문서 기준으로 YOLO predict 결과는 `Results` 객체 목록이며, 각 결과에서 `boxes`를 통해 bounding box 출력에 접근한다. inference 시 `conf` 인자를 통해 최소 confidence threshold를 지정할 수 있다.

- Ultralytics Predict mode: <https://docs.ultralytics.com/modes/predict/>
- Ultralytics Python usage: <https://docs.ultralytics.com/usage/python/>

따라서 현재 `ultralytics_runner.py`가 `model.predict(...)` 후 `boxes.xyxy`, `boxes.cls`, `boxes.conf`를 읽는 방식 자체는 공식 문서 흐름과 맞다. 이번 문제의 중심은 runner API 호출 방식보다, 우리 서비스가 허용하는 ROI taxonomy와 OCR merge/section parser 계약에 있다.

---

## 4. 원인 분리

### 주의사항 누락

원인 후보:

- section-level YOLO label이 taxonomy/allowlist에 없음
- 다중 ROI OCR 결과의 layout page가 merge 후 사라질 수 있음
- ROI 우선순위가 성분표/주의사항/섭취방법 섹션을 보장하지 않음
- full image OCR fallback이 작은 warning text를 안정적으로 읽지 못함

### 성분 후보 7개/1개 불일치

원인 후보:

- OCR provider가 표 안의 여러 row를 후보로 잡는 것은 멀티비타민 라벨에서는 정상일 수 있음
- 단일 성분 제품에서는 parser가 부원료, serving header, 문장 조각까지 성분 후보로 끌어올릴 수 있음
- `1회 제공량(26g)` 오탐은 serving-size heading filter가 부족해서 발생

---

## 5. 현재까지의 결론

이 문제는 "OCR이 아예 작동하지 않는다"로 보기보다, 다음 두 결함이 겹친 상태다.

1. YOLO ROI/OCR pipeline이 주의사항·섭취방법·성분표를 섹션별로 안정적으로 보존하지 못한다.
2. OCR fallback parser가 serving-size heading을 성분 후보에서 명확히 제외하지 못한다.

따라서 다음 구현은 YOLO26/Ultralytics API 호출 자체를 갈아엎는 방식이 아니라, section ROI taxonomy 확장, 다중 ROI OCR 보존, parser heading filter 강화 순서로 진행하는 것이 맞다.
