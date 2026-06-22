# 2026-05-31 검증 결과 및 Blocker

> 작성 기준: 2026-05-31
> 범위: frontend local build/smoke, Vercel preflight, Supabase/backend readiness

---

## 1. 통과한 검증

```bash
npm run typecheck
npm run build
npm run smoke:local
npm run vercel:build
npm run vercel:check-output
git diff --check -- frontend
```

확인한 내용:

- TypeScript typecheck 통과
- Next.js production build 통과
- Local smoke 통과
  - camera shell HTTP 200
  - deployment status HTTP 200
  - backend readiness proxy HTTP 200
  - Supabase runtime smoke HTTP 200
  - supplement OCR upload HTTP 202
  - meal YOLO upload HTTP 202 with fallback warning
- Vercel prebuilt output 생성 통과
- `.vercel/output`에 로컬 env 값이 들어가지 않았는지 검사 통과
- frontend diff whitespace 검사 통과

---

## 2. 실패한 검증과 원인 분류

```bash
npm run vercel:check-env
npm run vercel:readiness
npm run vercel:preflight
npm run goal:audit
```

실패 원인:

- Vercel Preview에 `LEMON_API_BASE_URL`이 아직 없다.
- Vercel Preview에 `NEXT_PUBLIC_SUPABASE_URL`이 아직 없다.
- Vercel Preview에 `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`가 아직 없다.
- Vercel 서버가 접근 가능한 public HTTPS backend `/api/v1` URL이 아직 없다.
- `LEMON_WEB_SMOKE_URL`이 없어 remote Preview smoke evidence를 만들 수 없다.

분류:

- 코드 compile/runtime 오류가 아니라 외부 배포 환경 blocker다.
- Vercel Preview env와 public backend URL이 준비되면 같은 검증 명령을 재실행해야 한다.

---

## 3. 현재 주의할 점

- 로컬 `.env.local`의 `127.0.0.1` backend URL은 Vercel Preview에 넣으면 안 된다.
- 임시 backend를 public으로 노출할 경우 token-gated gateway 없이 `AUTH_MODE=disabled` backend를 직접 열지 않는다.
- smoke 출력에 raw OCR text, provider payload, image 원문, Supabase key 값을 출력하지 않는다.
- `.vercel/output`은 생성 산출물이므로 stage 대상이 아니다.

---

## 4. 다음 검증 순서

```bash
cd frontend
npm run vercel:check-sync-source
vercel env ls preview
vercel pull --environment=preview --yes
npm run vercel:check-env
npm run vercel:preflight
vercel deploy --prebuilt --archive=tgz --yes
LEMON_WEB_SMOKE_URL=https://<preview-url> npm run smoke:remote
```

remote OCR/YOLO 업로드까지 확인하려면 아래 조건이 필요하다.

- `LEMON_API_BASE_URL`이 Vercel serverless runtime에서 접근 가능한 HTTPS URL이어야 한다.
- backend URL은 `/api/v1`로 끝나야 한다.
- backend의 OCR/YOLO endpoint가 preview smoke input을 받을 수 있어야 한다.
