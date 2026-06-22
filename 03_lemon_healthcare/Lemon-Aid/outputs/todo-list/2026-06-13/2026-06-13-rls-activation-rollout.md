# FORCE RLS 활성화 롤아웃 (2026-06-13)

> 근거: `docs/2026-05-31-force-rls-rollout-design.md` + 마이그레이션 0023a/b/c + 0041. 이 문서는 **Stage-1 요청 배선**(코드)과 **Stage-2 활성화**(인프라) 경계를 명확히 한다.

## 0. 현 상태 (확인값)

- **정책은 이미 정의됨**: 0023b가 owner-scoped RLS 정책(`lemon_app_owner_rw`/`lemon_app_catalog_read`)을 GUC `app.current_subject`/`app.current_subject_hash` 기준으로 생성. plaintext owner 10테이블·hashed owner 10테이블·child 8테이블·catalog read. **fail-closed**(빈 GUC=0행).
- **`lemon_app` 비-superuser 역할**: 0023a가 NOSUPERUSER·NOBYPASSRLS로 생성 + CRUD/SELECT grant. 0023c가 34테이블에 FORCE ROW LEVEL SECURITY.
- **차단점**: 앱이 **superuser `lemon`으로 접속 → RLS 전면 우회**. `set_request_rls_context`는 존재하나 호출처 0(“inert until wired”).

## 1. Stage-1 — 요청 배선 (코드, 이번 커밋)

- **신규 `get_rls_context_session`**(`src/db/dependencies.py`): `require_current_user`로 인증 주체 확보 → **요청 1트랜잭션**(`async with session.begin()`) 안에서 `set_request_rls_context(subject=build_owner_subject(user), subject_hash=hash_actor_subject(user, settings))` → 세션 yield. superuser 접속 중엔 GUC가 무시되므로 **지금 채택해도 안전**.
- **트랜잭션 모델 결정(중요)**: GUC는 `set_config(is_local=true)`라 트랜잭션 스코프. 따라서 이 의존성을 쓰는 라우트는 **요청 트랜잭션에 의존**하며 **자체 `session.begin()`/`session.commit()` 금지**(중간 commit 시 GUC 해제). 자체 트랜잭션을 관리하는 라우트는 리팩터 전까지 `get_async_session` 유지.
- **단위 테스트**(`tests/unit/db/test_rls_context_dependency.py`): 트랜잭션 안에서 두 GUC가 주체로부터 설정됨(subject→hash 순), 빈 주체는 세션 작업 전 fail-closed.
- **이번 범위 밖(의도적 연기)**: 40+ 라우트의 `get_async_session`→`get_rls_context_session` 일괄 교체는 블래스트 반경이 커 Stage-1 후속(점진 채택)으로 분리. superuser 접속 중엔 기능 효과 0이므로 서두를 이유 없음.

## 2. Stage-1 후속 — 라우트 점진 채택 (코드)

- owner-scoped 라우트(`require_*` 인증 + owner 필터) 중 **자체 트랜잭션 미관리** 라우트부터 의존성 교체.
- 자체 트랜잭션 라우트(쓰기 경로의 `async with session.begin()`)는 요청-트랜잭션 모델로 리팩터 후 교체.
- 채택 시에도 superuser 접속이면 무해(GUC 무시). 명시적 owner 필터(`WHERE owner_subject==…`)는 정책과 **중복 방어**로 당분간 유지.

## 3. Stage-2 — 활성화 (인프라 게이트, 코드 아님)

1. `lemon_app` 역할 비밀번호 설정(아웃오브밴드 `ALTER ROLE lemon_app PASSWORD` / secret manager).
2. **격리 통합 테스트 통과**(아래 §4) — staging에서 `lemon_app` 접속으로 교차 사용자 격리 검증.
3. `DATABASE_URL`을 `lemon_app`로 전환(staging).
4. 0023c FORCE 적용(이미 정의됨) → 정책 강제 발효.
5. 통합 테스트 그린 확인 후 production 승격.

- **PgBouncer 등 풀러 사용 시 session mode 필수**(`is_local=true`는 트랜잭션 스코프).

## 4. 격리 통합 테스트 명세 (Stage-2 전제, 현 미구현)

- live Postgres + `lemon_app` 역할 픽스처 필요(현 단위 테스트는 fake 세션이라 정책 강제는 검증 못 함).
- 시나리오: `lemon_app` 접속 → GUC=주체A 설정·A행 insert/select → GUC=주체B로 전환 → **A행이 B에게 0행**(격리), 빈 GUC=0행(fail-closed), catalog 테이블은 read 가능.
- 이 테스트가 **전체 설계(역할+GUC+정책+FORCE)를 한 번에 검증** → Stage-2 최대 리스크 제거.

## 5. 불가침 / 제약

- **PR#4 보호: 0023a/b/c·0041 등 alembic 트리 덮어쓰기·되돌리기 금지.** 필요 시 신규 마이그레이션(0045+)만.
- GUC 이름 `app.current_subject`/`app.current_subject_hash` 정확 일치(0023b 정책과 동기).
- superuser(`lemon`)는 FORCE도 우회 — 활성화는 `lemon_app` 접속에서만 발효.
