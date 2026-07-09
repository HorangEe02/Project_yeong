# AJIN Supabase + Vercel Hosting Implementation Plan

- 작성일: 2026-05-19
- 대상 경로: `~/99_me/00_github/04_AJIN/ajin-ai-assistant-react`
- 기준 아키텍처: Vercel은 React/Vite frontend 정적 호스팅, FastAPI backend는 기존 Cloud Run/Docker 운영 경로 유지, Supabase는 Postgres/Storage로 사용
- Firebase 목표: 최종 완전 제거

## 1. 결론

현재 프로젝트는 Firebase Hosting + Cloud Run 전제를 갖고 있지만, Supabase/Postgres 전환 기반은 이미 상당 부분 구현되어 있다. 따라서 다음 단계의 가장 현실적인 웹 호스팅 구조는 frontend만 Vercel로 이전하고, backend는 기존 Cloud Run 배포 파이프라인을 유지하는 방식이다.

권장 목표 상태는 다음과 같다.

| 영역 | 목표 상태 |
| --- | --- |
| Frontend hosting | Vercel 정적 배포 |
| Backend API | Cloud Run FastAPI 유지 |
| Database | Supabase Postgres, `APP_DB_BACKEND=postgres` |
| File storage | Supabase private bucket + backend signed URL |
| Firebase | Hosting, Firestore, RTDB, Storage, Auth 의존 최종 제거 |
| API routing | Vercel `/api/:path*` external rewrite -> Cloud Run `/api/:path*` |
| Secret boundary | Supabase secret/service-role/DB URL은 backend secret에만 보관 |

Vercel-only backend 이전은 이번 기본안에서 제외한다. Vercel은 FastAPI 배포를 지원하지만, 현재 backend는 Docker, Redis, Celery, LLM/Ollama, 검색 인덱스, 크롤링/배치 작업, 파일 처리 의존성이 커서 단일 Vercel Function 구조보다 Cloud Run 컨테이너 운영이 안전하다.

## 2. 공식 문서 기준

이번 계획은 아래 공식 문서를 기준으로 한다.

| 주제 | 공식 문서 | 계획 반영 |
| --- | --- | --- |
| Supabase changelog | https://supabase.com/changelog?tags=breaking-change | Data API 자동 노출 정책 변경을 고려해 explicit grant/RLS gate를 배포 전 점검한다. |
| Supabase API keys | https://supabase.com/docs/guides/getting-started/api-keys | `sb_secret_*`, legacy `service_role`, `DATABASE_URL`은 Vercel frontend에 넣지 않는다. |
| Supabase RLS | https://supabase.com/docs/guides/database/postgres/row-level-security | 노출 schema table은 RLS와 policy를 명시해야 한다. backend-only 구조에서도 defense-in-depth로 유지한다. |
| Supabase API security | https://supabase.com/docs/guides/api/securing-your-api | Data API 접근은 GRANT와 RLS가 모두 필요하다. AJIN은 기본적으로 FastAPI direct DB 접근으로 제한한다. |
| Supabase signed upload | https://supabase.com/docs/reference/javascript/storage-from-uploadtosignedurl | frontend 직접 upload는 signed upload token만 사용하고, 권한 판단은 backend에서 끝낸다. |
| Supabase Realtime | https://supabase.com/docs/guides/realtime/postgres-changes | Realtime 도입 시 publication, RLS, frontend subscription을 별도 gate로 다룬다. |
| Vercel Vite | https://vercel.com/docs/frameworks/frontend/vite | Vite 환경변수는 `VITE_*` prefix만 frontend build에 노출된다. |
| Vercel rewrites | https://vercel.com/docs/routing/rewrites | `/api` 요청을 Cloud Run backend origin으로 proxy한다. |
| Vercel env vars | https://vercel.com/docs/environment-variables | Preview/Production별 public env만 등록하고 secret은 backend platform에 둔다. |
| Vercel FastAPI | https://vercel.com/docs/frameworks/backend/fastapi | Vercel FastAPI는 가능하지만 현재 AJIN backend의 컨테이너/작업큐 특성과 맞지 않는다. |

