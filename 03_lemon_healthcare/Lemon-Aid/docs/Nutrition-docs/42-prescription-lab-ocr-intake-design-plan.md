# 42. Prescription/lab OCR intake 상세 설계 및 구현 플랜

작성일: 2026-05-15
범위: `docs/Nutrition-docs/36-post-p1-execution-plan.md`의 P4 Prescription/lab OCR intake 항목

## 1. 현재 상태 확인

현재 프로젝트는 처방전/검사표 OCR intake 기능을 운영에 노출하지 않는다.

| 영역 | 현재 상태 | 설계 방향 |
| --- | --- | --- |
| Feature flag | `feature_prescription_ocr_intake=false`, `feature_lab_result_ocr_intake=false` | 운영 sign-off 전까지 default-off 유지 |
| 복용량 변경 | `feature_dosage_change_recommendation=false` | 직접 복용량 변경 안내 금지 |
| OCR adapter | 영양제 라벨 OCR용 adapter/factory가 존재 | regulated document용 intake service에서 재사용하되 별도 gate 적용 |
| Consent | `SENSITIVE_HEALTH_ANALYSIS`, `OCR_IMAGE_PROCESSING`, `EXTERNAL_OCR_PROCESSING` 등이 존재 | 처방전/검사표 전용 민감 동의 bucket 추가 권장 |
| DB | `regulated_documents`, `prescription_items`, `lab_result_items` 없음 | preview/confirm 구조로 신규 table 추가 |
| 문서 정책 | docs/15, docs/36, config JSON이 intake-only와 전문가 상담 CTA를 요구 | 구현도 동일하게 제한 |

핵심 결론:

- 처방전/검사표 OCR은 처방 생성, 처방 변경, 질병 진단, 복용량 조정이 아니라 사용자가 보유한 문서를 확인 가능한 항목으로 정리하는 intake로만 구현한다.
- 사용자가 확인하기 전에는 medication/safety workflow, dashboard, notification, 추천 엔진으로 전달하지 않는다.
- 원문 이미지는 DB에 저장하지 않고, OCR 처리 직후 삭제한다.
- OCR 원문 전체 텍스트도 저장하지 않는다. 저장 대상은 hash와 사용자가 확인한 structured field다.

## 2. 공식 문서 확인 근거

| 주제 | 확인한 내용 | 설계 반영 |
| --- | --- | --- |
| 민감정보 처리 | 개인정보 보호법 제23조는 건강 정보를 포함한 민감정보를 원칙적으로 제한하고, 다른 개인정보 동의와 별도 동의가 있는 경우 등을 예외로 둔다. | 처방전/검사표 OCR은 일반 OCR 동의와 분리된 민감 문서 동의를 요구한다. |
| 비대면 진료 | 보건복지부 비대면진료 시범사업 안내는 제한된 범위와 의료진 판단, 대면진료 보조 원칙을 강조한다. | 앱 단독으로 진료·처방·용량 변경 판단을 하지 않고 전문가 상담 CTA로 연결한다. |
| 처방 안전 | 식품의약품안전처 의약품 안내에서 환자가 의·약사 상담 없이 임의로 복용을 중단하지 말아야 한다는 취지를 확인했다. | “오늘부터 줄이세요/중단하세요/바꾸세요” 같은 문구와 endpoint를 금지한다. |
| 의료기기 경계 | 의료기기법 제2조는 질병 진단·치료·경감·처치·예방 목적 제품을 의료기기 범주로 정의한다. | 검사표 OCR 결과를 질병 진단·위험도 예측·치료 추천으로 확장하지 않는다. |
| 프로젝트 정책 | docs/15와 implementation-readiness의 regulated input policy는 처방전/검사표를 intake-only로 제한한다. | API, DB, 테스트 모두 blocked output을 명시적으로 차단한다. |

참고 URL:

- 개인정보 보호법 제23조 민감정보 처리 제한: https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000634115
- 보건복지부 비대면진료 시범사업 안내: https://www.mohw.go.kr/board.es?act=view&bid=0027&cg_code=&list_no=376615&mid=a10503000000&tag=
- 보건복지부 비대면진료 시범사업 보완방안: https://www.mohw.go.kr/board.es?act=view&bid=0027&list_no=1479333&mid=a10503000000
- 식품의약품안전처 의약품 정책정보 Q&A: https://www.mfds.go.kr/brd/m_1091/list.do
- 의료기기법 제2조 정의: https://www.law.go.kr/LSW/lsPdfPrint.do?ancYnChk=0&bylChaChk=N&efGubun=Y&efYd=20240614&joAllCheck=Y&joEfOutPutYn=on&lsiSeq=251747&mokChaChk=N

