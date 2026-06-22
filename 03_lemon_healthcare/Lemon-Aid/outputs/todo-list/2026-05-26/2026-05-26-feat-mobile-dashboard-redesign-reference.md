# 2026-05-26 feat/mobile-dashboard-redesign 참고 브랜치 정리

## 기준 정보

- 작성일: 2026-05-26
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 참고 브랜치: `origin/feat/mobile-dashboard-redesign`
- 기준 head: `e50114c docs(team): 팀 협업 가이드 추가 (브랜치·커밋·PR·CI 규칙)`
- 현재 적용 브랜치: `feat/db-internal-learning-pipeline`
- 작성 목적: UIUX 담당 브랜치의 화면/구조를 어떤 기준으로 참고했고, current backend-connected OCR/YOLO/Ollama 흐름에는 무엇을 선별 반영했는지 기록한다.

## 브랜치/커밋 범위

참고 브랜치에서 확인한 주요 커밋은 다음과 같다.

| commit | 요약 | 현재 브랜치에서의 사용 방식 |
| --- | --- | --- |
| `7a8d47e` | `feat(mobile): 메인 대시보드 P0 + 5탭 셸 Pillyze 톤 + .env 시스템 (2026-05-19)` | 5-tab shell, 밝은 yellow-first visual tone, bottom navigation 방향 참고 |
| `7d1dfa8` | `feat(mobile): 메인 대시보드 본문 + 카메라/분석결과/챗/점수/설정 + 부가화면` | dashboard, camera, analysis result, chat, score, settings 화면 구성 참고 |
| `e170a18` | `feat(mobile): 메인 대시보드 히어로 카드 + 날짜 UX + 마스코트 15포즈` | dashboard hero/date UX와 mascot visual direction 참고 |
| `f442cc2` | `feat(mobile): 날짜 네비 히어로 카드 이동 + FAB 빠른 액션 팔레트` | 중앙 FAB quick action palette 흐름 참고 |
| `e50114c` | `docs(team): 팀 협업 가이드 추가 (브랜치·커밋·PR·CI 규칙)` | 협업 규칙 참고. current branch commit/push 규칙은 기존 팀 규칙과 함께 적용 |

## 수행한 작업

- 선별 반영한 UIUX 요소
  - 5-tab shell: 홈, 챗, 중앙 `+`, 점수, 설정 흐름을 current app에 맞게 적용했다.
  - Dashboard visual: yellow header, rounded white content surface, health score/hero/card tone을 참고했다.
  - FAB quick action palette: 중앙 `+` 클릭 시 영양제 촬영, 식단 촬영, 물 섭취, 직접 입력, 복약 기록 등 빠른 액션을 보여주는 흐름을 반영했다.
  - Camera UX: black full-screen camera, yellow guide corners, supplement/meal segmented control, gallery button, shutter button, provider selector preview 흐름을 반영했다.
  - Settings UX: source branch의 card/list 기반 설정 화면 톤을 current consent/auth/API/OCR smoke 정보에 맞춰 재구성했다.
  - Mascot/splash/dashboard assets: source UIUX visual identity를 current app 구조에 맞게 일부 사용했다.

- current backend-connected 흐름으로 바꾼 요소
  - camera mock result 대신 `POST /api/v1/supplements/analyze` 실제 endpoint를 호출한다.
  - multipart field는 `image`를 유지한다.
  - form fields는 `client_request_id`, `ocr_provider`를 유지한다.
  - provider 선택은 backend accepted selector와 맞춰 `configured`, `paddleocr`, `google_vision`, `clova`로 보낸다.
  - YOLO ROI와 Ollama는 모바일 fake endpoint가 아니라 backend runtime setting과 기존 explanation endpoint를 따른다.
  - dev/local smoke는 `LEMON_API_BASE_URL`, `LEMON_DEV_GATEWAY_TOKEN`, `LEMON_CERTIFICATE_PINS` 등 current `LEMON_*` config authority를 유지한다.

- 그대로 가져오지 않은 항목
  - source branch의 `.env` Flutter asset loading은 사용하지 않는다.
  - source branch의 mock auth/service/router 구조는 current JWT/dev bypass 구조와 충돌하므로 그대로 가져오지 않는다.
  - source branch의 전체 `mobile/` tree replacement는 사용하지 않는다.
  - Android/iOS project replacement diff는 current package/signing/security guardrail을 지우지 않도록 선별했다.
  - Kakao/Google auth, local DB, notification, health integration 등 현재 OCR smoke에 필요 없는 dependency는 추가하지 않는다.

## 검증 결과

- 참고 브랜치 head 확인
  - `origin/feat/mobile-dashboard-redesign` = `e50114c`
  - 최근 커밋 목록에서 `f442cc2`, `e170a18`, `7d1dfa8`, `7a8d47e` 확인

- current branch 적용 결과
  - `feat/db-internal-learning-pipeline` head `a03670d`에서 Android fresh install 후 source-style 화면 흐름 확인
  - 설정 화면 렌더링 확인
  - FAB quick action palette 확인
  - 영양제 촬영 화면 확인
  - 갤러리 입력 및 preview 화면 확인
  - Mac camera live preview 확인

- 테스트/품질 게이트
  - `flutter analyze`: No issues found
  - focused widget tests: settings tab, gallery preview, emulator camera fallback 통과
  - `git diff --check`: 통과
  - `detect-secrets scan`: 변경 파일 기준 결과 없음

## 남은 TODO

- UIUX 참고 브랜치와 current branch의 visual parity를 화면별로 계속 비교한다.
  - 홈
  - 중앙 팔레트
  - 영양제 촬영
  - 미리보기/분석 결과
  - 챗
  - 점수
  - 설정
- source branch의 mock data 문구가 current app에 남아 있지 않은지 추가 점검한다.
- 실제 OCR 결과 화면에서 provider별 상태, parser 상태, YOLO ROI 상태, retention 상태가 사용자가 이해할 수 있는 수준으로 표시되는지 확인한다.
- Android emulator뿐 아니라 physical Android 또는 iPhone/ngrok smoke에서 같은 endpoint 흐름을 재검증한다.
- source branch의 신규 UI assets가 추가로 필요한 경우에도 `.env`, raw provider payload, generated metadata, signing guardrail 삭제 diff는 제외한다.

## 주의할 파일/커밋 제외 항목

- `origin/feat/mobile-dashboard-redesign`는 UIUX 참고 원천이지 current branch에 통째로 merge할 대상이 아니다.
- current branch에서 반드시 보존해야 하는 구조:
  - `mobile/lib/core/api`
  - `mobile/lib/core/config`
  - `mobile/lib/features/consent`
  - `mobile/lib/features/dashboard`
  - `mobile/lib/features/supplements`
  - current mobile tests
  - Android package/signing guardrails
  - iOS project files
- source branch의 `API_BASE_URL`, `.env` asset, `flutter_dotenv` 방향은 current `LEMON_*` config authority와 충돌하므로 채택하지 않는다.
- raw OCR text, provider raw payload, public tunnel URL, gateway token, object URI는 비교 문서에 남기지 않는다.
