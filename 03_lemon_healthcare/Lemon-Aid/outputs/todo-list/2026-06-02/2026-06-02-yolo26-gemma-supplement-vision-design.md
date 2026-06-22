# 2026-06-02 YOLO26 + Gemma/Ollama 영양제 비전 설계

> 작성 기준: 2026-06-02
> 범위: 영양제 이미지 OCR/YOLO/Ollama 파이프라인 원인 분석, 설계, 구현 현황, 남은 차단점

---

## 1. 현재 문제

영양제 라벨에는 `Supplement Facts`, `Suggested Use`, `Warning/Caution`, 알레르기 문구가 보이지만 결과 화면에서는 성분 또는 주의사항이 비어 있는 경우가 있었다.

원인은 하나가 아니라 네 가지로 분리된다.

1. 범용 COCO pretrained YOLO26 모델은 사람/차량 같은 COCO class용이며, 영양제 섹션 class를 자동으로 알 수 없다.
2. custom section detector가 있어도 OCR merge에서 layout page를 버리면 `Warning` 같은 섹션 anchor가 사라질 수 있다.
3. OCR layout이 `precautions` 섹션을 잡아도 structured parser가 `precautions` 배열로 승격하지 않으면 모바일 4개 정보 카드가 비어 보인다.
4. `1회 제공량(26g)`, `Serving Size 26g` 같은 행은 성분이 아니라 제공량 metadata인데 성분 후보로 오탐될 수 있다.

---

## 2. 공식 문서 기준

- Ultralytics YOLO26 공식 문서는 `yolo26n.pt` 같은 detection 모델과 Python `YOLO(...)` 사용을 안내한다: <https://docs.ultralytics.com/models/yolo26/>
- Ultralytics Predict mode는 결과 객체에서 `boxes.xyxy`, `boxes.conf`, `boxes.cls`로 bounding box, confidence, class를 읽는 흐름을 설명한다: <https://docs.ultralytics.com/modes/predict/>
- Ollama structured outputs 문서는 `format`에 JSON schema를 전달하고 Pydantic schema로 검증하는 방식을 안내한다: <https://docs.ollama.com/capabilities/structured-outputs>
- Ollama generate API는 image input을 지원하는 모델에서 base64 image를 입력할 수 있음을 안내한다: <https://docs.ollama.com/api/generate>

중요한 결론: YOLO26 runtime을 붙였다고 해서 영양제명, 성분표, 섭취방법, 주의사항을 바로 감지할 수 있는 것은 아니다. 실제 section bbox 품질은 영양제 라벨 섹션 class로 학습한 custom `.pt` 모델이 있어야 판단할 수 있다.

---

## 3. 목표 아키텍처

### 3.1 인식 파이프라인

1. 모바일에서 카메라/갤러리 이미지를 업로드한다.
2. backend가 이미지를 decode하고 크기/형식/보안 조건을 검증한다.
3. YOLO26 custom section detector가 다음 bbox 후보를 반환한다.
   - `product_identity`
   - `supplement_facts`
   - `ingredient_amounts`
   - `intake_method`
   - `precautions`
   - `ingredients`
4. backend는 bbox를 crop하고 섹션 우선순위에 따라 OCR을 수행한다.
5. 필수 섹션이 비면 전체 이미지 OCR fallback을 수행한다.
6. OCR layout parser가 provider-neutral `label_sections`를 만든다.
7. deterministic parser fallback이 `precautions` layout 행을 structured `precautions` 배열로 승격한다.

### 3.2 해석 파이프라인

1. Ollama/Gemma vision-capable model은 OCR로 얻은 bounded section field가 이미지와 맞는지 보조 검증한다.
2. Ollama text-to-text 단계는 sanitized structured fields와 사용자 DB 정보만 입력받는다.
3. 출력은 JSON schema로 강제하고, backend Pydantic 검증을 통과한 결과만 UI에 전달한다.
4. 추천/주의/경고/의사 상담 안내는 의료 진단이 아니라 건강관리 참고 정보로 제한한다.
5. raw OCR, provider payload, 원본 이미지 경로는 API 응답이나 저장 모델에 포함하지 않는다.

---

## 4. 이번 섹션 구현

이번 섹션에서는 custom YOLO model 없이도 이미 OCR layout에 보이는 주의사항이 결과 카드에서 사라지는 문제를 막았다.

변경 사항:

