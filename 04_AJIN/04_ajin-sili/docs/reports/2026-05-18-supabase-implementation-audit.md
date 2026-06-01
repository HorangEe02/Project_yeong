# AJIN AI Assistant Supabase 연동 및 구현 상태 감사 보고서

- 작성일: 2026-05-18
- 대상 경로: `/Users/yeong/99_me/00_github/04_AJIN/ajin-ai-assistant-react`
- 요청 Supabase 프로젝트: https://supabase.com/dashboard/project/ycjuzwltwbeudanjykag
- 감사 관점: 현재 구현 기능, Supabase/Postgres 연동, 보안, 앱 배포 준비도, 문서-코드 일치성

## 1. 결론

현재 프로젝트는 FastAPI + React/Vite 기반의 업무용 AI 어시스턴트 기능이 넓게 구현되어 있으며, 검색, 기안서, 온보딩/챗, 컴플라이언스, 관리자, 설비/현장 모듈까지 라우터와 화면 구조가 상당히 확장되어 있다. 다만 Supabase는 "연동 기반 코드와 마이그레이션 스캐폴드"가 구현된 상태에 가깝고, 현재 로컬 실행 설정 기준으로는 활성화되어 있지 않다.

가장 중요한 결론은 다음과 같다.

| 구분 | 판단 |
| --- | --- |
| 기능 구현 범위 | 넓게 구현됨. OpenAPI 기준 215개 path, 229개 operation 확인 |
| Supabase DB 연동 | `APP_DB_BACKEND=postgres` 기반 코드, Alembic, 마이그레이션 스크립트는 존재하지만 현재 `.env`에는 Supabase/Postgres 연결값 없음 |
| 요청 Supabase 프로젝트 연결 | 코드에서 `ycjuzwltwbeudanjykag` 참조 없음. CLI 원격 확인도 access token 형식 오류로 실패 |
| Supabase Storage | 백엔드 signed upload/download 흐름은 구현됨. 그러나 다운로드 권한 검증 결함이 있어 배포 전 수정 필요 |
| 앱 배포 준비도 | 현재는 PWA 성격의 웹앱에 가까움. 네이티브 Android/iOS 프로젝트는 확인되지 않음 |
| 운영 보안 상태 | production-ready 아님. 토큰 저장, optional auth, RLS 정책 부재, 기본 관리자 계정, source map 등 차단 이슈 존재 |

따라서 이 프로젝트는 "기능 구현과 Supabase 전환 설계가 진행 중인 고도화 단계"로 보는 것이 정확하다. 앱으로 구현 및 배포하려면 Supabase 원격 프로젝트 검증, 보안 모델 정리, Storage 권한 보정, 인증/세션 구조 강화, 모바일/PWA 배포 전략 확정이 선행되어야 한다.

## 2. 공식 문서 기준

이번 검토에서 기준으로 삼은 공식 문서와 보안 표준은 다음과 같다.

- Supabase API keys: https://supabase.com/docs/guides/getting-started/api-keys
- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase Securing your API: https://supabase.com/docs/guides/api/securing-your-api
- Supabase Realtime Postgres Changes: https://supabase.com/docs/guides/realtime/postgres-changes
- Supabase Python Storage signed upload URL: https://supabase.com/docs/reference/python/storage-from-createsigneduploadurl
- Supabase JavaScript Storage signed upload: https://supabase.com/docs/reference/javascript/storage-from-uploadtosignedurl
- OWASP HTML5 Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html
- OWASP Session Management Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html

공식 문서 확인 기준에서, Supabase secret/service role 계열 키는 공개 클라이언트에 노출하면 안 되며, RLS는 테이블 노출 권한과 별개로 행 접근 정책을 설계해야 한다. 또한 브라우저 localStorage에 세션 식별자나 민감 토큰을 저장하는 방식은 XSS 발생 시 탈취 위험이 커서 앱 배포 기준으로 재검토가 필요하다.

## 3. 확인 범위와 한계

확인한 항목:

- 로컬 파일 시스템과 Git 저장소 구조
- backend/frontend 라우터와 주요 서비스 구현
- Supabase/Postgres 관련 설정, Alembic, Storage, migration script
- `.env`, `.env.example`, `.env.docker`, `frontend/.env.development`의 변수명 기준 설정 상태
- OpenAPI 문서의 path/operation 수
- Supabase CLI 설치 및 원격 프로젝트 조회 가능 여부
- 일부 핵심 테스트와 frontend production build

확인하지 못한 항목:

- Supabase 대시보드 내부 테이블, bucket, RLS policy, advisor 결과
- `ycjuzwltwbeudanjykag` 프로젝트의 실제 운영 설정
- 전체 pytest suite
- 실제 Supabase Storage signed upload의 end-to-end 업로드 성공 여부

한계 사유:

- Supabase MCP/connector 실행 도구가 현재 세션에 노출되지 않았다.
- `supabase projects list -o json` 실행 결과 access token 형식 오류가 발생했다.
- 현재 로컬 `.env`에는 `APP_DB_BACKEND`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`가 설정되어 있지 않다.

## 4. 현재 기능 구현 상태

OpenAPI 문서 기준으로 215개 path, 229개 operation이 확인되었다. 태그별 operation 수는 다음과 같다.

| 태그 | operation 수 |
| --- | ---: |
| admin | 48 |
| onboarding | 31 |
| draft | 27 |
| equipment | 19 |
| compliance | 19 |
| auth | 12 |
| search | 9 |
| admin-scenarios | 9 |
| models | 8 |
| notifications | 6 |
| dashboard | 6 |
| scenarios | 5 |
| idp | 5 |
| employee | 5 |
| storage | 3 |
| feature-flags | 3 |
| export | 3 |
| slack | 2 |
| me | 2 |
| live-alarms | 2 |
| health | 2 |
| feedback | 1 |
| directory | 1 |

README와 일부 문서에는 178개 endpoint라는 설명이 남아 있으므로, 현재 OpenAPI와 문서 간 숫자가 맞지 않는다. 기능 범위가 빠르게 확장되었지만 문서 동기화가 뒤처진 상태로 판단된다.

### 4.1 검색/직원 검색

구현 근거:

- `features/search/`
- `backend/routers/search.py`
- `backend/routers/employee.py`
- `backend/routers/directory.py`
- `features/search/employee/postgres_repository.py`

현재 상태:

- 일반 검색, 직원 검색, directory API 구조가 존재한다.
- 직원 데이터는 기존 SQLite/Chroma 중심 흐름을 유지하면서, Postgres backend가 활성화된 경우 일부 upsert/mirror를 수행하는 구조다.
- Supabase/Postgres가 전체 검색 저장소로 전환된 상태는 아니다.

위험:

- 운영 DB가 Postgres로 전환되더라도 검색 인덱스, SQLite mirror, Chroma 상태가 서로 어긋날 수 있다.
- Postgres 전환 범위가 "주 저장소 전환"인지 "일부 mirror"인지 문서와 코드에서 더 명확히 분리해야 한다.

### 4.2 기안서/문서 자동화

구현 근거:

- `features/draft/`
- `backend/routers/draft.py`
- `backend/routers/export.py`
- `backend/routers/storage.py`
- `frontend/src/routes/draft`

현재 상태:

- 기안서 생성, 규정 기반 문서 작성, export, 파일 첨부 흐름이 구현되어 있다.
- Supabase Storage signed upload/download를 위한 백엔드 API도 존재한다.

위험:

- 기안서와 export 계열 일부 endpoint가 optional auth 패턴에 의존한다.
- Storage signed download의 소유권 검증이 부족하여 다른 사용자의 첨부 파일에 접근할 수 있는 구조적 위험이 있다.

### 4.3 온보딩/챗

구현 근거:

- `features/onboarding/`
- `backend/routers/onboarding.py`
- `frontend/src/routes/onboarding`
- `frontend/src/routes/chat`

현재 상태:

- SOP, quiz, checklist, vision document, gamification, i18n 등 온보딩 기능이 넓게 구현되어 있다.
- 챗/LLM 기반 사용자 경험도 포함되어 있다.

위험:

- LLM, 문서 검색, onboarding endpoint가 공개 배포 환경에서 비용 또는 정보 노출 공격면이 될 수 있다.
- optional auth endpoint는 명시적인 public allowlist가 없으면 운영 보안 판단이 어렵다.

### 4.4 컴플라이언스

구현 근거:

- `features/compliance/`
- `backend/routers/compliance.py`
- `frontend/src/routes/compliance*`

현재 상태:

- 규정 검색, glossary, regulation, alert, crawl/history, RAG 성격의 기능이 구현되어 있다.
- 기능 범위는 넓지만 외부 데이터, crawler, LLM 경로가 섞여 있어 운영 검증이 중요하다.

위험:

- 법규/규정 답변은 최신성, 출처, 환각 방지 정책이 필수다.
- 외부 crawler 또는 RAG 데이터가 Supabase/Postgres 전환 대상인지 명확하지 않다.

### 4.5 관리자/인증/권한

구현 근거:

- `backend/routers/auth.py`
- `backend/routers/admin.py`
- `backend/routers/idp.py`
- `core/auth/`
- `features/admin/`

현재 상태:

- 자체 JWT 기반 인증, admin 기능, TOTP/2FA, 권한 정책, 보안 모니터링 구조가 구현되어 있다.
- Supabase Auth를 사용하는 구조는 아니다. 문서상으로도 AJIN JWT를 유지하고 Supabase는 DB/Storage로 사용하는 방향이다.

위험:

- 서버의 비밀번호 변경 endpoint가 최소 길이 6자만 검사하는 것으로 확인된다.
- 초기 관리자 계정 `admin/admin1234`가 로컬/문서에 남아 있어 production gate가 필요하다.
- 프론트엔드가 access/refresh token을 localStorage 기반 Zustand persist에 저장한다.

### 4.6 설비/현장 모드

구현 근거:

- `features/equipment/`
- `backend/routers/equipment.py`
- `backend/routers/live_alarms.py`
- `backend/services/live_events.py`
- `frontend/src/routes/equipment`
- `frontend/src/routes/equipment-field`

현재 상태:

- 설비 검색, PLC ingest, live alarm, SPC/inspection/mold 관련 기능이 구현되어 있다.
- PWA manifest의 `start_url`이 `/equipment/field`로 설정되어 있어 현장 모드를 앱 첫 화면으로 두려는 의도가 보인다.

위험:

- live alarm 조회/ack endpoint가 인증은 요구하지만 역할 또는 부서 단위 권한 검증은 부족하다.
- Supabase Realtime은 설정 변수만 있고 실제 클라이언트/정책/채널 설계가 확인되지 않는다.

## 5. Supabase/Postgres 연동 상태

### 5.1 환경 설정

`.env.example`에는 다음 Supabase 관련 변수가 존재한다.

- `APP_DB_BACKEND`
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_STORAGE_BUCKET_ATTACHMENTS`
- `SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS`
- `ENABLE_SUPABASE_REALTIME`