### 확인 한계

이 문서는 제품 구현 설계 기준이다. 의료기기 해당 여부, 비대면 진료 중개 해당 여부, 처방전 처리 범위는 운영 전 법무/인허가 리뷰가 필요하다. 따라서 구현 플랜은 일반 사용자 공개 기능에서 허용 가능한 최소 intake만 다룬다.

## 3. 브레인스토밍 결과

### 3.1 Endpoint 구조

검토안:

1. `POST /api/v1/regulated-inputs/ocr`
   - 장점: 구현 surface가 작다.
   - 단점: 처방전과 검사표 동의, parser, 금지 규칙이 섞인다.
2. `POST /api/v1/regulated-inputs/prescriptions/ocr`, `POST /api/v1/regulated-inputs/lab-results/ocr`
   - 장점: 문서 유형별 feature flag, consent, parser, response schema를 분리할 수 있다.
   - 단점: route와 schema가 늘어난다.

결정: 2번을 선택한다. 이미 docs/11, docs/15, implementation-readiness가 이 endpoint family를 기준으로 하고 있고, 처방전과 검사표는 금지 output이 다르다.

### 3.2 원문 이미지 처리

검토안:

1. 요청 중 memory only 처리
   - OCR adapter가 동기 처리할 수 있으면 가장 안전하다.
   - raw image 저장 row와 deletion worker가 필요 없다.
2. 임시 object storage 저장 후 job 처리
   - 비동기 OCR에는 유리하다.
   - 민감 문서 이미지 보유 리스크가 크고 삭제 실패 대응이 필요하다.

결정: MVP는 memory only 처리다. 비동기 OCR이 반드시 필요하면 `sensitive_document_original_image_retention_seconds`를 0보다 크게 두는 별도 PR에서만 허용하고, TTL worker와 삭제 실패 audit을 같이 구현한다.

### 3.3 OCR/parse 범위

처방전 OCR 허용 field:

- 약품명으로 보이는 텍스트
- 용량 텍스트
- 빈도 텍스트
- 기간 텍스트
- 처방일 또는 조제일로 보이는 날짜
- 병원/약국/의료진 이름은 저장 전 사용자 확인 대상이며, 필요 최소화한다.

검사표 OCR 허용 field:

- 검사명
- 수치
- 단위
- 참고범위
- 검사일

금지 field:

- 질병명 확정
- 치료 방침
- 약 변경/중단/증량/감량 지시
- 검사 수치 기반 질병 가능성 또는 위험도 예측

### 3.4 사용자 확인 단계

OCR 결과는 곧바로 확정 데이터가 아니다.

```text
uploaded -> ocr_preview_requires_confirmation -> user_corrected -> confirmed -> active
                                      |-> expired
                                      |-> deleted
```

규칙:

- preview는 TTL을 둔다.
- preview 상태에서는 medication schedule, medication safety, dashboard로 전달하지 않는다.
- confirm 요청은 사용자가 각 필드를 검토했다는 `user_confirmed=true`를 요구한다.
- confirm payload는 OCR 추출값을 그대로 저장하지 않고, 사용자가 수정/확인한 값만 저장한다.

### 3.5 상담 CTA

처방전과 검사표 response에는 항상 상담 CTA를 포함한다.

권장 schema:

```json
{
  "type": "consult_professional",
  "title": "전문가 상담이 필요한 정보입니다.",
  "message": "복용량 변경, 약 중단, 검사 결과 해석은 담당 의료진 또는 약사와 상담하세요.",
  "action": "contact_clinician_or_pharmacist"
}
```

CTA는 진단이나 지시가 아니라 다음 행동을 전문가 상담으로 돌리는 안전 장치다.

## 4. API 설계

### 4.1 처방전 OCR intake

Endpoint:

```text
POST /api/v1/regulated-inputs/prescriptions/ocr
```

Feature flag:

- `FEATURE_PRESCRIPTION_OCR_INTAKE=false` 기본값 유지

필수 동의:

- `PRESCRIPTION_OCR_INTAKE` 신규 consent type
- `SENSITIVE_HEALTH_ANALYSIS`
- OCR provider가 외부이면 `EXTERNAL_OCR_PROCESSING`

Response:

```json
{
  "document_id": "uuid",
  "document_type": "prescription",
  "status": "requires_confirmation",
  "recognized_items": [
    {
      "medication_name_text": "visible text only",
      "dose_text": "visible text only",
      "frequency_text": "visible text only",
      "period_text": "visible text only",
      "confidence": 0.82,
      "requires_user_confirmation": true
    }
  ],
  "warnings": ["OCR 결과는 사용자가 확인해야 합니다."],
  "consult_professional_cta": {
    "type": "consult_professional",
    "action": "contact_clinician_or_pharmacist"
  },
  "raw_image_stored": false,
  "raw_ocr_text_stored": false,
  "expires_at": "datetime"
}
```