## 3. 현재 구현 분석

### 3.1 Frontend

현재 frontend는 `frontend/package.json` 기준 React 19 + Vite 앱이다. `frontend/src/App.tsx`는 dashboard, search, draft, chat, onboarding, compliance, management, equipment, profile, `/equipment/field` PWA field mode를 라우팅한다.

확인된 배포 관련 상태는 다음과 같다.

- `frontend/src/api/baseUrl.ts`는 기본 API base를 `/api`로 둔다.
- `frontend/public/manifest.webmanifest`는 `start_url=/equipment/field`, `display=standalone`인 PWA field mode를 정의한다.
- `firebase.json`은 현재 `frontend/dist`를 Firebase Hosting public directory로 쓰고 `/api/**`를 Cloud Run service `ajin-backend`로 rewrite한다.
- `frontend/vercel.json`은 아직 없다.
- `frontend/vite.config.ts`는 production sourcemap을 기본 비활성화하는 형태로 정리되어 있다.

해석:

- Vercel 이전 난이도는 낮다. 기존 Firebase Hosting 구조가 이미 정적 SPA + `/api` backend rewrite 패턴이기 때문이다.
- Vercel에서도 `VITE_API_BASE_URL=/api`를 유지하면 frontend 코드 변경을 최소화할 수 있다.
- Firebase Hosting 제거는 Vercel preview에서 routing, auth, upload, field mode가 검증된 뒤 진행해야 한다.

### 3.2 Backend

현재 backend는 `backend/main.py`의 FastAPI 앱이며, Docker/Cloud Run 중심 운영 경로가 이미 있다. `cloudbuild.yaml`, `Dockerfile`, `scripts/deploy-backend.sh`, `docs/BACKEND_DEPLOY.md`가 Cloud Run no-traffic deploy, smoke test, canary promote 흐름을 담당한다.

backend의 운영 특성은 다음과 같다.

- 자체 JWT/RBAC/IdP/2FA 인증 구조를 사용한다.
- 검색, 기안서, 온보딩, 컴플라이언스, 설비/현장, 관리자 기능 API가 넓게 구현되어 있다.
- Redis, Celery beat/worker, scheduled crawler, digest, FTS reindex, 권한 escalation job이 있다.
- LLM/Ollama health middleware와 Cloud Run demo/tunnel 운영 흔적이 있다.
- `requirements.txt`는 Chroma, LangChain, ML/통계, PDF/문서, Firebase Admin, Supabase, SQLAlchemy, Alembic 등 무거운 의존성을 포함한다.

해석:

- frontend만 Vercel로 옮기고 backend는 Cloud Run에 두는 것이 적합하다.
- backend를 Vercel Function으로 옮기면 Redis/Celery/장시간 작업/컨테이너 의존성/대형 bundle 문제가 생긴다.
- Cloud Run backend는 Supabase secret, DB URL, service-role 계열 값을 보관하는 유일한 runtime이어야 한다.

### 3.3 Supabase/Postgres/Data

현재 Supabase 전환 기반은 다음 형태로 구현되어 있다.

- `APP_DB_BACKEND=sqlite|postgres`와 `DATABASE_URL` 기반 DB switch가 있다.
- Alembic migration이 있고, remote head 검증 기준은 `20260518_0002`다.
- `scripts/verify_supabase_remote.py`가 remote Supabase gate의 기준이다.
- `scripts/supabase_cutover.py`가 env 검증, CLI link, Alembic, bucket private 보정, strict verifier, advisor를 순서대로 실행한다.
- `backend/routers/storage.py`와 `backend/services/supabase_storage.py`가 signed upload/download API를 제공한다.
- `backend/services/live_events.py`는 Firebase RTDB 알람 대체 표준 경로로 `live_alarms`를 사용한다.
- `backend/services/feedback_events.py`는 frontend RTDB write 대신 backend API -> `feedback_events`를 사용한다.
- Firestore/RTDB/Storage export migration script가 존재한다.

해석:

- Supabase 자체 도입은 새 설계 단계가 아니라, 배포 gate와 잔여 보안 보완 단계다.
- 이전 remote cutover 성공 기록은 참고 가능하지만, Vercel 전환 전에는 `make supabase-release-check`를 실제 secret으로 다시 통과시켜야 한다.
- Supabase Data API 직접 사용은 기본안이 아니다. AJIN은 FastAPI backend-only direct DB 접근을 기본으로 한다.

### 3.4 Firebase 잔존 지점

Firebase는 비용 차단과 대체 경로가 들어갔지만, 완전 제거 상태는 아니다.

확인된 잔존 범주는 다음과 같다.

- `firebase.json`, `firestore.rules`, `database.rules.json`, `storage.rules`
- frontend Firebase SDK dependency와 fallback hook/lib 경로
- backend `firebase-admin` dependency와 legacy fallback/read path
- Firebase Hosting rewrite를 전제로 한 기존 배포 문서
- Firestore/RTDB/Storage migration script의 source input

제거 원칙:

- write path는 계속 기본 차단한다.
- read fallback은 기능별로 Supabase/Postgres parity 확인 후 끈다.
- hosting은 Vercel preview/production smoke 통과 후 교체한다.
- source export와 migration apply는 dry-run, apply, verifier 순서로 별도 gate를 둔다.

## 4. 권장 호스팅 설계

### 4.1 Vercel project 설정

Vercel project는 repo root가 아니라 `frontend`를 root directory로 둔다.

| 설정 | 값 |
| --- | --- |
| Framework preset | Vite |
| Root directory | `frontend` |
| Install command | `npm ci` |
| Build command | `npm run build` |
| Output directory | `dist` |
| Node version | project default 또는 Node 20+ |

Vercel environment variables는 아래처럼 최소화한다.

| 변수 | Production 값 | 공개 여부 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api` | public |
| `VITE_FIREBASE_WRITE_ENABLED` | `false` | public |
| `VITE_FIREBASE_READ_FALLBACK_ENABLED` | `false` 최종 목표 | public |

금지 변수:

- `DATABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_ACCESS_TOKEN`
- `SUPABASE_DB_PASSWORD`
- `service_role`
- `sb_secret_*`
- private JWT signing secret

### 4.2 `frontend/vercel.json` 초안

아래 파일을 후속 구현 단계에서 추가한다. `<cloud-run-backend-origin>`은 실제 Cloud Run production origin으로 교체한다.

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://<cloud-run-backend-origin>/api/:path*"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ],
  "headers": [
    {
      "source": "/assets/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    },
    {
      "source": "/index.html",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "no-cache, no-store, must-revalidate"
        }
      ]
    }
  ]
}
```

주의:

- Vercel rewrite는 backend CORS를 대체하지 않는다. Cloud Run backend의 allowed origin에는 Vercel production domain과 preview domain 전략을 반영해야 한다.
- preview domain을 모두 허용할지, 고정 preview domain만 허용할지는 보안 정책으로 결정해야 한다.
- `/api` rewrite 대상은 public Cloud Run URL 또는 custom backend API domain으로 둔다.

### 4.3 Cloud Run backend 설정

Cloud Run backend에는 다음 값이 있어야 한다.

```bash
APP_DB_BACKEND=postgres
DATABASE_URL=<supabase-postgres-url>
SUPABASE_PROJECT_REF=ycjuzwltwbeudanjykag
SUPABASE_URL=https://ycjuzwltwbeudanjykag.supabase.co
SUPABASE_SECRET_KEY=<backend-only-secret>
SUPABASE_STORAGE_BUCKET_ATTACHMENTS=ajin-attachments
SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS=ajin-draft-exports
ENABLE_SUPABASE_REALTIME=false
FIREBASE_WRITE_ENABLED=false
FIREBASE_READ_FALLBACK_ENABLED=false
```

배포 전에는 다음 gate를 통과해야 한다.

```bash
make supabase-release-check
bash scripts/deploy-backend.sh --require-supabase --skip-canary
```

`--require-supabase` 경로는 관리자용 extended health와 remote verifier를 통해 실제 runtime이 Supabase DB/Storage secret을 받은 상태인지 확인하는 용도로 유지한다.

