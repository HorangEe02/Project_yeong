# Lemon Healthcare 팀 공유 보고서 - 2026-05-18 작업 내용 정리

## 한 줄 요약

오늘 작업은 데모 인프라(Docker compose + Supabase Cloud)를 안정화하고 데모 웹의 인증·CORS·Storage 차단을 해소한 뒤, 웹과 모바일 양쪽에 디자인 시스템 기반 비전(OCR) 페이지 1차 모듈을 구축해 모두 push 한 라운드이다. 기존 PR #27(P1-5 stabilization)은 Backend CI 가 통과한 상태로 머지 대기 중이고, 본 라운드의 모든 신규 작업은 `lemon-aid/demo-web` 브랜치에 16+ 커밋으로 누적되었다. 다음 라운드에서 이 브랜치를 origin/main 대상 Pull Request 로 올리는 것이 우선 과제이다.

## 기준 정보

- 작업 대상일: 2026-05-18
- 로컬 프로젝트 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid`
- 워크트리 (이번 라운드 작업 본): `/Users/yeong/99_me/00_github/03_lemon_healthcare/.claude/worktrees/vigorous-turing-1219c5`
- 보고서 저장 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/outputs/todo-list/2026-05-18`
- 브랜치: `lemon-aid/demo-web` (origin push 완료)
- 데모 웹 경로: `03_lemon_healthcare/yeong-Lemon-Aid/demo-web` (Next.js 14, App Router)
- 모바일 경로: `03_lemon_healthcare/yeong-Lemon-Aid/mobile/flutter_app` (Flutter)
- 백엔드 경로: `03_lemon_healthcare/yeong-Lemon-Aid/backend/Nutrition-backend` (FastAPI + PaddleOCR)
- Supabase 프로젝트: `weipsloxntjzcqjvzjax` (region ap-south-1, Seoul 추후 마이그레이션 고려)

## 오픈 PR 현황

PR #27 (`lemon-backend/p1-5-stabilization-pr-q-r-lint`) 은 Backend quality 게이트가 통과한 상태이다. Documentation quality 와 Flutter quality 두 워크플로는 사전부터 인프라 결함을 가지고 있어 빨간색이나, 본 PR 의 코드 변경과는 무관하므로 admin override 로 머지가 가능하다. 본 라운드에서 새로 push 한 `lemon-aid/demo-web` 브랜치는 아직 PR 이 생성되지 않았고, 이는 의도된 분리이다. 다음 세션에서 별도 PR 로 올리고 본문·검증 체크리스트를 채울 예정이다.

## 인프라 / 백엔드 변경

Docker compose 로 backend + demo-web 두 서비스를 한 명령에 띄울 수 있게 만들었다. `make up` 한 줄, `make down`, `make logs`, `make rebuild`, `make set-db-password` 등 단축키가 Makefile 에 들어가 있다. `make set-db-password` 는 `read -s` 로 입력 받은 패스워드를 URL encode 후 `env/api.env` 의 DATABASE_URL placeholder 자리에 치환하고 chmod 600 까지 적용하는 헬퍼이다. 명령줄 노출 없이 처리한다.

CI 쪽은 pgvector extension 차단을 해소하기 위해 service image 를 `postgres:16` → `pgvector/pgvector:pg16` 로 교체했다. 또한 alembic revision ID 가 varchar(32) 한도를 초과한 3 건(`0005_create_learning_vector_tables`, `0007_health_daily_summaries_composite_pk`, `0008_health_daily_summaries_hypertable`)을 단축 명명으로 fix 해 `alembic upgrade head` 가 통과하도록 만들었다.

Supabase 쪽은 `lemon-aid-supplement-images` 버킷에 대한 storage.objects RLS 정책을 두 개(`for insert`, `for select` 둘 다 `to anon`) 추가해, path 첫 segment 가 `x-demo-session-id` 헤더와 일치할 때만 INSERT/SELECT 가 허용되도록 세션 경로 격리를 적용했다. Backend 의 CORSMiddleware `allow_headers` 에는 `X-Demo-Session-Id` 를 추가해 데모 클라이언트가 보내는 헤더가 preflight 단계에서 거부되지 않게 했다.

