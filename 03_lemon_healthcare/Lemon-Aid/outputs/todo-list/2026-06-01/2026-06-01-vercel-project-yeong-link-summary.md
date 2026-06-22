# 2026-06-01 Vercel `project-yeong` 연동 요약

> 작성 기준: 2026-06-01
> 범위: Lemon AID `frontend` Next.js 앱을 Vercel `yeong0202-s-projects/project-yeong`에 연결

---

## 1. 요청과 목표

사용자가 제공한 Vercel 프로젝트:

```text
https://vercel.com/yeong0202-s-projects/project-yeong
```

목표:

- 로컬 `frontend` Next.js 앱을 기존 `frontend` Vercel 프로젝트가 아니라 `project-yeong`에 연결한다.
- GitHub 자동 배포 기준 Root Directory가 실제 앱 위치를 바라보도록 Vercel 프로젝트 설정을 맞춘다.
- 배포 전 코드 빌드와 Vercel 설정 상태를 확인한다.

---

## 2. 확인한 기존 상태

Vercel CLI 상태:

- CLI 경로: `/Users/yeong/.npm-global/bin/vercel`
- CLI 버전: `54.4.1`
- 로그인 계정: `horangee02`
- 스코프: `yeong0202-s-projects`

기존 로컬 링크:

- `frontend/.vercel/project.json`은 `projectName: frontend`를 가리키고 있었다.
- 요청 프로젝트 `project-yeong`와 달라 재링크가 필요했다.

프로젝트 목록 확인:

- `project-yeong`
- `frontend`
- `ajin-ai-assistant-frontend`
- `ajin-ai-assistant-react`

---

## 3. 적용한 변경

로컬 링크:

```bash
vercel link --yes --team yeong0202-s-projects --project project-yeong
```

결과:

```text
Linked yeong0202-s-projects/project-yeong
```

Vercel 프로젝트 설정 패치:

- Project: `project-yeong`
- Root Directory: `03_lemon_healthcare/Lemon-Aid/frontend`
- Framework Preset: `Next.js`
- Node.js Version: `24.x`
- Build Command: `npm run build`
- Install Command: Vercel 기본값
- Output Directory: Next.js default

공식 참고:

- Vercel CLI: <https://vercel.com/docs/cli>
- Vercel Update Project API: <https://vercel.com/docs/rest-api/reference/endpoints/projects/update-an-existing-project>

---

## 4. 검증 결과

통과:

```bash
npm run typecheck
npm run build
vercel pull --environment=preview --yes
vercel project inspect project-yeong
node scripts/check-vercel-output-safety.mjs
```

확인한 내용:

- TypeScript typecheck 통과
- Next.js production build 통과
- Vercel local link가 `project-yeong`로 바뀜
- Vercel dashboard project settings에 Root Directory와 Framework 설정이 반영됨
- `.vercel/output`에 로컬 env 값이 포함되지 않았는지 검사 통과

확인된 Vercel 설정:

```text
Project: project-yeong
Root Directory: 03_lemon_healthcare/Lemon-Aid/frontend
Framework Preset: Next.js
Build Command: npm run build
Output Directory: Next.js default
Install Command: Vercel default
```

---

## 5. 실패 또는 보류된 부분

Preview 환경변수:

```bash
vercel env ls preview
```

결과:

```text
No Environment Variables found for yeong0202-s-projects/project-yeong
```

`node scripts/check-vercel-preview-env.mjs` 실패 원인:

- `LEMON_API_BASE_URL` missing
- `NEXT_PUBLIC_SUPABASE_URL` missing
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` missing

로컬 `.env.local`은 필수 키를 갖고 있지만 Vercel Preview 후보로 자동 업로드하지 않았다.

이유:

- 로컬 값은 Vercel serverless runtime에서 접근 가능한 public HTTPS backend 조건을 만족하지 않는다.
- Supabase/browser key는 값 노출 위험이 있어 자동 기록 또는 자동 업로드하지 않는다.
- service-role 또는 secret key가 public env에 들어가면 안 된다.

---

## 6. 다음 작업

Vercel Preview를 실제 OCR/YOLO/Supabase 연결까지 검증하려면 아래 값이 필요하다.

```text
LEMON_API_BASE_URL=https://<vercel-server에서-접근-가능한-backend>/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-or-anon-key>
```

등록 후 재검증 순서:

```bash
cd /Volumes/Corsair\ EX400U\ Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/frontend
vercel env ls preview
vercel pull --environment=preview --yes
npm run vercel:check-env
npm run vercel:preflight
```

Preview deploy는 환경변수와 public backend 준비 후 명시 승인 하에 진행한다.

---

## 7. 보안 원칙

- `.env`, `.env.local`, `.vercel/.env.*.local`은 stage 금지다.
- Supabase service-role key, secret key, provider token, ngrok token은 문서에 쓰지 않는다.
- OCR raw text, provider payload, 업로드 이미지 원문은 smoke 출력이나 문서에 남기지 않는다.
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`에는 publishable/anon key만 사용한다.
