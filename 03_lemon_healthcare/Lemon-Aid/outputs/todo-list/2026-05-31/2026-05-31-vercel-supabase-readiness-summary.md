# 2026-05-31 Vercel/Supabase 준비 상태 요약

> 작성 기준: 2026-05-31
> 범위: Vercel Preview readiness, Supabase runtime smoke, 배포 산출물 안전성 검사

---

## 1. 핵심 결론

Next.js 앱은 Vercel에 올릴 수 있는 구조로 준비됐다. 다만 실제 OCR/YOLO/Supabase까지 연결된 Preview 검증은 아직 완료 상태가 아니다. 이유는 코드 문제가 아니라 Vercel Preview 환경변수와 public HTTPS backend URL이 아직 준비되지 않았기 때문이다.

현재 로컬에서는 build, typecheck, local smoke가 통과했고, Vercel prebuilt output 생성과 output safety scan도 통과했다. Preview env 검증과 remote smoke는 외부 환경값이 없어서 실패하는 것이 정상 상태다.

---

## 2. 추가한 검증 장치

### 2.1 Vercel Preview env 검사

- script: `frontend/scripts/check-vercel-preview-env.mjs`
- 필수 key 존재 여부를 값 없이 검사한다.
- `127.0.0.1`, `localhost`, 사설망 IP, non-HTTPS backend URL을 Preview 후보로 거부한다.
- `NEXT_PUBLIC_SUPABASE_URL`이 `/rest/v1` REST endpoint 형태이면 project URL로 정리해야 한다고 안내한다.

### 2.2 Vercel readiness 검사

- script: `frontend/scripts/check-vercel-preview-readiness.mjs`
- Preview env, backend URL 후보, Supabase URL 후보를 보수적으로 점검한다.
- 현재 실패 원인은 다음으로 분류했다.
  - `LEMON_API_BASE_URL` Preview env 없음
  - `NEXT_PUBLIC_SUPABASE_URL` Preview env 없음
  - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` Preview env 없음
  - Vercel 서버가 접근 가능한 public HTTPS backend `/api/v1` 후보 없음

### 2.3 Vercel output safety 검사

- script: `frontend/scripts/check-vercel-output-safety.mjs`
- `.vercel/output`에 로컬 env 값, loopback backend, secret-looking value가 들어갔는지 검사한다.
- 현재 검사 결과는 통과 상태다.

### 2.4 Supabase runtime smoke

- route: `frontend/src/app/api/lemon/supabase-smoke/route.ts`
- Supabase Auth session 확인과 REST read-only smoke를 Vercel runtime에서 수행할 수 있게 했다.
- service-role key나 secret key를 클라이언트에 넣지 않는 전제를 유지한다.

---

## 3. Preview에 필요한 환경변수

```bash
LEMON_API_BASE_URL=https://<vercel-server에서-접근-가능한-backend>/api/v1
NEXT_PUBLIC_LEMON_WEB_API_BASE_URL=/api/lemon
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-or-anon-key>
```

주의사항:

- `http://127.0.0.1:8000/api/v1`은 로컬 개발 전용이다.
- Vercel Preview에서는 loopback 주소가 실제 backend가 아니라 Vercel 함수 자신을 가리킨다.
- Supabase URL은 `/rest/v1`을 붙이지 않은 project URL이어야 한다.
- service-role 또는 secret key는 `NEXT_PUBLIC_*`에 넣지 않는다.

---

## 4. 관련 파일

- `frontend/vercel.json`
- `frontend/.vercelignore`
- `frontend/.env.example`
- `frontend/scripts/check-vercel-preview-env.mjs`
- `frontend/scripts/check-vercel-preview-readiness.mjs`
- `frontend/scripts/check-vercel-sync-source.mjs`
- `frontend/scripts/check-vercel-output-safety.mjs`
- `frontend/scripts/check-goal-completion.mjs`
- `frontend/src/app/api/lemon/deployment-status/route.ts`
- `frontend/src/app/api/lemon/supabase-smoke/route.ts`
- `frontend/src/lib/supabase-url.ts`
- `frontend/src/lib/supabase.ts`

---

## 5. 공식 참고

- Vercel CLI deploy: https://vercel.com/docs/cli/deploy
- Vercel Environment Variables: https://vercel.com/docs/environment-variables
- Supabase API keys: https://supabase.com/docs/guides/getting-started/api-keys
- Supabase REST API: https://supabase.com/docs/guides/api
