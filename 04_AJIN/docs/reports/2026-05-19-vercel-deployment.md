# AJIN Vercel Deployment Report

- 작성일: 2026-05-19
- 대상 경로: `~/99_me/00_github/04_AJIN/ajin-ai-assistant-react/frontend`
- Vercel project: `ajin-ai-assistant-frontend`
- 배포 방식: Vercel CLI 수동 배포

## 1. 결과

Firebase Hosting `https://ajin-cb.web.app/`를 대체할 기본 확인 주소로 Vercel Production URL을 생성하고 smoke 검증을 완료했다.

| 구분 | URL | 상태 |
| --- | --- | --- |
| Preview deployment | `https://ajin-ai-assistant-frontend-27mptg7l6-yeong0202-s-projects.vercel.app` | Ready |
| Production deployment | `https://ajin-ai-assistant-frontend-13wvi688d-yeong0202-s-projects.vercel.app` | Ready |
| Production alias | `https://ajin-ai-assistant-frontend.vercel.app` | Ready |

## 2. 검증 결과

로컬 빌드:

```text
npm run build -> exit code 0
vite v8.0.10
2361 modules transformed
built in 1.45s
```

번들 secret scan:

```text
rg -n "SUPABASE_SECRET|service_role|sb_secret|DATABASE_URL|SUPABASE_ACCESS_TOKEN|SUPABASE_DB_PASSWORD|postgresql://|postgres://|supabase\\.co" dist
exit code 1, no output
```

Preview:

```text
vercel inspect -> status Ready, target preview
curl preview / -> 401 text/html; charset=utf-8
curl preview /api/health -> 401 text/html; charset=utf-8
curl preview /api/edge-health -> 401 text/html; charset=utf-8
vercel curl preview / -> 200 text/html; charset=utf-8
vercel curl preview /api/health -> 200 application/json
vercel curl preview /api/edge-health -> 200 application/json; charset=utf-8
```

Production:

```text
vercel promote preview --yes -> created production deployment
vercel env ls -> only public VITE_* names present in Production
vercel deploy --prod -> production deployment rebuilt after env registration
curl https://ajin-ai-assistant-frontend.vercel.app/ -> 200 text/html; charset=utf-8
curl https://ajin-ai-assistant-frontend.vercel.app/api/health -> 200 application/json
curl https://ajin-ai-assistant-frontend.vercel.app/api/edge-health -> 200 application/json; charset=utf-8
```

`/api/edge-health` 응답:

```json
{"ok":true,"service":"ajin-frontend","runtime":"vercel-function","cloud_run":false}
```

`/api/health` 응답은 Cloud Run backend rewrite를 통해 `200 application/json`을 반환했다.

Vercel env:

```text
VITE_USE_MOCK                              Production
VITE_API_BASE_URL                          Production
VITE_FIREBASE_WRITE_ENABLED                Production
VITE_FIREBASE_READ_FALLBACK_ENABLED        Production
```

Preview env 등록은 현재 Vercel project에 connected Git repository가 없어 branch-scoped preview env 추가 단계에서 거부되었다. CLI Preview deployment 자체는 로컬 workspace 업로드와 Deployment Protection 우회 smoke로 검증했다.

## 3. Cloud Run 상태

Vercel 배포 후에도 Cloud Run production traffic은 zero-min guarded revision을 유지한다.

```text
latestReadyRevisionName: ajin-backend-zero-min-20260519-1
traffic: ajin-backend-zero-min-20260519-1 100%
traffic tags: none
autoscaling.knative.dev/maxScale: '1'
run.googleapis.com/cpu-throttling: 'true'
autoscaling.knative.dev/minScale: not present
```

## 4. 다음 단계

- 사용자 확인 전까지 `https://ajin-cb.web.app/`는 rollback/비교용으로 유지한다.
- 기본 확인 URL은 `https://ajin-ai-assistant-frontend.vercel.app`로 전환한다.
- custom domain 준비 후 Vercel project에 연결한다.
- Firebase Hosting 제거는 Vercel Production URL 실사용 확인 후 별도 승인으로 진행한다.
