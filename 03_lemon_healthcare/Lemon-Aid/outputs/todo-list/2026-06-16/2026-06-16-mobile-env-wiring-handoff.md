# 다음 세션 핸드오프 — 모바일 환경 배선 (감사 권고 item 3)

작성일: 2026-06-16 · 브랜치 `feat/ai-agent-chat-import` · 이 문서 하나로 cold-start 가능.

---

## 0. 이 세션에서 할 일 (한 줄)

> OCR 파이프라인+빌드 감사(`docs/ocr_baseline_reports/2026-06-15-pipeline-and-build-implementation-audit.md`)의 **권고 #5 "모바일 환경 배선"** 을 구현한다. **사용자 결정값 반영**: staging/prod URL은 아직 없으니 **구조+placeholder/TODO**, `mobile/flutter_app/`는 **보존(삭제 금지)**, 테스트 타깃은 **iOS iPhone 17 Pro(iOS 26.5) 시뮬레이터 + Android Pixel 10 Pro(Android 17) 에뮬레이터**.

---

## 1. 직전까지 완료 상태 (커밋·푸시, 양 리모트)

HEAD = `7fb78dcc`. 이번 작업 아크의 커밋(최신→과거):
- `7fb78dcc` feat(ocr,ci): CLOVA-only 단계 견고화 — startup OCR 가드(main.py lifespan), docker-compose 폴백 CLOVA 정렬, .env.example, CI docker-build+frontend-build 잡, §5.3 회귀(ollama prompt-bound) 수정. **2341 passed**.
- `3a1b5148` docs(ocr): 파이프라인+빌드 감사 보고서.
- `69223c3d` feat(supplement): §6.2 LLM 성분 단위 canonicalize + dedup 키 정규화.
- `410cf6e7` fix(supplement): 파서 fallback over-limit graceful (500 방지).
- `720738be` feat(supplement): §5.3 파서 융합-인식 프롬프트.
- `1e3ce0f0` feat(supplement): one-shot 융합 per-image 학습 + dark-launch flip.

