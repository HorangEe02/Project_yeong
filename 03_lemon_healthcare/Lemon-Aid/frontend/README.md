# Lemon AID Web Frontend

Flutter로 검증한 Lemon AID 모바일 앱의 핵심 흐름을 React/Next.js 모바일 웹에서
확인하기 위한 기능 테스트 앱입니다.

## 현재 구현 범위

- React/Next.js App Router 기반 모바일 웹 화면
- Flutter 앱과 같은 홈 / 챗 / 중앙 카메라 / 점수 / 설정 5탭 모바일 셸
- Flutter 카메라 화면과 같은 전체 화면 프리뷰, 가이드 프레임, 셔터, 영양제/식단 전환 UI
- 브라우저 카메라 프리뷰(`getUserMedia`) 및 이미지 파일 업로드
- Next.js same-origin API proxy: `/api/lemon/*`
- 설정 탭에서 backend readiness, 배포 준비 상태, Vercel runtime Supabase smoke 직접 확인
- 영양제 OCR 업로드: `POST /api/v1/supplements/analyze`
- 식단 YOLO 업로드: `POST /api/v1/meals/analyze-image`
- 샘플 결과 렌더링으로 백엔드 미가동 상태에서도 UI 흐름 검증
- API `/ready` read-only smoke로 OCR/YOLO readiness 확인
- Supabase Auth session + Vercel runtime REST read-only smoke check
- Vercel 배포용 `vercel.json` 및 환경변수 예시

## 로컬 실행

```bash
npm install
npm run dev:local
```

기본 확인 URL은 `http://127.0.0.1:3000`입니다. `npm run dev`가 `localhost`
IPv6 listener로만 뜨는 환경에서는 `127.0.0.1` 접근이 실패할 수 있으므로,
Android Studio/Xcode와 나란히 확인할 때는 `dev:local`을 사용합니다.

## 환경변수

`.env.example`을 참고해 `.env.local`을 생성합니다.

```bash
LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1
LEMON_DEV_GATEWAY_TOKEN=
NEXT_PUBLIC_LEMON_WEB_API_BASE_URL=/api/lemon
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
```

Vercel Preview/Production에는 같은 값을 Project Environment Variables로 등록합니다.
브라우저는 `/api/lemon/*` same-origin proxy를 호출하고, Next.js route handler가
`LEMON_API_BASE_URL`의 FastAPI backend로 전달합니다. Supabase secret/service role key는
클라이언트에 넣지 않습니다.

`LEMON_DEV_GATEWAY_TOKEN`은 public backend가 아직 없을 때만 쓰는 개발 smoke 전용
서버 측 토큰입니다. Vercel route handler가 backend 요청에
`X-Lemon-Dev-Gateway-Token`을 붙이고, 로컬 개발 gateway가 같은 토큰을 요구합니다.
실제 운영 backend에는 이 값을 사용하지 않습니다.

## 검증 명령

```bash
npm run typecheck
npm run build
npm run smoke:local
npm run vercel:readiness
npm run vercel:check-sync-source
npm run vercel:ls-preview-env
npm run vercel:check-env
npm run vercel:check-output
npm run vercel:preflight
npm run vercel:build
npm run smoke:remote
npm run smoke:remote:uploads
npm run goal:audit
npm run audit:high
```

`smoke:local`은 이미 실행 중인 `http://127.0.0.1:3000` 서버를 대상으로 카메라 셸,
`/api/lemon/deployment-status`, `/api/lemon/ready`, `/api/lemon/supabase-smoke`,
영양제 OCR 업로드, 식단 이미지 업로드를
확인합니다. 출력은 상태 코드와 저장 여부 같은 운영 메타데이터만 표시하며 raw OCR,
이미지 원문, Supabase key 값은 출력하지 않습니다.

`goal:audit`은 React 모바일 웹 구현, OCR/YOLO proxy, Supabase smoke, Vercel project link,
Preview env, prebuilt output, 원격 smoke URL을 한 번에 점검합니다. 값은 출력하지 않고
현재 목표 완료 여부를 보수적으로 FAIL 처리합니다.

`smoke:remote`는 Preview URL을 받은 뒤 아래처럼 실행합니다. 원격 Preview에서 backend가
아직 공개 URL로 연결되지 않았거나 이미지 업로드 비용/시간을 줄여야 하는 경우를 고려해
기본적으로 이미지 업로드는 끕니다. 이 명령은 `LEMON_WEB_SMOKE_URL`이 없거나 HTTPS 원격
URL이 아니면 실패합니다.

```bash
LEMON_WEB_SMOKE_URL=https://<vercel-preview-url> npm run smoke:remote
```