그러나 현재 로컬 `.env`에는 위 Supabase/Postgres 핵심 변수가 설정되어 있지 않았다. 따라서 현재 로컬 실행은 Supabase/Postgres가 아니라 기본 SQLite 중심으로 동작할 가능성이 높다.

요청받은 project ref `ycjuzwltwbeudanjykag`는 코드에서 발견되지 않았다. 일반적으로 Supabase URL은 `https://<project-ref>.supabase.co` 형태를 사용하므로, 운영 설정에는 `SUPABASE_URL=https://ycjuzwltwbeudanjykag.supabase.co`가 필요할 가능성이 높다. 다만 현재 로컬 파일에서는 이를 확인할 수 없었다.

### 5.2 DB 전환 구조

구현 근거:

- `core/db.py`
- `alembic/env.py`
- `alembic/versions/20260518_0001_supabase_postgres_foundation.py`
- `scripts/migrate_sqlite_to_postgres.py`
- `scripts/migrate_firestore_export_to_postgres.py`
- `scripts/migrate_rtdb_export_to_postgres.py`

현재 상태:

- `APP_DB_BACKEND=sqlite|postgres` 분기 구조가 구현되어 있다.
- `DATABASE_URL`의 `postgres://` 또는 `postgresql://` 값을 SQLAlchemy `postgresql+psycopg://` 형식으로 정규화하는 코드가 있다.
- Alembic foundation migration은 roles, users, login_history, audit_logs, employees, regulation_changes, live_alarms, feedback_events, draft_versions, chat_messages, attachments, plc_violations 등 핵심 테이블을 생성한다.
- SQLite 대상 Alembic upgrade는 성공했다.