- `supplement_parser.py`
  - `LabelLayout.sections[].section_type == "precautions"`인 행을 sanitized `SupplementPreviewPrecaution`으로 변환
  - bare heading(`Warning`, `주의사항`)은 제외하고 실제 문장만 승격
  - section anchor가 `Warning`이면 본문에 `warning` 단어가 없어도 severity fallback 적용
  - fallback으로 채운 값은 `requires_review=True`, `low_confidence_fields=["precautions"]`로 표시
  - raw OCR text나 provider payload는 snapshot에 저장하지 않음
- `test_supplement_parser.py`
  - visible warning layout rows가 structured `precautions`로 승격되는지 검증
  - pregnancy/allergy category, severity, evidence ref, missing section 재계산을 검증

추가로 Gemma/Ollama vision 단계의 역할을 OCR 재시도에서 OCR 검증으로 분리했다.

- `ollama_vision.py`
  - `OllamaVisionTextVerificationResult` schema 추가
  - `verify_text(image, text)`로 OCR 텍스트와 이미지 또는 YOLO ROI crop을 local vision model에 전달
  - `match | partial | mismatch | uncertain` 상태와 `missing_critical_sections`를 schema로 강제
  - 외부 지식, 복용 조언, 의료 조언 생성을 금지하고 raw OCR/provider payload 저장을 하지 않음
- `supplement_image_analysis.py`
  - adapter가 `verify_text(...)`를 지원하면 structured verification 경로를 우선 사용
  - `mismatch`, 필수 섹션 누락, threshold 미만 `partial`은 기존 OCR verification warning으로 연결
  - protocol 미지원 adapter는 기존 `extract_text(...)` 유사도 검증 fallback 유지
- `test_ollama_vision_assist.py`, `test_supplement_image_analysis.py`
  - schema-valid verification payload
  - schema-invalid output reject
  - structured verification 우선 경로
  - structured verification match/mismatch warning 분기 검증

---

## 5. 설계 자체 점검

| 항목 | 판단 | 대응 |
| --- | --- | --- |
| YOLO26 pretrained만으로 섹션 감지 가능 여부 | 불가능에 가까움 | custom supplement section `.pt` 필요로 명시 |
| OCR layout 기반 fallback이 hallucination을 만들 가능성 | 낮지만 존재 | OCR에 보이는 행만 사용하고 `requires_review=True` 유지 |
| 주의사항 문장 요약/변형 위험 | 존재 | fallback은 보이는 문장을 그대로 저장하고 category/severity만 보조 태깅 |
| raw OCR/provider payload 노출 위험 | 존재 | preview sanitizer와 bounded snapshot만 저장 |
| 의료 조언 과잉 위험 | 존재 | 개인 맞춤 안내는 경고/상담 권고로 제한하고 진단/처방 금지 |
| vision model 검증이 OCR 재시도로 흐를 위험 | 존재 | `verify_text` schema 계약으로 OCR 대조/필수 섹션 누락만 반환 |

---

## 6. 검증

실행한 검증:

```bash
cd backend
.venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/services/test_supplement_parser.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/vision/test_yolo_detector.py \
  Nutrition-backend/tests/unit/test_config.py
```

결과:

```text
121 passed
```

추가 검증:

```bash
cd backend
.venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/llm/test_ollama_vision_assist.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py \
  Nutrition-backend/tests/unit/vision/test_yolo_detector.py \
  Nutrition-backend/tests/unit/test_config.py
```

결과:

```text
134 passed
```

```bash
cd backend
.venv/bin/python -m ruff check \
  Nutrition-backend/src/llm/ollama_vision.py \
  Nutrition-backend/src/services/supplement_image_analysis.py \
  Nutrition-backend/tests/unit/llm/test_ollama_vision_assist.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py
```

결과:

```text
All checks passed!
```

---

## 7. 남은 작업

1. 영양제 섹션 custom YOLO26 `.pt` 위치 확정 또는 학습
2. `VISION_YOLO_MODEL_PATH`에 custom section model 연결
3. 실제 라벨 이미지에서 `precautions`, `intake_method`, `supplement_facts` bbox smoke test
4. Gemma/Ollama vision model의 실제 local availability 확인
5. OCR structured fields + 사용자 정보 DB를 입력으로 하는 schema-validated explanation endpoint end-to-end 확인
6. Android/iOS 실제 화면에서 4개 정보 카드와 편집 흐름 확인