## 5. Firebase 제거 로드맵

### Phase 1. Vercel frontend preview 병렬 배포

목표:

- Firebase Hosting은 유지한 채 Vercel preview를 병렬로 띄운다.
- Vercel에서 `/`, `/login`, `/equipment/field`, `/api/health`가 정상 동작하는지 확인한다.

작업:

- `frontend/vercel.json` 추가.
- Vercel project root를 `frontend`로 연결.
- `VITE_API_BASE_URL=/api` 설정.
- Cloud Run CORS allowlist에 Vercel production/preview origin 반영.
- `npm run build`와 Vercel preview deploy 확인.

검증:

```bash
cd frontend && npm run build
curl -i https://<vercel-preview>/api/health
```

### Phase 2. Firebase read fallback 폐쇄

목표:

- Firebase write는 계속 차단한다.
- Firebase read fallback을 기능별로 제거하거나 `false`로 고정한다.

작업:

- `VITE_FIREBASE_READ_FALLBACK_ENABLED=false`.
- `FIREBASE_READ_FALLBACK_ENABLED=false`.
- Firestore chat/draft/equipment read fallback 사용 지점을 API 기반 read path로 대체한다.
- RTDB hooks는 `live_alarms` API 또는 추후 Supabase Realtime으로 대체한다.

검증:

```bash
rg -n "isFirebaseReadFallbackEnabled|FIREBASE_READ_FALLBACK_ENABLED|VITE_FIREBASE_READ_FALLBACK_ENABLED" frontend/src backend core features
make test PYTEST_ARGS="tests/test_live_events.py tests/test_plc_ingest.py tests/test_storage_permissions.py -q"
```

### Phase 3. Firebase Hosting cutover

목표:

- 사용자 진입 domain을 Vercel로 전환한다.
- Firebase Hosting rewrite는 rollback window 동안만 유지한다.

작업:

- Vercel production domain 연결.
- Firebase Hosting domain의 traffic/dns 전환 계획 수립.
- 기존 `firebase.json`은 rollback 기간 이후 archival 또는 제거 대상으로 둔다.

검증:

```bash
curl -I https://<vercel-production>/
curl -i https://<vercel-production>/api/health
```

### Phase 4. Firebase SDK/dependency 제거

목표:

- Firebase SDK, rules, legacy scripts를 제거하거나 archive로 격리한다.
- Supabase/Postgres/Cloud Run만 운영 경로로 남긴다.

작업:

- frontend `firebase` dependency 제거.
- backend `firebase-admin` dependency 제거 가능 여부 확인.
- `firestore.rules`, `database.rules.json`, `storage.rules` 제거 또는 `docs/legacy/` 이동.
- migration 완료 후 export scripts는 one-shot archival tool로 문서화한다.

검증:

```bash
rg -n "firebase|Firestore|RTDB|FIREBASE" -g '!frontend/node_modules/**' -g '!frontend/dist/**'
cd frontend && npm run build
make test-collect
```

## 6. P0/P1 선행 보완

### P0. Storage 권한 검증 보완

문제:

- signed download와 complete-upload는 attachment owner 검증이 배포 전 gate가 되어야 한다.
- complete-upload는 object 존재 여부, size, content-type 확인이 필요하다.

구현 방향:

- `attachment.employee_id == current_user.employee_id` 또는 admin 권한만 signed download 허용.
- upload request 생성 시 pending row를 만들고, complete 단계에서 Supabase object metadata와 DB row를 대조.
- 권한 우회 테스트를 `tests/test_storage_permissions.py`에 추가.

### P0. Supabase remote verifier 재실행

문제:

- 이전 remote cutover 성공 기록은 유효한 참고 자료지만, hosting 전환 시점의 현재 remote 상태를 보장하지 않는다.

구현 방향:

- 실제 secret이 있는 shell/CI에서 `make supabase-release-check`를 다시 실행한다.
- 결과 markdown을 `outputs/supabase-verification/<date>-remote-check.md`로 남긴다.
- `22 pass, 0 warn, 0 fail` 또는 동등한 strict pass를 production gate로 둔다.

### P1. Production default admin 차단