## 데모 웹 (Next.js)

`demo-web/` 디렉터리에 Next.js 14 App Router 프로젝트를 부트스트랩하고 `tokens.css` (Lemon Aid 디자인 시스템 원본)를 그대로 가져와 디자인 토큰 베이스로 적용했다. 1차로 만든 페이지는 `/`, `/onboarding`, `/upload`, `/analyzing/[id]`, `/result/[id]`, `/history` 였다. 본 라운드에서 그 위에 새 비전 라우트 4 개를 추가했다. `/vision` (랜딩 mascot + 카메라/갤러리 CTA), `/vision/upload` (CameraFrame overlay + fixture/직접 업로드 토글), `/vision/analyzing/[id]` (mascot loader + 5-step timeline polling), `/vision/result/[id]` (5 outputs 패널 + IngredientReviewList) 이다. 기존 `/upload` 페이지에는 DeprecationBanner 를 부착해 트래픽이 자연스럽게 새 라우트로 이동하도록 했다.

비전 컴포넌트는 다섯 개를 신규로 만들었다. `CameraFrame` 은 SVG 4-corner detection guide 와 dim mask 로 디자인 시스템의 `preview/screen-camera.html` 패턴을 재현한다. `MascotLoaderSequence` 는 mascot frame PNG 3 장을 순환하며 선택적으로 LinearProgress 를 표시한다. `StepTimeline` 은 5-step pill list 로 done/current/future 상태를 각각 leaf/lemon/ink 톤으로 시각화한다. `IngredientReviewList` 는 review-soft 배경의 "확인 필요" 배지와 lemon-400 accent checkbox 로 저신뢰 항목 확인 UX 를 제공한다. `DeprecationBanner` 는 review-tone 의 안내 줄로 구 라우트에서 신 라우트로 유도한다.

문제 해결 단위로 살펴보면, `crypto.randomUUID` 가 secure context(HTTPS / localhost / 127.0.0.1) 에서만 노출되는 표준 동작 때문에 `0.0.0.0:3000` 접속 시 에러가 발생하던 문제는 `crypto.getRandomValues` 기반 RFC 4122 §4.4 v4 polyfill 로 해결했다. `NEXT_PUBLIC_*` 변수가 빌드 시점에 클라이언트 번들에 박힌다는 Next.js 동작은 docker-compose `build.args` 와 Dockerfile 의 `ARG`/`ENV` 선언으로 해결해 supabase URL 과 anon key 가 빌드 시점에 주입되도록 했다. supabase-js 가 Storage / PostgREST 요청에 글로벌 헤더를 첨부할 수 있도록 `createSupabaseBrowserClient(sessionId?)` 시그니처를 확장해 RLS 정책에서 `x-demo-session-id` 를 읽을 수 있게 했다.

## 모바일 (Flutter)

사용자의 로컬 untracked 였던 `mobile/flutter_app/` 디렉터리를 rsync 로 워크트리에 옮겨와 git 추적 대상으로 만들었다 (104 source files, build/.dart_tool/Pods 등 빌드 산출물은 제외). 디자인 시스템 토큰을 `lib/core/theme/tokens.dart` 에 Dart 상수로 옮겼다. lemon/leaf/sky/ink 팔레트, semantic 토큰(success/warning/danger/review), radii, spacing, shadow, font family 까지 모두 컴파일타임 상수로 노출했다.

`assets/mascot/character-cutout.png`, `assets/mascot/frames/*.png`, `assets/fonts/AtoZ-*.ttf` 를 디자인 시스템 폴더에서 복사하고 `pubspec.yaml` 에 assets + fonts 섹션을 등록했다. ThemeData 의 seed 는 기존 leaf-green 0xFF4E8F73 에서 `LemonAidColors.lemon400` 으로 교체했고, fontFamily 는 AtoZ 로 지정했다. BottomNavigationBar 에는 4 번째 탭 "비전" 을 추가해 `VisionRoute(repository:)` 가 들어가게 했다.