중요한 문제:

- PostgreSQL에서 RLS enable은 수행하지만 실제 policy와 GRANT가 없다.
- Supabase Data API 또는 Realtime을 직접 사용할 계획이라면 `anon`/`authenticated` role grant와 RLS policy 설계가 별도로 필요하다.
- 반대로 FastAPI만 DB에 직접 접근하는 구조라면, Supabase Data API 노출을 막고 backend-only DB 접근 원칙을 문서와 설정으로 고정해야 한다.

### 5.3 Supabase Storage

구현 근거:

- `backend/services/supabase_storage.py`
- `backend/routers/storage.py`
- `frontend/src/api/upload.ts`
- `scripts/migrate_firebase_storage_to_supabase.py`

현재 상태:

- 백엔드에서 Supabase secret key로 signed upload/download URL을 발급한다.
- 프론트엔드는 signed upload URL에 직접 `fetch(..., method: PUT)`으로 파일을 업로드한 뒤 complete API를 호출한다.
- 기존 Firebase Storage export를 Supabase bucket으로 옮기는 migration script가 있다.

중요한 문제:

- signed download endpoint가 `attachment_id` 소유자를 현재 사용자와 비교하지 않는다.
- complete-upload도 현재 사용자와 metadata 소유자를 비교하지 않는다.
- complete-upload는 실제 object가 업로드되었는지 확인하지 않고 metadata 기반으로 signed download URL을 반환한다.
- Supabase 공식 JavaScript signed upload 예시는 `uploadToSignedUrl(path, token, file)` 형태를 사용한다. 현재 수동 `fetch` 방식은 실제 Supabase Storage 응답과 end-to-end 검증이 필요하다.

### 5.4 Realtime

`ENABLE_SUPABASE_REALTIME=false` 설정과 문서 언급은 있으나, 현재 확인한 코드 기준으로 Supabase Realtime client, channel policy, live alarm subscription 구현은 보이지 않았다. live alarm은 backend API를 통해 list/ack하는 구조에 가깝다.

Supabase Realtime을 앱 현장 모드의 핵심 기능으로 사용할 계획이라면 다음이 필요하다.

- publication 대상 table 확정
- RLS policy와 Realtime 권한 정책 확정
- frontend subscription 구현
- offline/reconnect/backfill 정책
- 모바일 네트워크 불안정 상황에서의 재전송 및 중복 처리

## 6. 보안 및 구현 결함

### P0. Supabase 원격 프로젝트와 실제 연결이 확인되지 않음

증거:

- 코드에서 `ycjuzwltwbeudanjykag` 참조 없음
- 현재 `.env`에 Supabase/Postgres 핵심 변수 없음
- `supabase projects list -o json`은 access token 형식 오류로 실패
- Supabase MCP/connector 실행 도구 미노출

영향:

- 요청한 Supabase dashboard project에 실제 테이블, RLS, bucket, secret이 정상 구성되었는지 확인할 수 없다.
- 현재 코드가 로컬에서는 동작해도 배포 시 Supabase 연동이 끊겨 있을 수 있다.