### 4.2 검사표 OCR intake

Endpoint:

```text
POST /api/v1/regulated-inputs/lab-results/ocr
```

Feature flag:

- `FEATURE_LAB_RESULT_OCR_INTAKE=false` 기본값 유지

필수 동의:

- `LAB_RESULT_OCR_INTAKE` 신규 consent type
- `SENSITIVE_HEALTH_ANALYSIS`
- OCR provider가 외부이면 `EXTERNAL_OCR_PROCESSING`

Response:

```json
{
  "document_id": "uuid",
  "document_type": "lab_result",
  "status": "requires_confirmation",
  "recognized_items": [
    {
      "test_name_text": "visible text only",
      "value_text": "visible text only",
      "unit_text": "visible text only",
      "reference_range_text": "visible text only",
      "confidence": 0.79,
      "requires_user_confirmation": true
    }
  ],
  "warnings": ["검사 결과 해석은 담당 의료진과 상담해야 합니다."],
  "consult_professional_cta": {
    "type": "consult_professional",
    "action": "contact_clinician"
  },
  "raw_image_stored": false,
  "raw_ocr_text_stored": false,
  "expires_at": "datetime"
}
```

### 4.3 사용자 확인 endpoint

Endpoint:

```text
POST /api/v1/regulated-inputs/{document_id}/confirm
```

역할:

- preview가 current user 소유인지 확인
- preview status가 `requires_confirmation`인지 확인
- TTL 만료 여부 확인
- 사용자가 수정/확인한 structured field만 저장
- 상담 CTA acknowledgment를 저장

금지:

- confirm 시점에도 복용량 변경 안내 생성 금지
- 검사 결과 질병 해석 생성 금지
- confirm 전 medication/safety workflow 전달 금지

## 5. DB 설계 초안

### 5.1 `regulated_documents`

목적: 처방전/검사표 OCR preview의 공통 lifecycle 관리.

주요 필드:

| 필드 | 설명 |
| --- | --- |
| `id` | UUID primary key |
| `owner_subject_hash` | HMAC owner id. raw subject 저장 금지 |
| `document_type` | `prescription`, `lab_result` |
| `status` | `requires_confirmation`, `confirmed`, `expired`, `deleted`, `failed` |
| `image_sha256` | 원문 이미지 hash |
| `image_mime_type` | `image/jpeg`, `image/png`, `image/webp` |
| `image_size_bytes` | 업로드 크기 |
| `ocr_provider` | provider 식별자 |
| `ocr_text_hash` | raw OCR text fingerprint |
| `parsed_snapshot` | OCR parser가 만든 structured candidate. raw OCR text 금지 |
| `warning_codes` | 안전한 warning code |
| `consult_professional_cta` | CTA payload |
| `raw_image_deleted_at` | 원문 이미지 삭제 완료 시각 |
| `expires_at` | preview 만료 시각 |
| `confirmed_at` | 사용자 확인 시각 |
| `created_at`, `updated_at` | lifecycle 추적 |

금지 컬럼:

- `raw_image`
- `raw_image_bytes`
- `image_base64`
- `raw_ocr_text`
- `diagnosis`
- `treatment_recommendation`
- `dose_change_instruction`

### 5.2 `prescription_items`

목적: 사용자가 확인한 처방전 항목 저장.

주요 필드:

- `regulated_document_id`
- `medication_name_text`
- `dose_text`
- `frequency_text`
- `period_text`
- `route_text`
- `prescribed_date`
- `confidence`
- `source`: `ocr_candidate`, `user_corrected`
- `sort_order`

금지:

- `recommended_dose`
- `dose_change_instruction`
- `stop_medication_instruction`
- `substitute_medication`

### 5.3 `lab_result_items`

목적: 사용자가 확인한 검사표 항목 저장.

주요 필드:

- `regulated_document_id`
- `test_name_text`
- `value_text`
- `unit_text`
- `reference_range_text`
- `measured_at`
- `confidence`
- `source`: `ocr_candidate`, `user_corrected`
- `sort_order`

금지:

- `diagnosis`
- `disease_probability`
- `treatment_recommendation`
- `medication_adjustment`

## 6. Service 설계

패키지 후보:

```text
src/regulated/
  __init__.py
  documents.py
  consent_gate.py
  ocr_intake.py
  prescription_parser.py
  lab_result_parser.py
  safety_text.py
```

