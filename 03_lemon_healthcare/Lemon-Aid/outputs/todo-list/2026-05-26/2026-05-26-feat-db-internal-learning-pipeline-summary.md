# 2026-05-26 feat/db-internal-learning-pipeline 작업 요약

## 기준 정보

- 작성일: 2026-05-26
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- remote: `origin` = `https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 최종 확인 head: `a03670d fix(mobile): 에뮬레이터 카메라 조건 정렬`
- 작성 목적: OCR(PaddleOCR, Google Vision, CLOVA) + YOLO + Ollama 연동 흐름을 모바일 UIUX와 Android Studio smoke 기준으로 이어서 검증할 수 있게 오늘 작업을 브랜치 단위로 정리한다.

## 브랜치/커밋 범위

오늘 현재 브랜치에서 확인한 작업 범위는 `927927b`부터 `a03670d`까지다.

| commit | 요약 |
| --- | --- |
| `927927b` | `fix(docker): 백엔드 컨테이너 OCR 경로 정렬` |
| `72298c3` | `feat(mobile): Android OCR smoke UI 정렬` |
| `264e0ba` | `feat(mobile): UIUX 공용 위젯 세트 이식` |
| `efce77b` | `feat(mobile): 17 Pro UIUX endpoint 정렬` |
| `a9d1c73` | `fix(mobile): OCR 리뷰 화면 원본 UI 정렬` |
| `2c7b659` | `fix(mobile): 17 Pro 촬영 플로우 정렬` |
| `52dd154` | `fix(mobile): 시작 화면과 촬영 진입 복구` |
| `d86638b` | `fix(mobile): OCR 입력 팔레트 안정화` |
| `a03670d` | `fix(mobile): 에뮬레이터 카메라 조건 정렬` |

## 수행한 작업

- Docker/OCR runtime 정렬
  - stale Docker 컨테이너와 구버전 백엔드 이미지로 인한 OCR/parser 판단 혼선을 정리했다.
  - 백엔드가 최신 코드로 실행되는 상태에서 OCR provider, parser, Ollama host alias 문제를 분리해 볼 수 있게 했다.
  - `lemon-aid-demo`, `lemon-aid-team-backend`처럼 혼동을 만드는 stale 컨테이너는 복구 대상이 아니라 정리 대상으로 판단했다.

- Android OCR smoke UI 정렬
  - Android emulator용 실행 경로를 `--flavor dev`와 `LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` 기준으로 정리했다.
  - Android Studio AVD에서 OCR/YOLO/Ollama smoke를 수행할 수 있도록 안내 문서와 실행 스크립트 방향을 맞췄다.
  - YOLO와 Ollama는 모바일 fake endpoint를 만들지 않고 backend runtime 설정에 따르도록 유지했다.

- 17 Pro UIUX + endpoint 정렬
  - `origin/feat/mobile-dashboard-redesign` UIUX를 참고하되 current backend-connected 구조를 보존했다.
  - 5-tab shell, dashboard, camera, chat, score, settings 흐름을 source UIUX 톤으로 맞추면서 OCR endpoint는 기존 `/api/v1/supplements/analyze` 계약을 유지했다.
  - OCR provider selector는 `Auto`, `Paddle`, `Vision`, `CLOVA` 흐름으로 테스트할 수 있게 했다.

- 설정 화면 구성
  - Android Studio emulator에서 설정 화면이 실제 렌더링되는지 확인했다.
  - 설정 화면에 계정, 동의 상태, API access, OCR 테스트, 촬영 환경, 갤러리 입력, 로컬 LLM 설명 항목을 배치했다.
  - 최신 APK 설치 후 `촬영 환경` 문구가 `Android Studio AVD와 live flag 사용`으로 표시되는 것을 확인했다.

- 갤러리 입력 오류 수정
  - 갤러리 picker 호출 시 선택 이미지를 app cache로 복사한 뒤 OCR preview로 전달하는 흐름을 사용했다.
  - Android photo picker에서 이미지를 선택한 뒤 앱의 `미리보기` 화면으로 정상 복귀하는 것을 확인했다.
  - 이미지 preview 단계에서 `Auto`, `Paddle`, `Vision`, `CLOVA` provider 선택과 `분석하기` 버튼이 함께 표시되도록 유지했다.

- 하단 버튼 겹침 수정
  - `다시 촬영`과 `분석하기` 버튼이 bottom navigation bar와 겹치지 않는 위치로 조정됐다.
  - OCR preview 결과 화면의 `다시 촬영하기` 버튼도 bottom nav 위에 충분한 간격으로 표시되는 것을 확인했다.

- Mac camera live preview 정렬
  - Codex가 직접 띄운 emulator에서는 macOS camera permission owner가 Codex가 되어 host webcam frame delivery가 실패할 수 있음을 확인했다.
  - Android Studio 또는 Android Studio 내장 Terminal에서 AVD를 실행하고 `LEMON_ENABLE_EMULATOR_LIVE_CAMERA=true`를 전달하는 방식으로 정리했다.
  - 최신 APK 설치 후 Lemon-Aid `영양제 촬영` 화면에서 Mac camera live preview가 표시되는 것을 확인했다.

## 검증 결과

- Git 상태
  - 현재 브랜치: `feat/db-internal-learning-pipeline`
  - remote tracking: `origin/feat/db-internal-learning-pipeline`
  - tracked working tree: clean
  - 남은 untracked: `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`

- Flutter/Android 검증
  - `flutter run -d emulator-5554 --flavor dev --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1 --dart-define=LEMON_ENABLE_EMULATOR_LIVE_CAMERA=true --no-resident`
  - 최신 APK fresh install 확인
  - Android emulator에서 설정 화면 렌더링 확인
  - 설정 화면의 OCR 테스트 섹션 표시 확인
  - Android photo picker 열림 확인
  - 갤러리 이미지 선택 후 `미리보기` 화면 복귀 확인
  - `다시 촬영`/`분석하기` 버튼이 하단 bar와 겹치지 않음 확인
  - Mac camera live preview 확인
  - camera provider 오류 로그 없음

- 테스트/품질 게이트
  - `flutter analyze`: No issues found
  - `flutter test`: 45 passed
  - focused widget tests: `source_camera_screen_test.dart`, `widget_test.dart` 통과
  - `git diff --check`: 통과
  - `detect-secrets scan`: 변경 파일 기준 결과 없음

- push 상태
  - `a03670d fix(mobile): 에뮬레이터 카메라 조건 정렬`까지 `origin/feat/db-internal-learning-pipeline`에 push 완료

## 남은 TODO

- 실제 보충제 라벨 이미지를 사용해 provider별 OCR 결과를 다시 비교한다.
  - `configured`
  - `paddleocr`
  - `clova`
  - `google_vision`은 credential 상태를 분리해서 판단한다.
- 최신 backend 실행 상태에서 provider가 정상 실행되는데도 성분 후보가 0이면 OCR 품질, parser/domain correction, YOLO ROI 순서로 원인을 분리한다.
- YOLO ROI는 backend `ENABLE_VISION_CLASSIFIER`가 켜진 상태에서 별도 smoke로 확인한다.
- Ollama local explanation은 `/supplements/recommendations/explain` 기존 endpoint를 통해 등록/추천 설명 흐름까지 확인한다.
- Android Studio Device Manager에서 AVD camera 설정과 실행 주체를 계속 동일하게 유지한다.

## 주의할 파일/커밋 제외 항목

- `.env`, ngrok token, ngrok public URL, provider raw payload, raw OCR text, object URI, image bytes는 문서와 커밋에 포함하지 않는다.
- `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`는 현재 untracked 상태이며 이번 요약 작업에 포함하지 않는다.
- source UIUX 브랜치의 `.env` asset loading, mock auth/backend replacement, 전체 Android/iOS tree replacement는 current branch에 그대로 가져오지 않는다.
- package/signing guardrail은 current branch 기준을 유지한다.
- Flutter release build에는 API token 또는 dev gateway token을 embed하지 않는다.