원격 OCR/YOLO 업로드까지 검증하려면 Vercel 환경변수의 `LEMON_API_BASE_URL`이
Vercel 서버 함수에서 접근 가능한 backend URL이어야 하며, 아래처럼 명시적으로 켭니다.

```bash
LEMON_WEB_SMOKE_URL=https://<vercel-preview-url> npm run smoke:remote:uploads
```

## 기능 테스트 체크리스트

1. 홈 화면에서 레몬·에이드 노란 헤더, 건강 점수 카드, 4개 출력 카드, 5탭 셸이 보이는지 확인합니다.
2. 중앙 `+` 버튼 또는 홈의 `촬영` 버튼으로 전체 화면 카메라 UI에 진입합니다.
3. 촬영 화면에서 영양제/식단 모드 전환, 이미지 선택, 웹 카메라 프리뷰, 프레임 캡처를 확인합니다.
4. 영양제 모드에서 이미지 분석을 실행해 OCR API proxy 연결을 확인합니다.
5. 식단 모드에서 이미지 분석을 실행해 YOLO/수동 입력 fallback 응답을 확인합니다.
6. 설정 탭에서 API readiness와 Supabase Auth/REST smoke를 확인합니다.

## 배포 판단

현재 구조는 Vercel에 배포 가능한 Next.js 앱입니다. 단, 실제 OCR/YOLO API 테스트는
Vercel 서버 함수에서 접근 가능한 `LEMON_API_BASE_URL`이 필요합니다. Supabase는
publishable key 기반 Auth/REST smoke까지만 직접 연결하며, 사용자 데이터 저장/조회는
RLS 정책과 별도 API 계약을 확정한 뒤 추가해야 합니다. 실제 Vercel Preview 배포는
프로젝트 링크와 외부 업로드 승인이 필요합니다.

### 2026-06-01 검증 상태

- `npm run build`: 통과
- `npm run vercel:build`: 통과, `.vercel/output` 생성 확인
- `npm run smoke:local`: 통과. 로컬 테스트 backend 기준 카메라 셸, readiness proxy,
  Supabase runtime smoke, 영양제 OCR upload, 식단 YOLO fallback 흐름을 확인했습니다.
- `npm run audit:high`: 통과. `postcss` moderate advisory는 확인됐지만 자동 수정이
  Next.js major downgrade를 유도하므로 적용하지 않았습니다.
- `npm run vercel:check-env`: 실패. Vercel Preview 필수 env 3개가 아직 등록되지 않았습니다.
- `npm run vercel:ls-preview-env`: 확인 결과 Vercel Preview Environment Variables가
  아직 등록되지 않았습니다.
- `npm run vercel:check-output`: 통과. 이 검사는 env 값을 출력하지 않고, 로컬 값이
  `.vercel/output`에 들어갔는지만 확인합니다.
- `npm run vercel:check-sync-source`: 실패. 현재 `.env.local`은 로컬 loopback/non-HTTPS
  값이라 Preview 후보로 사용할 수 없습니다. Vercel에서 접근할 수 없는 사설망 backend URL도
  Preview 후보로 사용하지 않습니다.
- `npm run vercel:readiness`: 실패. 현재 파일들에는 Vercel에서 접근 가능한 HTTPS backend
  `/api/v1` 후보가 없습니다. 루트 `.env`의 Supabase URL 후보는 `/rest/v1` REST endpoint
  형태라 Preview의 `NEXT_PUBLIC_SUPABASE_URL`에는 `/rest/v1`을 제거한 project URL 형태로
  정리해 넣어야 합니다.
- `npm run goal:audit`: 실패. React 구현, Vercel project link, Vercel output은 확인되지만
  Preview env와 원격 smoke URL이 없어 전체 목표 완료 증거는 아직 부족합니다.
- Vercel route handler는 `LEMON_DEV_GATEWAY_TOKEN`이 설정된 경우 token-gated 개발
  gateway로만 전달되는 `X-Lemon-Dev-Gateway-Token` 헤더를 서버 측에서 붙일 수 있습니다.

로컬 검증에서 사용한 backend는 compose DB/Redis 네트워크에 붙인 임시 컨테이너입니다.
종료가 필요하면 아래 명령을 사용합니다.

```bash
docker stop lemon-aid-backend-webtest
docker rm lemon-aid-backend-webtest
```

### Vercel Preview 필수 환경변수

현재 Vercel 프로젝트에 아래 환경변수가 없으면 Preview 배포 후에도 샘플 UI만 검증되고,
실제 OCR/YOLO/Supabase smoke는 통과하지 않습니다.