감사 결론(요약): 설계(YOLO+CLOVA/Paddle+Gemma Vision)는 코드에 전부 구현됐으나 라이브는 **CLOVA OCR(전체 이미지)+Gemma 검증(~20%)** 만 활성(YOLO/Paddle/Gemma-assist OFF). **모바일 빌드(권고 #5)만 미구현 — 이번 세션 대상.** 권고 #4(코드 기본값 CLOVA flip)는 **의도적으로 안 함**(privacy-보수적 local-first 기본 + `test_supplement_analyze_paddleocr_default` 보존; CLOVA-only는 배포 계층으로 달성).

---

## 2. item 3 작업 명세 (모바일 환경 배선)

감사가 짚은 갭 + 사용자 결정값:

### 2.1 Android 플레이버 ↔ 환경 결합
- 현재(`mobile/android/app/build.gradle.kts`): `flavorDimensions += "environment"` + `productFlavors { dev(.dev suffix), staging(.staging suffix), prod }`. base `applicationId = releaseApplicationId`. **플레이버가 appId/versionName suffix만 바꾸고 백엔드 URL/보안과 분리됨** — 이게 갭.
- **할 일**: 플레이버별 환경값(API base URL, cert-pin)을 결합. dart-define은 빌드 시 주입되므로, 플레이버별 **기본 dart-define** 또는 `buildConfigField`/`resValue`로 환경을 연결. **URL은 아직 없으니 placeholder/TODO 상수**(예: `STAGING_API_BASE_URL = "TODO://staging-not-provisioned"`)로 두고, 주석에 "URL 확정 시 교체" 명시.

### 2.2 iOS 환경 스킴 + bundle id
- 현재: 단일 `Runner` 스킴 + Debug/Profile/Release 빌드타입만(환경별 스킴 없음). bundle id = **`com.example.lemonAidMobile` 플레이스홀더**(`mobile/ios/Runner.xcodeproj/project.pbxproj:491,678,705` + RunnerTests 508/526/542).
- **할 일**: (a) dev/staging/prod xcconfig/스킴 추가해 Android 플레이버 미러링, (b) **실 reverse-domain bundle id로 교체** — `com.example.*`는 릴리스 부적합. **제안: `kr.ai.lemonade.mobile`**(이메일/도메인 `lemonade.ai.kr` 기반; 사용자 최종 확인 필요). Android base applicationId와 일치시킬지 결정.
- ⚠️ bundle id 자체 값은 사용자가 디바이스 타깃(iPhone 17 Pro/Pixel 10 Pro)만 답했고 reverse-domain 문자열은 미확정 → **세션 시작 시 reverse-domain을 1회 확인**받고 진행.

### 2.3 staging/prod 빌드 문서화
- `mobile/README.md`에 dev/staging/prod 빌드 매트릭스 추가(현재 localhost 예시만). placeholder URL + `--dart-define`/`--flavor` 조합 명시. 예:
  - dev: `flutter run --flavor dev --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1`
  - staging/prod: `--flavor staging/prod --dart-define=LEMON_API_BASE_URL=<TODO>` + `LEMON_CERTIFICATE_PINS=<TODO>`.

### 2.4 flutter_app/ 레거시
- **보존(삭제 금지)** — 사용자 결정. 건드리지 말 것. (감사상 미사용 중복이나 사용자가 유지 결정.)

### 2.5 검증
- `cd mobile && flutter analyze` (클린 유지) + `flutter test`.
- 빌드/실행 타깃: **iOS = iPhone 17 Pro, iOS 26.5 시뮬레이터**(UDID는 memory `ios-simulator-udid-fix` 참조: 7B2E1A72… — 구 문서 71FB0384…는 26.3이라 틀림, **항상 UDID로 지정**), **Android = Pixel 10 Pro, Android 17 에뮬레이터**.
- ⚠️ **dart format은 기본(80) — 절대 `--line-length=100` 금지**(mobile/CLAUDE.md의 100은 틀림, 31220241서 정정). 수정 파일에 dart format 돌리지 말 것(flutter analyze 통과로 충분; 거대 reflow diff 방지).
- 관련 테스트: `mobile/test/unit/app_config_test.dart`, `mobile/test/unit/release_security_config_test.dart` (환경/릴리스 보안 단언 — 환경 배선 변경 시 갱신).

---

## 3. 현재 적용 중인 규칙 (필수 준수)

- **브랜치/리모트**: `feat/ai-agent-chat-import`. 커밋 후 **양 리모트 모두 푸시** — `origin`(Lemon-Aid-KDT/Lemon-sin) + `personal`(HorangEe02/Project_yeong).
- **커밋 트레일러**: 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **커밋 타이밍**: 사용자가 요청할 때만 커밋. 커밋 전 **항상 `git status --porcelain` + staged diff 검토** — 사용자가 병렬로 커밋/편집하므로 foreign WIP 혼입 금지. 필요 시 **헝크격리**(`git add <특정파일>` 또는 `git apply --cached`). 신규 생성 파일이 git status에 `M`이면 이미 병렬 커밋된 것.
- **black 부채 주의**: `black <file>`(mutating)은 기존 부채까지 collateral 수정 → 커밋 노이즈. `supplement_parser.py`(87-92·470-477줄 등) + 일부 테스트는 기존 black 부채 보유 → **내 라인만 black-clean하게, mutating black 전체 실행 금지**. 내 diff가 부채 라인을 포함하지 않는지 `git diff`로 확인.
- **모바일 dart format = 기본 80**(위 2.5). 백엔드 lint = `black --line-length=100` + `ruff`.
- **백엔드 테스트**: `cd backend && .venv/bin/python -m pytest Nutrition-backend/tests/unit Nutrition-backend/tests/integration/api -o addopts="" -q` (현재 2341 passed). venv = `backend/.venv`(컨테이너엔 pytest 없음).
- **OCR 코드 기본값**: config.py 기본은 `paddleocr`/local-first(의도적·privacy-보수적). **flip 금지.** CLOVA-only는 배포 계층(`docker-compose.yml` 폴백 + `.env`/`.env.example`) + lifespan startup 가드로 달성됨.
- **Docker/디스크**: 소스가 이미지에 baked(바인드마운트 X) → 코드 반영하려면 `docker compose build backend` 재빌드 필수. 빌드 전 `docker system df`+`df -h /System/Volumes/Data`로 여유 확인(디스크-풀 시 데몬 hung). recreate 시 외장 `/Volumes/Corsair EX400U Media`(공백) VirtioFS 마운트 스턱 → Docker Desktop 재시작. **모바일 작업엔 백엔드 재빌드 불필요**(라이브 백엔드는 그대로).
- **라이브 백엔드/인증**: 컨테이너 `lemon-aid-backend-1`(`:8000`), `AUTH_MODE=disabled`(토큰 불요, local-dev-user 전스코프), RLS Stage-2 lemon_app. WORKDIR `/app/Nutrition-backend`.
- 출력물 PII 주의: `outputs/oneshot-fusion-verification/`는 gitignore(파싱 라벨 내용). 이 핸드오프 `outputs/todo-list/`는 PII 없음.

---

## 4. 경로 맵 (현재 적용 중)

- **활성 모바일 앱 = `mobile/`** (패키지 `lemon_aid_mobile`). `mobile/flutter_app/` = 레거시(보존, 미사용).
  - 진입점: `mobile/lib/main.dart`. 환경: `mobile/lib/utils/device_env.dart` + app_config. env 주입 = `--dart-define`(`LEMON_API_BASE_URL`/`LEMON_API_TOKEN`/`LEMON_DEV_GATEWAY_TOKEN`/`LEMON_CERTIFICATE_PINS`).
  - Android: `mobile/android/app/build.gradle.kts`(flavors dev/staging/prod). 빌드 스크립트: `mobile/scripts/run-android-dev.sh`, `mobile/scripts/prepare-ios-flutter-uiux-xcode.sh`.
  - iOS: `mobile/ios/Runner.xcodeproj/project.pbxproj`(bundle id, 스킴).
  - 테스트: `mobile/test/unit/{app_config_test,release_security_config_test}.dart`. `mobile/README.md`(빌드 커맨드).
- **백엔드**: `backend/Nutrition-backend/src/...`. OCR 파이프라인 = `services/supplement_image_analysis.py`, `ocr/factory.py`, `ocr/providers/`, `vision/`, `llm/ollama.py`. config = `src/config.py`. 진입점/startup = `src/main.py`(lifespan에 OCR 가드 추가됨). Dockerfile = `backend/Dockerfile`. 배포 env = `docker-compose.yml`(+`.google-vision.yml`), 템플릿 = `backend/.env.example`, 실 env = repo 루트 `.env`.
- **프론트**: `frontend/`(Next.js, `next.config.ts`, `package.json` scripts: build/typecheck/vercel:*).
- **CI**: `.github/workflows/ci.yml`(lint/backend-test/mobile-build/security/dependency-audit + **신규 docker-build/frontend-build**), `agent-backend-ci.yml`.
- **문서**: 감사 보고서 `docs/ocr_baseline_reports/2026-06-15-pipeline-and-build-implementation-audit.md`. memory: `ocr-pipeline-runtime-state`, `ios-simulator-udid-fix`, `oneshot-ocr-fusion-impl`, `local-db-topology`.

---

## 5. 다음 세션 시작 프롬프트 (복사용)

```
감사 보고서(docs/ocr_baseline_reports/2026-06-15-pipeline-and-build-implementation-audit.md) 권고 #5 "모바일 환경 배선"을 구현해줘.
핸드오프: outputs/todo-list/2026-06-16/2026-06-16-mobile-env-wiring-handoff.md 참고.
결정값: staging/prod URL은 아직 없으니 구조+placeholder/TODO로만, mobile/flutter_app/는 보존(삭제 금지),
테스트는 iOS iPhone 17 Pro(iOS 26.5) 시뮬레이터 + Android Pixel 10 Pro(Android 17) 에뮬레이터로.
시작 시 iOS/Android 실 bundle id(reverse-domain, 예: kr.ai.lemonade.mobile) 1회 확인받고 진행.
규칙: dart format 기본 80(--line-length=100 금지), 커밋은 요청 시 + 양 리모트 푸시 + 헝크격리, 트레일러 Claude Opus 4.8 (1M context).
```