API router 후보:

```text
src/api/v1/regulated_inputs.py
```

schema 후보:

```text
src/models/schemas/regulated.py
```

DB 모델 후보:

```text
src/models/db/regulated.py
```

핵심 service:

- `evaluate_regulated_document_gate(settings, user_consents, document_type)`
- `create_prescription_ocr_preview(...)`
- `create_lab_result_ocr_preview(...)`
- `confirm_regulated_document(...)`
- `assert_no_blocked_medical_outputs(payload)`
- `build_consult_professional_cta(document_type)`

OCR parser 규칙:

- OCR adapter는 보이는 텍스트만 반환한다.
- parser는 OCR text에서 field candidate만 만든다.
- LLM을 쓰더라도 질병명, 치료, 복용량 변경을 생성하지 않는 system prompt와 output schema를 별도 둔다.
- raw OCR text와 raw model response는 DB, log, audit event에 저장하지 않는다.

## 7. 구현 플랜

### RGI-0. 설계 문서와 sign-off 조건 고정

- 본 문서를 P4 기준 문서로 사용한다.
- docs/36 P4와 dev checklist에 링크한다.
- legal/privacy/security review 전까지 production 활성화를 금지한다.

완료 기준:

- default-off flag와 intake-only 원칙이 docs/15, docs/36, docs/42에서 충돌하지 않는다.

### RGI-1. Consent와 settings gate

- `ConsentType.PRESCRIPTION_OCR_INTAKE` 추가
- `ConsentType.LAB_RESULT_OCR_INTAKE` 추가
- active consent policy 추가
- `Settings` production guard 유지
- external OCR 사용 시 `EXTERNAL_OCR_PROCESSING` 동의도 요구

검증:

- feature flag default-off test
- production에서 sign-off 없이 flag true이면 validation error
- 전용 동의 없으면 403

### RGI-2. DB migration과 schema

- `regulated_documents`
- `prescription_items`
- `lab_result_items`
- raw image/raw OCR text/diagnosis/dose-change 금지 컬럼 test

검증:

- Alembic script head 갱신
- ORM metadata test
- deletion request에 regulated rows 포함

### RGI-3. OCR intake service

- 처방전 OCR preview service
- 검사표 OCR preview service
- image validation 재사용
- OCR adapter/factory 재사용
- raw image memory-only 처리
- OCR text hash만 저장
- parsed structured candidate 저장
- CTA 포함 response 반환

검증:

- flag off이면 endpoint 노출 차단
- consent missing이면 403
- raw image/raw OCR text 저장 금지
- OCR 실패 시 안전한 warning만 반환

### RGI-4. 사용자 확인 endpoint

- `POST /api/v1/regulated-inputs/{document_id}/confirm`
- owner hash scope 확인
- preview TTL 확인
- user-corrected structured field 저장
- `confirmed_at` 기록
- confirm 전 downstream 전달 차단

검증:

- 다른 사용자 document confirm 금지
- expired preview confirm 금지
- confirm 전 medication/safety workflow 호출 없음
- confirm 후에도 직접 복용량 변경 안내 없음

### RGI-5. 원문 이미지 자동삭제

- MVP는 memory-only로 `raw_image_stored=false`
- async OCR이 필요할 경우 별도 `sensitive_document_objects` table과 TTL worker 추가
- `sensitive_document_original_image_retention_seconds=0` 기본값 유지
- OCR 완료 직후 `raw_image_deleted_at` 기록

검증:

- raw image DB 저장 금지
- temporary object storage 사용 시 TTL 만료 삭제 test
- delete all user data에서 regulated artifacts 삭제

### RGI-6. 직접 복용량 변경 안내 금지 테스트

- response schema, OpenAPI examples, warning/CTA 문구에서 금지 표현 검사
- parser output에 blocked field가 있으면 validation error
- `/api/v1/medications/change-dose`, `/api/v1/prescriptions/create` endpoint 부재 test 유지

금지 표현 예:

- “오늘부터 절반만”
- “복용량을 늘리세요”
- “복용을 중단하세요”
- “다른 약으로 바꾸세요”
- “진단됩니다”
- “치료하세요”

검증:

- `test_regulated_outputs_do_not_include_dose_change_advice`
- `test_openapi_examples_avoid_regulated_medical_advice`
- `test_blocked_endpoint_patterns_are_not_registered`

### RGI-7. 발주처/팀 리뷰 산출물

- endpoint contract 문서
- consent 문구 문서
- raw image deletion evidence
- 금지 표현 테스트 결과
- 전문가 상담 CTA response example

완료 기준:

- reviewer가 이 기능을 의료 판단이 아니라 intake preview로 판단할 수 있는 evidence가 있다.

## 8. 테스트 매트릭스

| 테스트 | 목적 |
| --- | --- |
| `test_prescription_ocr_flag_default_off` | 처방전 OCR endpoint 기본 비활성 |
| `test_lab_result_ocr_flag_default_off` | 검사표 OCR endpoint 기본 비활성 |
| `test_prescription_ocr_requires_sensitive_consent` | 처방전 전용 민감 동의 강제 |
| `test_lab_result_ocr_requires_sensitive_consent` | 검사표 전용 민감 동의 강제 |
| `test_external_ocr_requires_external_ocr_consent` | 외부 OCR 동의 강제 |
| `test_prescription_preview_stores_no_raw_image_or_ocr_text` | 원문 이미지/OCR text 저장 금지 |
| `test_lab_preview_stores_no_diagnosis_or_treatment_fields` | 검사표 진단/치료 필드 금지 |
| `test_confirm_requires_user_review` | 사용자 확인 전 저장 확정 금지 |
| `test_confirm_rejects_expired_preview` | TTL 만료 preview confirm 금지 |
| `test_consult_professional_cta_present` | 상담 CTA 항상 포함 |
| `test_dose_change_advice_is_blocked` | 직접 복용량 변경 안내 금지 |
| `test_delete_all_user_data_removes_regulated_documents` | 사용자 삭제 요청 반영 |

## 9. PR 분리 권장안

1. `docs(regulated): define prescription and lab OCR intake plan`
   - 이유: regulated intake 범위와 금지 output을 팀 기준으로 먼저 고정하기 위함.
2. `feat(privacy): add regulated document OCR consent gates`
   - 이유: 처방전/검사표 전용 민감 동의를 일반 OCR 동의와 분리하기 위함.
3. `feat(db): add regulated document intake tables`
   - 이유: raw image/raw OCR text를 저장하지 않는 schema를 먼저 검증하기 위함.
4. `feat(regulated): add intake-only OCR preview endpoints`
   - 이유: OCR 결과를 사용자 확인 preview로만 제공하기 위함.
5. `feat(regulated): add user confirmation flow`
   - 이유: 사용자가 확인한 structured field만 downstream 저장 대상으로 만들기 위함.
6. `fix(regulated): block direct dose-change advice`
   - 이유: 처방 변경, 복용량 변경, 약 중단 안내가 API response와 examples에 섞이지 않게 하기 위함.

## 10. 이번 단계의 결론

처방전/검사표 OCR intake는 OCR 기능처럼 보이지만 실제 위험은 OCR보다 해석과 행동 지시에 있다. 따라서 첫 구현은 원문 이미지 memory-only 처리, 별도 민감 동의, preview TTL, 사용자 확인, 상담 CTA, 금지 표현 테스트를 한 묶음으로 가져가야 한다.

구현 순서는 `consent/settings gate -> DB schema -> OCR preview endpoint -> confirmation endpoint -> deletion/auto-delete -> dose-change blocker tests`가 적절하다. 이 순서를 벗어나 추천, 진단, 복용량 변경, medication workflow로 바로 연결하면 P4 범위를 넘어선다.

## 11. 구현 반영 상태

2026-05-15 기준으로 본 문서의 MVP 범위를 백엔드에 반영했다.

구현된 항목:

- `POST /api/v1/regulated-inputs/prescriptions/ocr`
- `POST /api/v1/regulated-inputs/lab-results/ocr`
- `POST /api/v1/regulated-inputs/{document_id}/confirm`
- `PRESCRIPTION_OCR_INTAKE`, `LAB_RESULT_OCR_INTAKE` consent type과 active policy
- `REGULATED_DOCUMENT_PREVIEW_TTL_MINUTES`, `SENSITIVE_DOCUMENT_ORIGINAL_IMAGE_RETENTION_SECONDS=0` 설정
- `regulated_documents`, `prescription_items`, `lab_result_items` DB 모델과 Alembic migration
- 원문 이미지 request-memory 처리, `raw_image_stored=false`, `raw_ocr_text_stored=false` 응답
- 전문가 상담 CTA 응답
- 직접 복용량 변경, 약 중단, 진단, 치료 권고 문구 차단 guard와 테스트

운영 전 남은 항목:

- 법무/인허가 리뷰
- 운영 sign-off 후 feature flag 활성화
- 실제 OCR provider smoke test는 명시 opt-in 환경에서만 수행
- 비동기 OCR 또는 임시 object storage가 필요할 경우 별도 retention sign-off와 삭제 실패 audit 구현