```bash
LEMON_API_BASE_URL=https://<vercel-server에서-접근-가능한-backend>/api/v1
NEXT_PUBLIC_LEMON_WEB_API_BASE_URL=/api/lemon
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-key>
```

`LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1`은 로컬 개발에서만 유효하며,
Vercel Preview에서는 Vercel 서버 자신을 가리키므로 실제 backend 연결에 사용할 수 없습니다.
`10.x.x.x`, `172.16.x.x`-`172.31.x.x`, `192.168.x.x` 같은 사설망 주소도 Vercel 서버
함수에서 접근 가능한 public backend URL로 취급하지 않습니다.
`NEXT_PUBLIC_SUPABASE_URL`은 `/rest/v1`이 붙은 REST endpoint가 아니라
Supabase project URL이어야 합니다.
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`에는 publishable/anon key만 넣고 service-role 또는
secret key는 절대 넣지 않습니다.

#### Public backend가 아직 없을 때의 제한적 smoke 경로

운영용 backend URL이 아직 없고 Vercel Preview에서 OCR/YOLO 업로드 흐름만 검증해야 할 때는
로컬 backend를 직접 공개하지 말고 token-gated 개발 gateway를 먼저 둡니다.

```bash
export LEMON_DEV_GATEWAY_TOKEN=<random-local-smoke-token>
python backend/scripts/dev_mobile_ngrok_backend_gateway.py \
  --listen-host 127.0.0.1 \
  --listen-port 8010 \
  --backend-url http://127.0.0.1:8000 \
  --require-token
```

그 다음 승인된 터널 또는 임시 HTTPS endpoint를 gateway의 `8010` 포트로만 연결하고,
Vercel Preview env에는 아래처럼 등록합니다.

```bash
LEMON_API_BASE_URL=https://<token-gated-gateway-host>/api/v1
LEMON_DEV_GATEWAY_TOKEN=<same-random-local-smoke-token>
```

이 경로는 개발 smoke 전용입니다. `AUTH_MODE=disabled` backend를 토큰 없는 public URL로
직접 노출하지 않습니다.

### Preview 배포 순서

1. `npm run vercel:check-sync-source`로 `.env.local`의 값이 Preview 후보로 안전한지
   먼저 확인합니다. 이 명령은 dry-run 전용이며 값을 출력하거나 Vercel에 전송하지 않습니다.
2. Vercel Project Environment Variables에 위 4개 값을 등록합니다.
   공식 Vercel CLI 기준으로는 `vercel env add <KEY> preview` 형태를 사용하며,
   shell history에 값이 남지 않도록 값을 직접 명령줄에 붙이지 않습니다.
3. `npm run vercel:ls-preview-env`로 Preview 환경변수 key가 Vercel 프로젝트에 등록됐는지
   값 없이 확인합니다.
4. `vercel pull --environment=preview --yes`로 Preview 환경변수와 Project Settings를
   `.vercel/.env.preview.local`에 갱신합니다.
5. `npm run vercel:check-env`로 필수 Preview env 존재 여부와 HTTPS/loopback 금지를 확인합니다.
   이 명령은 key 이름과 pass/fail만 출력하고 env 값은 출력하지 않습니다.
6. `npm run vercel:preflight`로 타입 검사, Preview env 검증, Vercel build,
   산출물 local-env 오염 검사를 한 번에 확인합니다. Preview env 검증이 실패하면
   Vercel build를 진행하지 않습니다.
7. `vercel build --yes`로 `.vercel/output` 생성을 별도로 확인할 수 있습니다.
8. 명시 승인을 받은 뒤 `vercel deploy --prebuilt --archive=tgz --yes`를 실행합니다.
9. 출력된 Preview URL에 대해 `LEMON_WEB_SMOKE_URL=<url> npm run smoke:remote`를 실행합니다.

`vercel build`는 로컬 `.env.local`도 읽을 수 있으므로, 원격 Preview 검증용 prebuilt
산출물을 만들 때는 반드시 Preview 환경변수를 먼저 pull 합니다. 로컬 Supabase URL이나
`127.0.0.1` backend URL이 들어간 산출물은 Vercel에서 실제 OCR/YOLO/Supabase 연결
검증에 사용할 수 없습니다.

## 공식 참고

- Next.js CLI: https://nextjs.org/docs/api-reference/cli
- Vercel CLI deploy / prebuilt output: https://vercel.com/docs/cli/deploy
- Vercel CLI local build and deploy flow: https://vercel.com/docs/cli/deploying-from-cli
- Supabase REST API: https://supabase.com/docs/guides/api
- Supabase API keys: https://supabase.com/docs/guides/getting-started/api-keys