`features/vision/vision_route.dart` 는 idle → analyzing → result → error 의 4-stage 상태 머신으로 작성했다. idle 단계는 mascot hero + 카메라/갤러리 두 가지 CTA 를 lemon 토큰으로 표시하고, analyzing 단계는 `MascotLoader` (frame 시퀀스 + LinearProgress) 와 `StepTimeline` (5-step pill) 을 같이 보여준다. result 단계는 백엔드가 돌려준 `SupplementAnalysisPreview` 의 analysisId, status, warnings 를 paper card 로 표시하고, error 단계는 danger 컬러로 메시지와 다시 시도 CTA 를 보여준다. 실제 API 호출은 기존 `LemonAidRepository.analyzeSupplementImage(imagePath)` 를 재사용해 중복 구현을 피했다.

`camera: ^0.11.0` 을 pubspec 에 등록했으나 본 라운드는 image_picker 기반으로 동작한다. 라이브 viewport 의 라벨 detection guide overlay 는 camera 패키지의 CameraController 와 CustomPaint 조합으로 다음 라운드에서 본격 구현 예정이다.

## 차단점 분석 보고

이번 라운드에서 만난 세 가지 사용자 가시 차단을 정리해둔다.

첫째, `crypto.randomUUID is not a function` 은 화면의 빨간 박스로 노출되어 OCR 호출 자체가 발사되지 않게 만들었다. 원인은 `crypto.randomUUID` 가 secure context 전용 API 라는 점이었고, `0.0.0.0:3000` 에 접속하면 Chrome 이 insecure 로 간주해 API 가 undefined 가 된다. 해결은 코드 polyfill 과 사용자에게 localhost 사용 권고 두 가지를 함께 적용했다.

둘째, backend CORS preflight 가 400 Bad Request 를 반환하는 문제는 `allow_headers` 에 `X-Demo-Session-Id` 가 없어서 "Disallowed CORS headers" 가 났다. 헤더 한 개를 allow_headers 리스트에 추가해 해결했다.

셋째, Supabase Storage 의 anon INSERT 가 RLS 위반으로 400 을 받는 문제는 `storage.objects` 에 대한 정책이 정의되지 않았기 때문이었다. 세션 경로 격리 정책(INSERT + SELECT 모두 path 첫 segment 가 x-demo-session-id 헤더와 일치하는 조건) 을 supabase migration 으로 적용했다.

세 가지 fix 모두 커밋·push 가 완료되어 다음 라운드에서는 직접 확인 가능하다.

## 검증 결과

`npm run build` 는 10 routes (기존 6 + vision 4) 를 모두 정상 컴파일했고 turbopack TypeScript 검증도 통과했다. `docker ps` 기준으로 `lemon-aid-backend` 와 `lemon-aid-web` 두 컨테이너가 모두 healthy 상태이다. `curl http://localhost:8000/health` 는 `{"status":"ok","version":"0.1.0"}` 를, `curl -sI http://localhost:3000/vision` 과 `/vision/upload` 는 HTTP/1.1 200 OK 를 반환한다. CORS 검증을 위해 `curl -X OPTIONS ... -H "Access-Control-Request-Headers: content-type,x-demo-session-id"` 를 호스트에서 직접 실행하면 200 + `access-control-allow-headers` 가 `X-Demo-Session-Id` 까지 포함하는 것을 확인했다.

## 공식 문서 / 표준 기준

본 라운드의 fix 와 구현 결정은 다음 공식 문서를 근거로 했다.

