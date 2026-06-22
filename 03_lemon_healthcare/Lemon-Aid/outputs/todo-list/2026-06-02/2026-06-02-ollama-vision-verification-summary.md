# 2026-06-02 Ollama/Gemma 비전 OCR 검증 구현 요약

> 작성 기준: 2026-06-02
> 범위: 영양제 OCR 결과를 local vision model이 이미지와 대조 검증하는 backend 계약 보완

---

## 1. 배경

기존 backend의 멀티모달 검증은 local vision model이 다시 읽은 텍스트와 primary OCR 텍스트의 유사도를 비교하는 방식이었다.

이 방식은 다음 문제가 있었다.

- 모델이 OCR처럼 다시 읽은 텍스트만 비교하므로, "이미지에 실제로 보이는 필수 섹션이 빠졌는지"를 명확히 표현하지 못한다.
- `Supplement Facts`, `Suggested Use`, `Warning/Caution` 같은 섹션 단위 누락을 warning으로 분리하기 어렵다.
- Gemma/Ollama vision 단계가 OCR 보조인지, OCR 검증인지 계약이 모호했다.

---

## 2. 공식 문서 기준

- Ollama structured outputs는 `format`에 JSON Schema를 전달해 모델 출력을 구조화할 수 있다고 안내한다: <https://docs.ollama.com/capabilities/structured-outputs>
- Ollama API는 vision model에 base64 image를 전달하는 image input을 지원한다고 안내한다: <https://docs.ollama.com/api/generate>

이번 구현은 위 계약에 맞춰 local Ollama 호출을 schema-validated verification 단계로 분리했다.

---

## 3. 구현 내용

### Backend LLM adapter

- `OllamaVisionTextVerificationResult` 추가
  - `verification_status`: `match | partial | mismatch | uncertain`
  - `confidence`: `0..1`
  - `source_region`: `full_image | yolo_roi`
  - `matched_fragments`, `missing_fragments`
  - `missing_critical_sections`: `product_name`, `supplement_facts`, `intake_method`, `precautions`
  - `warnings`
- `OllamaVisionAssistAdapter.verify_text(...)` 추가
  - OCR 텍스트와 이미지 또는 YOLO ROI crop을 local Ollama vision model에 전달
  - JSON Schema 기반 출력만 허용
  - schema validation 실패 시 `OllamaStructuredOutputError`
- prompt 정책
  - 이미지에 보이는 텍스트만 기준으로 비교
  - 외부 지식, 복용 조언, 의료 조언 생성 금지
  - raw OCR/provider payload 저장 없음

### Image analysis service

- `multimodal_adapter`가 `verify_text(...)`를 지원하면 구조화 검증 경로를 우선 사용
- 구조화 검증 결과가 다음 중 하나면 기존 OCR mismatch warning을 사용
  - `verification_status == "mismatch"`
  - `missing_critical_sections`가 비어 있지 않음
  - `verification_status == "partial"`이고 confidence가 threshold 미만
- 기존 `extract_text(...)` 유사도 비교 경로는 protocol 미지원 adapter의 fallback으로 유지

---

## 4. 검증 결과

### Backend unit regression

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

### Backend lint

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

### Diff check

```bash
git diff --check
```

결과:

```text
pass
```

---

## 5. 남은 차단점

- 실제 Gemma4/Ollama vision model이 local runtime에 설치되어 있는지 live smoke가 필요하다.
- 영양제 섹션 custom YOLO26 `.pt`가 아직 없어 `precautions`, `supplement_facts`, `intake_method` ROI 품질은 검증하지 못했다.
- 개인 정보 DB 기반 안내는 우선 최신 body profile snapshot의 sanitized bucket을 opt-in으로 explanation context에 연결했다.
- 질환/복약 정보 DB 기반 안내는 raw text가 아닌 condition/medication summary bucket을 opt-in으로 explanation context에 연결했다.
- 다음 검증은 실제 local Ollama/Gemma runtime에서 profile/medical bucket이 안전 문장으로 유지되는지 확인하는 live smoke다.