권장 조치:

- Supabase CLI access token을 올바른 `sbp_...` 형식으로 설정한다.
- staging Supabase project에 Alembic migration을 적용한다.
- `SUPABASE_URL=https://ycjuzwltwbeudanjykag.supabase.co`와 backend-only secret을 배포 secret manager에 등록한다.
- Supabase dashboard의 table, bucket, RLS policy, advisor 결과를 별도 체크리스트로 캡처한다.

### P0. Storage signed download 소유권 검증 결함

증거:

- `/api/storage/signed-download/{attachment_id}`는 인증 사용자를 받지만, metadata의 `employee_id`와 현재 사용자를 비교하지 않는다.
- `/api/storage/complete-upload`도 metadata 소유권을 검증하지 않는다.

영향:

- 인증된 사용자가 다른 사용자의 `attachment_id`를 알면 signed download URL을 발급받을 수 있다.
- 내부 기안서, 첨부 파일, 현장 자료 유출로 이어질 수 있다.

권장 조치:

- `attachment.employee_id == current_user.employee_id` 또는 admin 권한을 검사한다.
- complete-upload에서 object 존재 여부와 크기/content-type을 Supabase Storage metadata로 확인한다.
- pending/complete 상태 컬럼을 두고 업로드 전 metadata와 업로드 완료 metadata를 분리한다.
- 해당 권한 검증에 대한 단위 테스트와 통합 테스트를 추가한다.

### P0. access/refresh token을 localStorage에 저장

증거:

- `frontend/src/store/auth.ts`가 Zustand persist로 access token과 refresh token을 저장한다.

영향:

- XSS가 발생하면 토큰이 직접 탈취될 수 있다.
- 앱 배포 및 공개 웹 배포 기준에서는 세션 탈취 위험이 크다.

권장 조치:

- refresh token은 HttpOnly, Secure, SameSite cookie로 이전한다.
- access token은 가능한 memory 저장으로 제한하고 짧은 만료 시간을 사용한다.
- CSP, dependency audit, route-level sanitization을 함께 강화한다.

### P1. optional auth endpoint 범위가 넓음

증거:

- draft, onboarding, export, feedback 등 여러 라우터가 `get_optional_user` 패턴을 사용한다.

영향:

- 공개 배포 시 문서 생성, LLM 호출, 검색, feedback spam, 내부 template 노출 가능성이 커진다.
- 현재 rate limit 600/min per IP는 LLM/Storage/문서 생성 방어 기준으로 높다.

권장 조치:

- 기본 정책을 auth-required로 전환한다.
- 정말 공개가 필요한 endpoint만 public allowlist로 분리한다.
- LLM, export, storage, crawl 계열은 사용자/조직/역할 단위 quota를 적용한다.

### P1. RLS enable만 있고 policy/GRANT 설계가 없음

증거:

- foundation migration은 PostgreSQL에서 table별 RLS를 enable한다.
- 그러나 RLS policy와 Supabase API role grant는 확인되지 않는다.

영향:

- Supabase Data API를 쓰면 접근이 막히거나, 나중에 grant를 추가하는 과정에서 과다 노출될 수 있다.
- RLS가 켜져 있다는 사실만으로 보안이 완성되지 않는다.

권장 조치:

- backend-only direct DB 원칙인지, Supabase client 직접 접근 원칙인지 먼저 확정한다.
- direct DB만 쓸 경우 exposed schema/API 사용을 제한한다.
- client 직접 접근이 필요하면 table별 SELECT/INSERT/UPDATE/DELETE policy와 grant를 작성한다.
- Supabase advisor와 policy test를 CI에 포함한다.

### P1. 비밀번호 변경 정책이 약함

증거:

- 서버 change-password 로직은 새 비밀번호 최소 길이 6자만 검사한다.
- 프론트엔드와 문서에는 더 강한 정책이 존재하지만 서버에서 강제되지 않는다.

영향:

- 프론트엔드 우회 요청으로 약한 비밀번호가 설정될 수 있다.

