# 05. FORCE RLS 롤아웃 (마이그레이션 + 세션 배선, 라이브 미적용)

> 브랜치 성격: feat(db) — 로드맵, 파일만
> 대응 커밋: `ed54f82` (구현), `641ce27` (설계문서)
> 핵심 파일: `backend/alembic/versions/0023a~0023c`, `src/db/rls_context.py`, `scripts/db_poc/force_rls_poc.sql`

---

## 1. 배경

핵심 사용자 데이터 테이블에 DB 레벨 RLS는 ENABLE 되어 있으나, 요청 경로가 `lemon`(superuser + table owner)로 접속해 **RLS·FORCE 모두 우회**된다. 진짜 행 단위 격리를 하려면 비superuser 요청 역할 + per-row 정책 + FORCE가 필요하다.

---

## 2. 작성 산출물 (라이브 미적용)

- **0023a** `create_lemon_app_request_role.py`
  - 비superuser 역할 `lemon_app` 생성 (LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE **NOBYPASSRLS**)
  - 사용자데이터 28테이블 CRUD / 카탈로그 9테이블 SELECT / 시퀀스 USAGE·SELECT
  - **비밀번호는 마이그레이션에 미포함**(운영자가 시크릿으로 `ALTER ROLE ... PASSWORD` 별도 설정)
- **0023b** `create_rls_owner_policies.py`
  - 4 아키타입 per-row 정책 32개: plaintext owner(10) / hashed owner(10) / FK child(8) / catalog read(4)
  - GUC `current_setting('app.current_subject'|'_hash', true)` 기준, 미설정 시 0행(fail-closed)
  - 8개 FK child 컬럼은 라이브 스키마와 실측 대조
- **0023c** `force_row_level_security.py`
  - 32테이블 `FORCE ROW LEVEL SECURITY` (downgrade=`NO FORCE`, 정책/역할 보존)
  - ⚠️ `lemon_app` 접속 검증 전 적용 금지
- **세션 배선** `src/db/rls_context.py`
  - `set_request_rls_context()`: `set_config(name, value, true)`로 트랜잭션-로컬 GUC 주입
  - bind 파라미터 → SQL 인젝션 불가, commit/rollback 시 자동 해제 → 풀 누수 없음
  - **현재 호출부 없음(inert)** — superuser 접속에선 GUC 무시되어 동작 불변
- **POC** `scripts/db_poc/force_rls_poc.sql` — 4 아키타입 throwaway DB 증명

---

## 3. 증명 ✅ (throwaway DB)

- `alembic upgrade head`(0001…0023c) → **forced=32 / policies=32 / role=1 / head=0023c**
- downgrade `0023c→0023b` → **forced=0** (롤백 동작)
- 종료 후 임시 DB·`lemon_app` 역할 drop으로 클러스터 원복
- **라이브 `lemon` DB 무변경 확인**: forced=0 / lemon_app=0 / head=0022
- 단위테스트 `test_rls_context.py` 3 passed, black/ruff/py_compile 통과

---

## 4. 라이브 적용 전 남은 단계 (전부 승인 게이트)

1. `lemon_app` 비밀번호 시크릿 발급 → `ALTER ROLE lemon_app PASSWORD '<secret>'` (마이그레이션 밖)
2. 세션 배선 활성화: 요청 트랜잭션 시작부에서 `set_request_rls_context()` 호출 + `AuthenticatedUser`→subject 해석 연결
3. 스테이징: 0023a/b/c 적용 → `DATABASE_URL`을 `lemon_app`로 전환 → 통합테스트
4. 프로덕션: 스테이징 green 후 별도 승인
