# 22. P1-4 Supplement Matching and Registration API

> 상태: 구현 완료 | 기준일: 2026-05-12 | 범위: 사용자 확인 영양제 등록, deterministic 제품 매칭, 조회, soft delete

## 1. 목적

P1-4는 P1-2/P1-3에서 만든 preview를 사용자가 확인한 뒤 실제 사용자 영양제 기록으로 승격하는 단계다. OCR/LLM 결과는 최종 데이터가 아니며, `POST /api/v1/supplements`는 `user_confirmed=true` payload만 저장한다.

이 단계에서 식약처/MFDS 실시간 조회나 LLM 기반 제품 확정은 하지 않는다. 이미 적재된 `supplement_products` reference row를 보수적인 deterministic matching으로만 연결하고, 기준을 만족하지 못하면 `matched_product_id`를 `NULL`로 둔다.

## 2. 구현 범위

- `POST /api/v1/supplements` 501 stub 제거
- `GET /api/v1/supplements` 501 stub 제거
- `GET /api/v1/supplements/{supplement_id}` 501 stub 제거
- `DELETE /api/v1/supplements/{supplement_id}` 501 stub 제거
- `sensitive_health_analysis` 동의 확인
- `owner_subject` 서버 생성 및 owner-scoped 조회
- `analysis_id`가 있는 경우 preview 상태·소유자·만료 검증
- user-confirmed supplement와 ingredient row 저장
- reference product deterministic matching
- preview `status=confirmed`, `confirmed_at`, `match_snapshot` 업데이트
- soft delete용 `deleted_at` 설정
- 민감 health data audit event 기록

## 3. 제외 범위

- MFDS API 실시간 조회
- OCR adapter public 연결
- LLM 기반 제품 매칭
- 제품 매칭 강제 확정
- 영양제 복용량 변경 추천
- 의학적 진단·치료 조언

## 4. 구현 파일

| 파일 | 역할 |
|---|---|
| `backend/src/services/supplement_matching.py` | 제품명·제조사·성분 overlap 기반 deterministic matching |
| `backend/src/services/supplement_registration.py` | 등록, list, detail, soft delete service |
| `backend/src/api/v1/supplements.py` | P1-4 route 구현, consent, audit, error mapping |
| `backend/src/models/schemas/supplement.py` | confirmed ingredient input, strict request body schema |
| `backend/src/api/v1/contract.py` | `p1_4_registration_ready` contract status |
| `backend/tests/unit/services/test_supplement_matching.py` | matching 단위 테스트 |
| `backend/tests/unit/services/test_supplement_registration.py` | registration service 단위 테스트 |
| `backend/tests/integration/api/test_supplement_registration_api.py` | API route 통합 테스트 |

## 5. API 동작

| API | 구현 상태 | 주요 보안 조건 |
|---|---|---|
| `POST /api/v1/supplements` | 구현 완료 | `supplement:write`, `sensitive_health_analysis`, `user_confirmed=true` |
| `GET /api/v1/supplements` | 구현 완료 | `supplement:read`, current owner only |
| `GET /api/v1/supplements/{supplement_id}` | 구현 완료 | `supplement:read`, non-owner는 404 |
| `DELETE /api/v1/supplements/{supplement_id}` | 구현 완료 | `supplement:delete`, soft delete |

OpenAPI `x-contract-status`는 위 4개 API에서 `p1_4_registration_ready`를 사용한다.

## 6. 매칭 알고리즘

1. 입력 `display_name`, `manufacturer`, ingredient display name/code를 NFKC 정규화, casefold, 공백 collapse로 표준화한다.
2. active `supplement_products`를 최대 200개까지 조회한다.
3. 제품명, 제조사, 성분 overlap을 점수화한다.
4. 상위 5개 후보를 `match_snapshot.matched_product_candidates`에 저장한다.
5. top score가 `0.92` 이상이고 제품명 유사도가 `0.90` 이상일 때만 `matched_product_id`를 확정한다.
6. 기준 미달이면 후보만 보존하고 사용자 영양제의 `matched_product_id`는 `NULL`로 둔다.

Python `difflib.SequenceMatcher`는 사람이 보기에 가까운 문자열 유사도를 계산하는 도구이며 의미 기반 매칭이 아니다. 따라서 자동 확정 threshold는 보수적으로 유지한다.

## 7. 저장 데이터

| 테이블 | 저장 내용 |
|---|---|
| `user_supplements` | owner, source preview id, matched product id, display name, manufacturer, serving snapshot, intake schedule |
| `user_supplement_ingredients` | display name, nutrient code, amount, unit, confidence, source, sort order |
| `supplement_analysis_runs` | confirmed status, confirmed timestamp, match snapshot, source manifest version |

API 응답에는 `owner_subject`, `source_analysis_run_id`, `matched_product_id`, preview raw snapshot, OCR text hash, deleted timestamp를 노출하지 않는다.

## 8. 보안 결정

1. **Mass assignment 차단**
   `UserSupplementCreate`와 하위 request schema는 `extra="forbid"`를 사용한다. 클라이언트가 `owner_subject`, `matched_product_id`, `confirmed_at` 등을 보낼 수 없다.

2. **Owner scope 강제**
   `analysis_id`, `supplement_id` 조회는 항상 `owner_subject == iss::sub` 조건을 포함한다. non-owner와 missing row는 모두 404로 처리한다.

3. **동의 분리**
   이미지 intake는 `ocr_image_processing`, 최종 영양제 저장은 `sensitive_health_analysis`를 요구한다.

4. **영양소 코드 allowlist**
   confirmed ingredient의 `nutrient_code`는 `data/reference/nutrient_codes.json`에 있는 값만 허용한다.

5. **Preview 재사용 방지**
   expired, already confirmed, failed preview는 409로 차단한다.

6. **삭제 정책**
   일반 delete API는 soft delete로 앱 노출만 제거한다. 전체 사용자 데이터 삭제 요청은 privacy service의 hard delete 경로가 처리한다.

## 9. 검증

```bash
cd yeong-Lemon-Aid/backend
./.venv/bin/python -m pytest -o addopts='' \
  tests/unit/services/test_supplement_matching.py \
  tests/unit/services/test_supplement_registration.py \
  tests/integration/api/test_supplement_registration_api.py \
  tests/integration/api/test_p1_api_contract.py \
  tests/integration/api/test_openapi_examples.py
```

검증 결과: 22개 테스트 통과.

전체 백엔드 회귀 확인:

```bash
./.venv/bin/python -m pytest
```

검증 결과: 183개 테스트 통과, 1개 skip, coverage 89.01%.

## 10. 후속 단계

1. P1-3b에서 실제 OCR adapter를 연결해 `/supplements/analyze`가 parser service까지 이어지게 한다.
2. 운영 영양제 reference import를 확장해 `supplement_products` 후보 품질을 높인다.
3. ingredient code deterministic alias mapping을 별도 service로 분리한다.
4. 중복 영양제 등록 병합 UX와 duplicate detection 정책을 추가한다.

## 11. 참고한 공식 문서/보안 기준

- FastAPI Request Body: https://fastapi.tiangolo.com/tutorial/body/
- FastAPI Dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Python difflib: https://docs.python.org/3/library/difflib.html
- OWASP API Security Top 10 2023: https://owasp.org/API-Security/editions/2023/en/0x11-t10/