권장 조치:

- 서버 endpoint에서 동일한 password policy를 강제한다.
- 기존 비밀번호 재사용 금지와 common password blocklist를 검토한다.
- 실패 사유는 과도한 사용자 존재 여부 정보를 노출하지 않도록 정리한다.

### P1. 기본 관리자 계정이 운영 위험으로 남아 있음

증거:

- 로컬 auth database seed와 배포 문서에 `admin/admin1234`가 남아 있다.

영향:

- production 환경에서 seed가 실행되거나 문서 기반으로 배포되면 즉시 계정 탈취 위험이 된다.

권장 조치:

- production에서는 기본 admin seed를 금지한다.
- 최초 admin bootstrap은 one-time secret 또는 admin invite flow로 분리한다.
- 배포 문서에서 demo credential을 production 절차와 명확히 분리한다.

### P1. frontend Dockerfile의 API URL build arg 이름이 코드와 다름

증거:

- Dockerfile은 `VITE_API_BASE_URL`을 설정한다.
- frontend code는 `VITE_API_URL`을 참조한다.

영향:

- 배포 환경에서 API URL이 의도대로 주입되지 않고 `/api` fallback에 의존할 수 있다.
- Firebase/Cloud Run/Supabase Edge 등 배포 조합에서 API 요청이 잘못 라우팅될 수 있다.

권장 조치:

- Dockerfile과 `.env`를 `VITE_API_URL`로 통일한다.
- production build 시 API URL validation을 추가한다.

### P1. production source map 노출 가능성

증거:

- Vite config에서 sourcemap이 활성화되어 있고 production build 결과 `.map` 파일이 생성된다.

영향:

- 공개 배포 시 내부 API 호출 구조, route logic, 일부 feature flag 판단이 노출될 수 있다.

권장 조치:

- production public hosting에서는 sourcemap을 비활성화한다.
- 필요 시 private error tracking service로만 업로드한다.

### P1. 앱 배포 기준으로 bundle 크기가 큼

증거:

- frontend build는 성공했지만 `plotly` chunk 약 4.6MB raw, gzip 약 1.38MB가 생성되었다.
- Vite가 500kB 초과 chunk 경고를 출력했다.

영향:

- 모바일 현장 모드의 초기 로딩, 저속 네트워크, PWA 설치 후 UX가 악화될 수 있다.

권장 조치:

- Plotly와 admin/dashboard 분석 화면을 route-level lazy loading으로 분리한다.
- 현장 모드 `/equipment/field`는 별도 lightweight entry 또는 최소 chunk로 유지한다.

### P2. 문서와 OpenAPI 수치가 불일치

증거:

- 이전 감사 당시 README에는 OpenAPI와 맞지 않는 고정 endpoint 설명이 남아 있었다.
- 현재 OpenAPI 기준은 215 path, 229 operation이며, README/API 요약은 생성 스크립트 기준으로 갱신된다.

영향:

- 팀 공유, 배포 판단, QA 범위 산정이 실제 구현과 어긋난다.

권장 조치:

- OpenAPI 생성 시점과 README/API 문서의 endpoint count 자동 갱신 gate를 유지한다.
- Supabase 전환 문서와 Firebase/SQLite 설명을 현재 단계별로 분리한다.

## 7. 앱 구현 및 배포 준비도

현재 확인된 앱 관련 구현:

- `frontend/public/manifest.webmanifest`
- PWA display mode `standalone`
- start URL `/equipment/field`
- SVG icon
- React route 기반 field mode 화면

확인되지 않은 항목:

- native Android project
- native iOS project
- Capacitor/Expo/Tauri/Electron wrapper
- service worker/offline cache
- push notification
- 모바일 권한 정책
- 앱스토어/플레이스토어 signing 설정

판단:

현재 상태는 네이티브 앱이라기보다는 PWA 지향 웹앱이다. 앱 배포를 목표로 한다면 두 가지 중 하나를 선택해야 한다.

