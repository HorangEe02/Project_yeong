# 2026-06-02 영양제 분석 설명 사용자 프로필 컨텍스트 구현 요약

> 작성 기준: 2026-06-02
> 범위: OCR 분석 미리보기 설명을 사용자 정보 DB의 최신 건강 프로필과 안전하게 연결

---

## 1. 배경

목표 파이프라인은 영양제 라벨에서 추출한 성분, 함량, 섭취 방법, 주의사항을 local LLM 설명 단계로 넘기고, 사용자의 건강 정보 DB와 함께 확인해 권장, 주의, 경고, 상담 안내를 제공하는 것이다.

기존 `POST /api/v1/supplements/analyses/{analysis_id}/explain` 경로는 분석 record의 sanitized parsed fields만 사용했다. 최신 사용자 프로필 snapshot을 설명 context에 포함하는 계약은 없었다.

---

## 2. 공식 문서 기준

- FastAPI는 POST request body를 Pydantic model로 선언해 검증하는 흐름을 안내한다: <https://fastapi.tiangolo.com/tutorial/body/>
- Pydantic fields 문서는 기본값이 있는 model field를 선택 입력값으로 정의하는 방식을 안내한다: <https://docs.pydantic.dev/latest/concepts/fields/>

이번 변경은 기존 request body model에 선택 필드 `include_profile_context`를 추가하고, true일 때만 별도 동의와 DB 조회를 수행하는 방식으로 구현했다.

---

## 3. 구현 내용

### Request contract

- `SupplementAnalysisExplainRequest.include_profile_context: bool = False` 추가
- 기본값은 false라 기존 모바일/테스트 호출은 동작이 바뀌지 않는다.

### Consent gate

- `include_profile_context=true`일 때만 `ConsentType.SENSITIVE_HEALTH_ANALYSIS` 동의를 추가로 요구한다.
- OCR 설명 자체는 기존처럼 `ConsentType.OCR_IMAGE_PROCESSING` 동의를 먼저 요구한다.
- 민감 건강 동의가 없으면 profile row를 읽지 않고 `403 consent_required`로 차단한다.

### DB context

- `get_latest_body_profile_snapshot(session, current_user)`로 현재 사용자 최신 profile snapshot만 조회한다.
- explanation context에는 owner id, consent snapshot, source record, raw payload를 넣지 않는다.
- 전달하는 값은 coarse bucket만 포함한다.
  - `sex`
  - `age_band`
  - 신장/체중/허리둘레 존재 여부
  - `pregnancy_status`
  - `lactation_status`
  - `activity_level`

### Explanation behavior

- deterministic fallback은 profile context가 있으면 "개인 프로필(...)" 확인 bullet을 추가한다.
- 임신/수유 상태와 라벨 주의 문구가 겹칠 수 있으면 전문가 상담 여부 확인 bullet을 추가한다.
- local LLM prompt는 sanitized OCR fields와 optional profile bucket만 사용하도록 제한한다.
- 진단, 처방, 용량 변경, 외부 지식 생성은 계속 금지한다.

### Audit

- audit metadata에는 다음 flag만 기록한다.
  - `profile_context_requested`
  - `profile_context_included`
  - `raw_profile_payload_stored=False`
- raw OCR/provider payload, image URI, raw LLM response도 계속 저장하지 않는다.

---

## 4. 검증 결과

### Backend regression

```bash
cd backend
.venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/integration/api/test_supplement_ocr_text_api.py \
  Nutrition-backend/tests/unit/llm/test_ollama_vision_assist.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py \
  Nutrition-backend/tests/unit/vision/test_yolo_detector.py \
  Nutrition-backend/tests/unit/test_config.py
```

결과:

```text
147 passed
```

### Backend lint

```bash
cd backend
.venv/bin/python -m ruff check \
  Nutrition-backend/src/models/schemas/supplement_recommendation.py \
  Nutrition-backend/src/services/supplement_explanation.py \
  Nutrition-backend/src/api/v1/supplements.py \
  Nutrition-backend/tests/integration/api/test_supplement_ocr_text_api.py
```

결과:

```text
All checks passed!
```

---

## 5. 남은 작업

- 모바일에서 `include_profile_context=true`를 언제 켤지 UX 정책 확정
- 사용자 질환/복약 정보 DB context bucket은 `include_medical_context=true` 계약으로 별도 구현됨
- 실제 local Ollama/Gemma model이 profile bucket과 label precautions를 입력받았을 때 schema-valid response를 반환하는 live smoke
- custom supplement YOLO26 `.pt` 기반 ROI 품질 검증
