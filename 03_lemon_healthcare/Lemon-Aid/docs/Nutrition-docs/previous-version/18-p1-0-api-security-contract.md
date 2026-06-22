# 18. P1-0 API/Security Contract

> 상태: 구현 계약 동결 | 기준일: 2026-05-12 | 범위: P1 영양제, 헬스 데이터, 대시보드 API

## 1. 목적

P1-0은 OCR, LLM, DB 저장 로직을 바로 완성하는 단계가 아니다. 모바일, OCR/LLM, 백엔드 저장 계층이 같은 API 계약을 보고 병렬 구현할 수 있도록 인증 스코프, 요청/응답 스키마, 동의 요구사항, OpenAPI 노출 방식을 먼저 고정한다.

## 2. 보안 원칙

- 모든 P1 API는 OAuth/OIDC Bearer access token을 사용한다.
- 백엔드는 외부 Identity Provider가 발급한 JWT를 검증하는 resource server 역할만 담당한다.
- owner 값은 클라이언트 요청이 아니라 검증된 `iss`와 `sub`에서만 만든다.
- API별 권한은 중앙 scope registry의 `ApiScope`로만 정의한다.
- 사용자 확인 전 OCR/LLM preview는 최종 섭취 데이터로 저장하지 않는다.
- 영양제 라벨 원본 이미지는 P1 기본 경로에서 저장하지 않는다.
- OCR/LLM 원문, Authorization header, 이미지 binary는 운영 로그에 저장하지 않는다.

## 3. Scope Registry

| Scope | 목적 | 적용 API |
|---|---|---|
| `supplement:read` | 현재 사용자 영양제 기록 조회 | `GET /api/v1/supplements`, `GET /api/v1/supplements/{supplement_id}` |
| `supplement:write` | 영양제 라벨 preview 생성, 사용자 확인 저장 | `POST /api/v1/supplements/analyze`, `POST /api/v1/supplements` |
| `supplement:delete` | 현재 사용자 영양제 기록 삭제 | `DELETE /api/v1/supplements/{supplement_id}` |
| `health:write` | HealthKit/Health Connect 일별 집계 sync | `POST /api/v1/health/sync` |
| `health:read` | 현재 사용자 헬스 요약 조회 | P1 이후 헬스 조회 API |
| `dashboard:read` | 현재 사용자 대시보드 summary 조회 | `GET /api/v1/dashboard/summary` |

기존 `analysis:*`, `privacy:*`는 유지한다. `supplement:*`는 입력/저장 도메인, `analysis:*`는 계산 결과 저장 도메인으로 분리한다.

## 4. Consent Contract

| API | Required consent | 이유 |
|---|---|---|
| `POST /api/v1/supplements/analyze` | `ocr_image_processing` | 영양제 라벨 이미지를 OCR 처리한다. |
| `POST /api/v1/supplements` | `sensitive_health_analysis` | 사용자 확인 후 섭취 관련 구조화 데이터를 저장한다. |
| `POST /api/v1/health/sync` | `health_device_data` | 모바일 헬스 데이터 집계를 수집한다. |
| `GET /api/v1/dashboard/summary` | `sensitive_health_analysis` | 사용자별 건강관리 summary를 구성한다. |

## 5. Frozen Endpoints

| Method | Path | Request | Response | Scope |
|---|---|---|---|---|
| `POST` | `/api/v1/supplements/analyze` | `multipart/form-data` image, `client_request_id` | `SupplementAnalysisPreview` | `supplement:write` |
| `POST` | `/api/v1/supplements` | `UserSupplementCreate` | `UserSupplementResponse` | `supplement:write` |
| `GET` | `/api/v1/supplements` | `limit`, `offset` | `UserSupplementListResponse` | `supplement:read` |
| `GET` | `/api/v1/supplements/{supplement_id}` | path id | `UserSupplementResponse` | `supplement:read` |
| `DELETE` | `/api/v1/supplements/{supplement_id}` | path id | `204` | `supplement:delete` |
| `POST` | `/api/v1/health/sync` | `HealthSyncRequest` | `HealthSyncResponse` | `health:write` |
| `GET` | `/api/v1/dashboard/summary` | `as_of`, `days` | `DashboardSummaryResponse` | `dashboard:read` |

P1-0 구현은 위 endpoint를 OpenAPI에 노출하지만 실제 OCR, LLM, DB 저장 로직은 `501 p1_contract_stub`으로 막는다. P1-2 이후 `POST /api/v1/supplements/analyze`는 이미지 intake까지 구현되어 `x-contract-status: p1_2_intake_ready`를 사용한다. P1-4 이후 `POST /api/v1/supplements`, `GET /api/v1/supplements`, `GET /api/v1/supplements/{supplement_id}`, `DELETE /api/v1/supplements/{supplement_id}`는 사용자 확인 등록·조회·삭제까지 구현되어 `x-contract-status: p1_4_registration_ready`를 사용한다. P1-6 이후 `POST /api/v1/health/sync`는 HealthKit/Health Connect 일별 aggregate 저장까지 구현되어 `x-contract-status: p1_6_health_sync_ready`를 사용한다. 실제 OCR adapter public 연결은 여전히 후속 단계 범위다.

## 6. OpenAPI Contract

각 P1 endpoint는 다음 확장 필드를 포함한다.

- `x-contract-status: p1_0_contract_stub`
- `x-required-scopes`
- `x-required-consents`

이는 모바일 앱과 API 테스트가 구현 완료 전에도 동일한 계약을 참조하도록 하기 위한 임시 계약 고정 장치다.

## 7. 검증 항목

- P1 endpoint가 모두 `/api/v1` 아래 등록된다.
- 각 endpoint에 `BearerAuth` security가 표시된다.
- 각 endpoint의 `x-required-scopes`와 `x-required-consents`가 누락되지 않는다.
- JWT mode에서 인증 없는 요청은 401을 반환한다.
- development mode에서는 계약 stub이 501을 반환한다.
- OpenAPI 예시는 금지 표현을 포함하지 않는다.

## 8. 참고한 공식 문서/표준

- FastAPI OAuth2 scopes: https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/
- FastAPI file uploads: https://fastapi.tiangolo.com/tutorial/request-files/
- OpenAPI Specification security: https://swagger.io/specification/
- RFC 6750 Bearer Token Usage: https://www.rfc-editor.org/rfc/rfc6750
- RFC 8725 JWT Best Current Practices: https://www.rfc-editor.org/rfc/rfc8725
- RFC 9068 JWT Profile for OAuth 2.0 Access Tokens: https://www.rfc-editor.org/rfc/rfc9068
