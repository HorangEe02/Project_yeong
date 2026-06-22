# 2026-06-02 Supplement Analysis Medical Context Summary

## 목적

영양제 OCR 분석 결과 설명이 라벨 OCR 결과만 반복하지 않고, 사용자가 동의한 의료정보 DB의 질환/복약 요약을 함께 고려할 수 있도록 백엔드 계약을 확장했다.

## 적용 내용

- `SupplementAnalysisExplainRequest.include_medical_context`를 추가했다.
- `include_medical_context=true`일 때만 `sensitive_health_analysis` 동의를 요구한다.
- 동의 전에는 `patient_conditions`, `patient_medications`를 조회하지 않는다.
- 의료정보는 원문 질환명, 약명, 용량, 복용 빈도를 LLM에 전달하지 않는다.
- 전달하는 값은 아래 요약 버킷으로 제한한다.
  - active condition count
  - canonical condition code
  - active medication count
  - medication review category
  - uncategorized count

## 구현 파일

- `backend/Nutrition-backend/src/models/schemas/supplement_recommendation.py`
- `backend/Nutrition-backend/src/services/medical_records.py`
- `backend/Nutrition-backend/src/services/supplement_explanation.py`
- `backend/Nutrition-backend/src/api/v1/supplements.py`
- `backend/Nutrition-backend/tests/integration/api/test_supplement_ocr_text_api.py`
- `backend/Nutrition-backend/tests/unit/services/test_medical_records.py`

## 보안 규칙

- raw OCR text 저장 금지 유지
- provider payload 저장 금지 유지
- raw LLM response 저장 금지 유지
- raw profile payload 저장 금지 유지
- raw medical payload 저장 금지 추가
- audit metadata에는 요청 여부와 포함 여부만 기록

## 공식 참고

- FastAPI request body: https://fastapi.tiangolo.com/tutorial/body/
- SQLAlchemy 2.0 ORM select: https://docs.sqlalchemy.org/20/orm/queryguide/
- Pydantic fields: https://docs.pydantic.dev/latest/concepts/fields/

## 남은 작업

- 실제 모바일 버튼에서 `include_medical_context=true` 요청 연결
- OCR 분석 결과와 확정 영양제 성분을 comprehensive nutrition engine으로 연결
- Gemma/Ollama live runtime에서 의료 요약 버킷이 안전 문장으로 유지되는지 smoke test
