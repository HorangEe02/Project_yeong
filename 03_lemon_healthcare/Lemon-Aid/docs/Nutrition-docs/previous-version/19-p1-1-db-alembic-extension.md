# 19. P1-1 DB/Alembic Extension

> 상태: 구현 완료 | 기준일: 2026-05-12 | 범위: P1 영양제, 헬스 데이터 저장 기반

## 1. 목적

P1-1은 P1-0에서 동결한 API/보안 계약을 실제 저장 계층으로 연결하기 위한 DB/Alembic 확장 단계다. OCR/LLM 분석 로직과 모바일 동기화 서비스는 아직 구현하지 않고, 후속 서비스가 안전하게 사용할 owner-scoped 테이블과 마이그레이션을 먼저 고정한다.

## 2. 설계 원칙

- 사용자 소유 데이터는 클라이언트가 보낸 `user_id`가 아니라 인증된 JWT의 `iss`와 `sub`에서 만든 `owner_subject`로만 저장한다.
- 영양제 라벨 원본 이미지와 OCR 원문은 기본 저장하지 않는다. 이미지와 OCR 텍스트는 SHA-256 해시 또는 구조화 snapshot만 저장한다.
- 식약처/운영 수집 영양제 제품 데이터는 reference table로 분리하고, 사용자 데이터 삭제 대상에서 제외한다.
- 사용자 확인 전 OCR/LLM 결과는 `supplement_analysis_runs` preview로 분리하고, 확인된 복용 데이터는 `user_supplements`에 저장한다.
- HealthKit/Health Connect 원천 이벤트 전체가 아니라 일별 요약과 sync batch 결과 snapshot만 저장한다.
- `DELETE /api/v1/me/data-deletion-requests`의 all-user-data 경로가 P1 owner-scoped 테이블까지 삭제하도록 확장한다.

## 3. 추가 테이블

| 테이블 | 소유 범위 | 목적 |
|---|---|---|
| `supplement_products` | reference | 식약처/운영 source의 영양제 제품 마스터 |
| `supplement_product_ingredients` | reference | 제품별 성분, 함량, 단위, nutrient code 매핑 |
| `supplement_analysis_runs` | owner-scoped | 영양제 라벨 OCR/LLM preview, 이미지/텍스트 해시, 파싱 snapshot |
| `user_supplements` | owner-scoped | 사용자가 확인한 최종 영양제 복용 데이터 |
| `user_supplement_ingredients` | owner-scoped | 사용자 확인 성분·함량 데이터 |
| `health_sync_batches` | owner-scoped | 모바일 헬스 데이터 sync 요청 단위의 수락/거절 결과 |
| `health_daily_summaries` | owner-scoped | 일별 걸음수, 체중, 안정시 심박, 활동에너지 요약 |

## 4. 제약조건과 보안 보강

- `source_provider + source_product_id`, `owner_subject + client_request_id`, `owner_subject + client_batch_id`, `owner_subject + measured_date + source_platform`에 unique constraint를 둔다.
- 이미지 MIME type은 `image/jpeg`, `image/png`, `image/webp`만 허용하는 DB check constraint를 둔다.
- OCR confidence, 사용자 성분 confidence, 성분 함량, 헬스 수치에는 범위 check constraint를 둔다.
- owner 조회 패턴에 맞춰 `owner_subject + created_at`, `owner_subject + status + created_at`, `owner_subject + measured_date`, `owner_subject + synced_at` 인덱스를 둔다.
- 삭제 요청 처리 시 `health_daily_summaries`, `health_sync_batches`, `supplement_analysis_runs`, `user_supplements`, `user_supplement_ingredients`를 함께 삭제하고 audit log에는 raw snapshot이 아니라 삭제 count만 저장한다.

## 5. 구현 파일

- ORM: `backend/src/models/db/supplement.py`, `backend/src/models/db/health.py`
- 모델 registry: `backend/src/models/db/__init__.py`
- Alembic: `backend/alembic/versions/0004_create_p1_supplement_health_tables.py`
- Privacy deletion: `backend/src/services/privacy.py`
- 테스트: `backend/tests/unit/db/test_models.py`, `backend/tests/unit/db/test_alembic_setup.py`, `backend/tests/unit/services/test_privacy.py`

## 6. 후속 구현 기준

1. P1-2는 `supplement_analysis_runs`에 preview 저장 API를 연결한다.
2. P1-3은 식약처/운영 영양제 source import를 `supplement_products`와 `supplement_product_ingredients`에 적재한다.
3. P1-4는 사용자 확인 저장 API를 `user_supplements`와 `user_supplement_ingredients`에 연결한다.
4. P1-5는 `health_daily_summaries`, 기존 `analysis_results`를 대시보드 요약에 연결했고, P1-6은 `health_sync_batches`, `health_daily_summaries`를 HealthKit/Health Connect sync 저장 API에 연결했다.

## 7. 참고한 공식 문서

- SQLAlchemy Declarative Table Configuration: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
- Alembic Operation Reference: https://alembic.sqlalchemy.org/en/latest/ops.html
- PostgreSQL JSON Types: https://www.postgresql.org/docs/current/datatype-json.html