- Next.js App Router: https://nextjs.org/docs/app
- Next.js useSearchParams 와 Suspense: https://nextjs.org/docs/messages/missing-suspense-with-csr-bailout
- Supabase Storage Access Control: https://supabase.com/docs/guides/storage/security/access-control
- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
- W3C Secure Contexts (crypto.randomUUID 가용 조건): https://www.w3.org/TR/secure-contexts/
- RFC 4122 §4.4 UUID v4: https://www.rfc-editor.org/rfc/rfc4122#section-4.4
- Flutter Material 3 ThemeData: https://api.flutter.dev/flutter/material/ThemeData-class.html
- Flutter camera package: https://pub.dev/packages/camera
- Flutter image_picker package: https://pub.dev/packages/image_picker

## 다음 라운드 권장 우선순위

가장 우선은 `lemon-aid/demo-web` 브랜치를 origin/main 대상 Pull Request 로 생성하는 것이다. 본문 안에 본 라운드의 모든 변경(Docker compose 인프라, 데모 웹 vision, 모바일 vision)을 도메인별 bullet 로 정리하고 검증 체크리스트(`npm run build`, `docker compose config`, `/vision` smoke) 를 명시한다. 그 다음 PR #27 머지(Docs/Flutter override) 를 처리하고, 모바일 실측(Android emulator + iOS simulator) 으로 비전 탭이 실제 기기에서도 동작하는지 확인한다. 후속으로는 PaddleOCR 의 실 텍스트 추출 품질 검증(현재 placeholder fixture 한계 확인) 과 camera 패키지를 사용한 라이브 viewport overlay 구현이 남는다.

## 다음 세션 시작 프롬프트

다음 세션을 새 채팅으로 시작해도 컨텍스트 손실 없이 이어갈 수 있도록 자족적 프롬프트를 부록으로 남긴다. 아래 블록 그대로 다음 세션에 붙여 넣으면 된다.

```text
브랜치 `lemon-aid/demo-web` 에는 2026-05-18 라운드에서 push 한 16개 커밋이
origin 에 올라가 있다 (Next.js 14 데모 웹 + Flutter 모바일 비전 모듈 +
Docker compose + Supabase Storage RLS + CORS fix 등). 다음 작업으로
이 브랜치를 origin/main 대상 Pull Request 로 생성하고, PR 본문 / Test plan /
스크린샷 / 리뷰 포인트를 채워달라.

전제:
- 작업 경로: /Users/yeong/99_me/00_github/03_lemon_healthcare/.claude/
  worktrees/vigorous-turing-1219c5
- 브랜치: lemon-aid/demo-web (origin push 완료)
- 베이스: origin/main
- 함께 열려 있는 PR #27 (lemon-backend/p1-5-stabilization-pr-q-r-lint) 는
  본 PR 의 의존이 아니지만 Backend CI 가 이미 pass 함

해야 할 일:
1) git log origin/main..lemon-aid/demo-web --oneline 로 모든 신규 커밋 확인
2) gh pr create 로 PR 생성. 본문은 다음 구조:
   ## Summary (3-5 bullet, 도메인별)
   ## Change Type (feat / fix / chore / ci 체크박스)
   ## Validation (npm run build, docker compose config, curl /vision)
   ## Lemon Healthcare P1 Gates (Pydantic / Nutrition / OCR / Config 4종)
   ## Screenshots / Evidence (브라우저 + 모바일 비전 탭)
3) 머지는 사용자가 직접 (rebase 머지 모드, 기존 정책 유지)
4) team 저장소 미러는 이번에도 보류 (지난 라운드 결정 유지)

추가로:
- 본 PR 의 CI 가 backend / docs / flutter 워크플로 어디까지 트리거되는지
  확인 (변경 파일 영역에 따라 다를 수 있음)
- 의료 금지 표현 grep 검사 (`grep -rE "진단|처방|치료" demo-web/src/app/
  vision mobile/flutter_app/lib/features/vision`) 0건인지 PR 본문에 명시

오늘은 PR 생성과 본문 작성까지만 진행. 머지 / 추가 fix / Vercel 배포는
PR 리뷰 후 별도 라운드.

오늘(2026-05-18) 라운드의 전체 작업 보고서는
outputs/todo-list/2026-05-18/2026-05-18-vision-demo-rollout-summary.md
에 정리되어 있다.
```