1. PWA 배포: HTTPS, manifest, service worker, offline cache, install UX, push 전략을 완성한다.
2. Native wrapper 배포: Capacitor 또는 별도 native shell을 도입하고 Android/iOS signing, deep link, push, file/camera 권한을 설계한다.

현장 설비 모드가 핵심이라면 offline-first 설계가 필요하다. 네트워크가 끊겨도 최근 알람, 점검 기록, 임시 작업 로그를 저장하고, 재연결 시 중복 없이 sync해야 한다.

## 8. 검증 결과

실행한 검증:

```bash
supabase --version
```

결과:

```text
2.98.2
```

```bash
supabase projects list -o json
```

결과:

```text
Invalid access token format. Must be like `sbp_0102...1920`
```

```bash
APP_DB_BACKEND=sqlite DATABASE_URL=sqlite:////private/tmp/ajin_supabase_audit_test.db .venv/bin/python -m pytest tests/test_db_config.py tests/test_live_events.py tests/test_slack_signing.py -q
```

결과:

```text
11 passed in 0.11s
```

```bash
APP_DB_BACKEND=sqlite DATABASE_URL=sqlite:////private/tmp/ajin_alembic_audit.db .venv/bin/alembic upgrade head
```

결과:

```text
Running upgrade  -> 20260518_0001, Supabase/Postgres foundation tables
```

```bash
npm run build
```

결과:

```text
built successfully
Vite warning: Some chunks are larger than 500 kB after minification.
```

검증 해석:

- 로컬 SQLite 대상 DB 설정 테스트와 foundation migration은 통과했다.
- frontend production build도 성공했다.
- 그러나 Supabase 원격 project에 대한 실제 연결, RLS, bucket, Storage signed upload end-to-end는 검증되지 않았다.
- 전체 테스트 suite는 실행하지 않았으므로 전체 회귀 안정성을 보장할 수 없다.

## 9. 우선순위 실행 계획

### 1단계: Supabase 원격 연결 확정

- 올바른 Supabase CLI access token을 설정한다.
- `ycjuzwltwbeudanjykag` 프로젝트가 CLI에서 조회되는지 확인한다.
- staging DB에 Alembic migration을 적용한다.
- table, bucket, policy, advisor 결과를 캡처한다.

### 2단계: Storage 권한 결함 수정

- signed download와 complete-upload에 소유권 검증을 추가한다.
- admin 권한 예외를 명시한다.
- 실제 object 존재 여부와 size/content-type 검증을 추가한다.
- 권한 우회 테스트를 작성한다.

### 3단계: 인증/세션 보안 강화

- localStorage token 저장을 제거하거나 최소화한다.
- refresh token을 HttpOnly Secure SameSite cookie로 전환한다.
- server-side password policy를 강화한다.
- default admin seed를 production에서 금지한다.

### 4단계: Supabase 접근 모델 확정

- FastAPI direct DB only라면 Data API/Realtime 노출을 최소화한다.
- Supabase client 직접 접근이 필요하다면 RLS policy와 GRANT를 table별로 작성한다.
- Realtime이 필요한 table과 channel 정책을 별도 설계한다.

### 5단계: 앱 배포 전략 확정

- PWA로 갈지 native wrapper로 갈지 결정한다.
- `/equipment/field`를 lightweight mobile entry로 분리한다.
- service worker/offline queue/sync conflict 정책을 설계한다.
- production source map 비활성화와 bundle splitting을 적용한다.

### 6단계: 문서와 QA 기준 정리

- README endpoint 수를 OpenAPI 생성 스크립트 기준으로 유지한다.
- Firebase/SQLite/Supabase 전환 단계 문서를 분리한다.
- 배포 전 보안 checklist, Supabase checklist, app release checklist를 CI와 연결한다.

## 10. 제안 커밋 메시지

```text
docs(audit): add Supabase implementation readiness report

Document the current implementation scope, Supabase/Postgres integration status,
and deployment blockers so the team can separate completed features from
production risks before app release planning.
```