문제:

- demo/admin seed가 production에서 켜지면 즉시 계정 탈취 위험이 된다.

구현 방향:

- production에서는 `AUTH_BOOTSTRAP_ADMIN_ENABLED=false`를 강제한다.
- `scripts/bootstrap_supabase_sys_admin.py` 방식의 one-time named admin bootstrap만 허용한다.
- 배포 smoke에서 active default admin count를 확인한다.

### P1. Browser token 저장 최소화

문제:

- access/refresh token을 localStorage에 장기 저장하면 XSS 시 탈취 위험이 크다.

구현 방향:

- refresh token은 HttpOnly, Secure, SameSite cookie로 이전하는 별도 auth hardening issue로 분리한다.
- access token은 memory 저장 또는 짧은 TTL로 제한한다.
- CSP와 dependency audit를 frontend hosting gate에 포함한다.

### P1. Secret bundle 검사

문제:

- Vercel frontend bundle에 secret이 들어가면 배포 후 회수가 어렵다.

검증:

```bash
rg -n "SUPABASE_SECRET|service_role|sb_secret|DATABASE_URL|SUPABASE_ACCESS_TOKEN|SUPABASE_DB_PASSWORD" frontend/dist
```

기대:

- production bundle에서 결과가 없어야 한다.

## 7. 구현 순서

1. `frontend/vercel.json` 추가.
2. Cloud Run backend CORS allowlist에 Vercel origin 정책 추가.
3. Storage signed URL 권한 검증 보완.
4. Supabase strict verifier와 backend no-traffic deploy gate 재실행.
5. Vercel preview project 연결.
6. Preview smoke: `/`, `/equipment/field`, `/api/health`, login, file upload.
7. Vercel production domain 연결.
8. Firebase read fallback `false` 전환.
9. Firebase Hosting traffic 제거.
10. Firebase SDK/rules/dependency 제거 또는 legacy archive.

## 8. 검증 계획

문서 생성 직후 최소 검증:

```bash
git diff --check
```

구현 단계 검증:

```bash
cd frontend && npm run build
make openapi-docs-check
make supabase-release-check
rg -n "SUPABASE_SECRET|service_role|sb_secret|DATABASE_URL" frontend/dist
```

Vercel preview smoke:

```bash
curl -I https://<vercel-preview>/
curl -i https://<vercel-preview>/api/health
curl -I https://<vercel-preview>/equipment/field
```

수동 QA:

- 로그인 성공.
- dashboard 첫 로드 성공.
- `/equipment/field` PWA 화면 진입 성공.
- 기안서 route lazy chunk 로드 성공.
- 파일 업로드 signed URL flow 성공.
- Firebase write/read fallback off 상태에서 주요 화면이 깨지지 않음.

## 9. 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| Vercel preview origin CORS 미반영 | `/api` 호출 실패 | preview domain 정책을 backend CORS에 명시 |
| Supabase secret이 Vercel env에 등록됨 | DB/Storage 권한 유출 | Vercel env 등록 금지 목록과 bundle scan gate 운영 |
| Firebase read fallback 조기 폐쇄 | 일부 화면 데이터 누락 | 기능별 parity 확인 후 단계적으로 `false` |
| Storage owner 검증 누락 | 첨부 파일 유출 | P0로 먼저 수정 후 hosting cutover |
| backend를 Vercel로 무리하게 이전 | Celery/Redis/LLM/대형 의존성 문제 | backend는 Cloud Run 유지 |
| Supabase Data API grant/RLS 불일치 | 과다 노출 또는 접근 실패 | backend-only 원칙 유지, Data API는 필요한 경우만 explicit grant |

## 10. 커밋 메시지 제안

```text
docs(hosting): add Supabase Vercel hosting implementation plan

Explain the target deployment split before moving hosting traffic:
Vercel serves the Vite frontend, Cloud Run keeps the FastAPI backend,
and Supabase remains the backend-only Postgres and Storage provider.

The plan also separates completed Firebase replacement work from the
remaining cutover gates so the team can remove Firebase without exposing
Supabase secrets or weakening storage ownership checks.
```
