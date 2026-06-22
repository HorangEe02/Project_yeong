# 2026-05-31 다음 섹션 인계 프롬프트

> 작성 기준: 2026-05-31
> 목적: 다음 Codex 섹션에서 React/Next.js 웹 UI와 Vercel Preview 검증을 이어서 진행하기 위한 handoff

---

## 이어서 사용할 프롬프트

아래 내용을 다음 섹션의 첫 메시지로 사용한다.

```text
Lemon-Aid repo에서 이어서 작업해줘.

Repo root:
/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid

현재 작업 범위:
- frontend React/Next.js 모바일 웹 앱
- Android Studio/Flutter에서 확인한 Lemon AID UI와 맞춘 웹 UI
- 카메라 preview, 이미지 업로드, 영양제 OCR, 식단 YOLO proxy
- Supabase runtime smoke
- Vercel Preview readiness/preflight/remote smoke

현재 구현 상태:
- `frontend/src/components/lemon-web-app.tsx`에 모바일 5탭 셸과 전체 화면 카메라 UI 구현
- `/api/lemon/*` same-origin proxy 구현
- supplement OCR: `/api/lemon/supplements/analyze`
- meal YOLO: `/api/lemon/meals/analyze-image`
- readiness: `/api/lemon/ready`, `/api/lemon/deployment-status`
- Supabase smoke: `/api/lemon/supabase-smoke`
- Vercel 관련 scripts:
  - `npm run vercel:check-sync-source`
  - `npm run vercel:check-env`
  - `npm run vercel:readiness`
  - `npm run vercel:build`
  - `npm run vercel:check-output`
  - `npm run vercel:preflight`
  - `npm run goal:audit`

검증 결과:
- 통과: `npm run typecheck`, `npm run build`, `npm run smoke:local`, `npm run vercel:build`, `npm run vercel:check-output`, `git diff --check -- frontend`
- 실패: `npm run vercel:check-env`, `npm run vercel:readiness`, `npm run vercel:preflight`, `npm run goal:audit`
- 실패 원인: 코드 오류가 아니라 Vercel Preview env 3개와 public HTTPS backend `/api/v1`, remote Preview URL이 아직 없음

다음 목표:
1. Vercel Preview env를 값 노출 없이 확인한다.
2. `LEMON_API_BASE_URL`은 Vercel 서버에서 접근 가능한 public HTTPS backend `/api/v1`로 준비한다.
3. `NEXT_PUBLIC_SUPABASE_URL`은 `/rest/v1` 없는 Supabase project URL을 사용한다.
4. `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`는 publishable/anon key만 사용하고 service-role/secret key는 금지한다.
5. `vercel pull --environment=preview --yes` 후 `npm run vercel:preflight`를 재실행한다.
6. 명시 승인을 받은 뒤 Vercel Preview deploy를 진행하고 `LEMON_WEB_SMOKE_URL=<preview-url> npm run smoke:remote`를 실행한다.

규칙:
- raw OCR text, provider payload, image 원문, Supabase key, env secret, ngrok token은 출력하거나 stage하지 않는다.
- `.env`, `.env.local`, `.vercel/output`, raw screenshots, private dataset은 stage 금지다.
- 기존 mobile/iOS/backend dirty changes는 사용자 변경일 수 있으므로 임의로 되돌리지 않는다.
- 커밋 메시지는 Conventional Commits 형식으로 작성한다.
- 작업 전 `git status --short --branch`로 repo 상태를 확인한다.
```

---

## Git/GitHub 규칙

- true repo root를 항상 확인한다.
- team repo와 외부 개인 repo를 혼동하지 않는다.
- stage는 요청 범위 파일만 제한적으로 진행한다.
- commit message는 Conventional Commits를 사용한다.
- commit body에는 무엇을 했는지뿐 아니라 왜 필요한지 적는다.
- push는 사용자가 명시적으로 요청한 경우에만 진행한다.

예상 commit scope:

```text
feat(frontend): add Lemon AID mobile web camera flow

Implement the React/Next.js mobile web shell and camera analysis flow so the
team can validate OCR/YOLO/Supabase integration through Vercel Preview without
exposing backend secrets or raw provider payloads.
```
