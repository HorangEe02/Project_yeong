# 다음 세션 핸드오프 — 영양제 OCR 정상화 + Figma UI 전 화면 적용

작성일: 2026-06-16 · 브랜치 `feat/ai-agent-chat-import` · HEAD `78ea6454` · 이 문서 하나로 cold-start 가능.

---

## 0. 이 세션에서 할 일 (두 줄)

> **(작업 A)** 영양제 OCR 기능이 다시 정상 동작하지 않음(분석 결과 성분 후보가 비어 나옴 + 분석이 ~54s로 느림) — **확인·원인분석·수정**.
> **(작업 B)** Figma UI(https://www.figma.com/design/tabLE08wPC1EQ0XdfgCwII/LemonAid?node-id=0-1)가 **홈 화면에만 적용**됐고 **퀵액션 팔레트·챗봇·그 외 다방면 화면**은 미적용 — **Xcode(iPhone 17 Pro·iOS 26.5)·Android Studio(Pixel 10 Pro·Android 17)** 빌드 앱에 전 화면 적용.

---

## 1. 직전 세션 완료/미완 상태

### 1.1 커밋·푸시 완료 (양 리모트 origin+personal, HEAD `78ea6454`)
- `78ea6454` feat(mobile): 영양제 성분 함량 → Figma 회색 알약(analysis_result_screen.dart)
- `0c7d9f4e` feat(mobile): 음식 후보 → Figma 그룹 카드(food_candidate_list.dart)
- `8a9dc104` feat(mobile): 홈 히어로 → Figma 중앙 점수카드(health_hero_card.dart)
- `c162c717` feat(mobile): 카메라 앞면/성분표 2슬롯 제거(camera_screen.dart)
- `76c1f7b4` feat(mobile): 빌드 플레이버↔환경 배선 + 실 bundle id `kr.ai.lemonade.mobile`

### 1.2 ⚠️ 내 미커밋 변경 (모바일 — 다음 세션서 커밋 필요)
- `mobile/lib/widgets/dashboard/health_hero_card.dart` — **게이지 두께 수정**(stroke 18→32, radius -14→-18, h 0.52→0.56). figma 처럼 굵은 골드 아크. iPhone 17 Pro/Pixel 10 Pro 양쪽 캡처 확인됨.
- `mobile/lib/core/api/api_client.dart` — **업로드 타임아웃 60s→120s**(`uploadTimeout` 기본값). 영양제/식단 분석이 ~54s라 60s 타임아웃 초과 → "서버 응답 지연" 실패하던 것 방지. `app_providers.dart:53`이 기본값 사용(오버라이드 없음).
- 제안 커밋: `fix(mobile): thicken hero gauge to match Figma + raise analyze upload timeout to 120s`. analyze 0건·해당 위젯 테스트 통과 확인됨. **커밋 시 foreign 백엔드 WIP 격리(파일단위 `git add` 모바일 2파일만).**

### 1.3 ⚠️ 미커밋 ops 변경 (gitignore라 git status 미표시)
- 루트 `.env:271` `ENABLE_MULTIMODAL_VERIFICATION=true`→**`false`**(이번 세션 적용. multimodal Gemma 검증 단계 끔. **단 latency 거의 안 줄었음** — 아래 §2.3). 커밋 대상 아님(ops/secret).

### 1.4 🔴 foreign 백엔드 WIP (사용자 병렬 OCR 작업 — 절대 건드리지/커밋하지 말 것, 파일단위 격리)
git status에 다음이 떠 있고 **전부 사용자 소유**(OCR 재학습/Paddle 재통합/structured extraction eval):
- `backend/Nutrition-backend/src/config.py`, `backend/Nutrition-backend/src/ocr/factory.py`
- `backend/Nutrition-backend/tests/unit/ocr/{test_ocr_factory,test_paddle_provider}.py`, `tests/unit/test_config.py`
- `backend/scripts/{paddleocr_clova_eval,build_supplement_structured_extraction_eval_summary,run_paddleocr_structured_sweep,run_paddleocr_adaptive_structured_eval,extract_supplement_structured_hardcases}.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_*.py` (신규)
- `docker-compose.yml`(수정) + `docker-compose.ocr-models.yml`(신규 — PaddleOCR 모델 마운트 오버라이드)
- ⚠️ **작업 A(OCR)와 직접 연관**: 사용자가 OCR 파이프라인(config.py/factory.py/paddle provider)을 능동적으로 바꾸는 중. OCR 이슈가 이 WIP와 얽혔을 수 있음 — 조사 전 `git diff`로 foreign 변경 파악 + 충돌 주의.

### 1.5 산출물
- `outputs/generated/2026-06-16-supplement-demo/lemon-aid-supplement-demo.gif`(187KB·12s) — 홈(굵은 게이지)→영양제 다중이미지 미리보기(Nutricost 병)→3장 분석→로딩→완료 데모. **단 결과 성분이 비어 나옴**(테스트 크롭 이미지 한계, 작업 A 참조).

---

## 2. 작업 A — 영양제 OCR 정상화 (확인·원인분석·수정)

### 2.1 증상 (직전 세션 실측)
- iOS 시뮬레이터서 영양제 분석 → **"분석을 완료하지 못했어요. 서버 응답이 지연되고 있어요"**(타임아웃). → 이번 세션 **C(타임아웃 120s)로 완화**: 이제 분석이 완료까지 감.
- 그러나 분석 결과가 **"성분 후보가 비어 있어 다시 확인이 필요해요"**(빈 추출) + 제품명/성분 미확인. = **OCR/추출 품질 문제**(타임아웃과 별개).
- 분석 latency **~54초**(여전히 느림).

### 2.2 이번 세션 실측 (재현·확인 완료)
- 백엔드 `/supplements/analyze` 단일 이미지 timed curl: **HTTP 202, 54.6s, 정상 결과**(Magnesium Citrate 등 성분 추출됨) — *좋은 단일 성분표 이미지*면 추출 정상.
- 앱(에뮬레이터) 다중이미지(3장) 분석: 완료되나 **빈 결과** — 배치에 *앞면 라벨 사진 + YOLO 부분 크롭*이 섞여 성분표 패널이 없어 추출 실패로 추정.
- 즉 **추출 실패는 이미지 품질/조합 의존**일 가능성 큼. 단일 깨끗한 성분표 사진=정상, 앞면/크롭 혼합=빈 결과.

### 2.3 원인 분석 (이번 세션 확정 + 미해결)
- **타임아웃(확정·수정됨)**: 분석 ~54s > 모바일 60s 타임아웃 → C(120s)로 해결.
- **Latency 근본원인(미해결)**: B(`ENABLE_MULTIMODAL_VERIFICATION=false`)로 Gemma 검증 껐는데도 **여전히 ~54s**. 병목은 **Ollama qwen3.5:9b 파싱 모델이 외장 Corsair 드라이브(`/Volumes/Corsair EX400U Media/.ollama/models/`)에서 로드**되는 것 + CLOVA OCR 외부 API. → **근본 완화 = Ollama 모델을 내장 디스크로 이전 또는 사전 워밍업**(미수행).
- **추출 빈 결과(미해결·작업 A 핵심)**: 다중이미지 융합/이미지 품질/CLOVA 추출/foreign OCR WIP(config.py·factory.py 변경 중) 중 하나 이상. **원인 미확정 — 이번 세션서 조사.**

### 2.4 다음 세션 조사 플랜 (작업 A)
1. **foreign OCR WIP 파악 우선**: `git diff backend/Nutrition-backend/src/config.py backend/Nutrition-backend/src/ocr/factory.py docker-compose.yml docker-compose.ocr-models.yml` — 사용자가 OCR 파이프라인을 어떻게 바꿨는지(Paddle 재통합? CLOVA 변경?) 먼저 확인. **이게 빈-결과 원인일 수 있음.**
2. **클린 단일 성분표 이미지로 재현**: 깨끗한 ingredient-facts 패널 사진으로 `/supplements/analyze` → 성분 추출되는지(직전 세션 curl=Magnesium Citrate 정상). 샘플: `outputs/generated/supplement-learning/.../yolo-section/detail-yolo-*.jpg`(부분 크롭=품질 낮음 주의) 또는 깨끗한 성분표 사진 준비.
3. **다중이미지(analyze-multi) 빈-결과 재현**: 앞면+성분표 2장 vs 성분표만 1장 → 융합 결과 비교. 융합 로직이 빈 결과를 만드는지(`services/supplement_image_analysis.py` one-shot 융합).
4. **백엔드 로그 추적**: 실패 분석 중 `docker logs lemon-aid-backend-1` — CLOVA OCR 원문 텍스트가 비었는지(OCR 실패) vs 파서가 못 뽑았는지(파싱 실패) 구분. 신뢰도/금칙어/단위 정규화 단계 확인.
5. **OCR provider 상태**: 라이브 env(`docker exec lemon-aid-backend-1 env | grep -iE 'OCR|CLOVA|PADDLE|MULTIMODAL'`). 현재: `OCR_PRIMARY_PROVIDER=clova`·`ENABLE_CLOVA_OCR=true`·`ENABLE_LOCAL_OCR=false`(Paddle off)·`ENABLE_MULTIMODAL_VERIFICATION=false`·`MULTIMODAL_OCR_ASSIST_POLICY=disabled`·`OLLAMA_MODEL=qwen3.5:9b`(파싱)·`OLLAMA_VISION_MODEL=gemma4:e4b`.
6. **수정 후 재검**: 클린 이미지 분석 → 성분 추출 200 + 모바일서 결과 화면 채워짐. iPhone 17 Pro/Pixel 10 Pro 양쪽 스모크.
7. **latency 근본완화(여력 되면)**: Ollama 모델을 내장 디스크로 이전(`OLLAMA_MODELS` 환경변수 또는 ~/.ollama 심볼릭) 또는 분석 진입 시 qwen3.5:9b 사전 로드. 목표 분석 <20s.

### 2.5 백엔드 엔드포인트/경로 (작업 A)
- `POST /api/v1/supplements/analyze`(단일, 멀티파트 필드 `image`/`ocr_provider`/`barcode_text` 등) · `/analyze-multi`(다중) · `/analyses/{id}/ocr-text`(수동 OCR 텍스트) · `/analyze/comprehensive`.
- 파이프라인 코드: `backend/Nutrition-backend/src/services/supplement_image_analysis.py`, `ocr/factory.py`, `ocr/providers/`, `llm/ollama.py`, `services/supplement_parser.py`. config=`src/config.py`.
- 라이브 백엔드: 컨테이너 `lemon-aid-backend-1`(:8000, healthy), `AUTH_MODE=disabled`(토큰 불요). WORKDIR `/app/Nutrition-backend`. 모바일 iOS=`127.0.0.1:8000`, Android=`10.0.2.2:8000`.

---

## 3. 작업 B — Figma UI 전 화면 적용 (Xcode + Android Studio)

### 3.1 현재 상태 (직전 세션)
**적용 완료(커밋됨)**: 홈 히어로(중앙 점수카드·굵은 골드 게이지·매크로 미니카드)·음식 후보 그룹 카드·영양제 성분 함량 알약. 히어로는 양 디바이스 라이브 검증.
**미적용(사용자 지적 — 이번 세션 대상)**:
- **퀵액션 팔레트**(+ FAB 메뉴): `mobile/lib/widgets/common/quick_action_palette.dart` — figma 미정합.
- **챗봇(챗 탭)**: `mobile/lib/screens/chat_screen.dart` + `mobile/lib/features/chat/` — figma 미정합. figma 프레임 `773:23`(S-11 챗), 가이드 `05-chat-lemonbot.md`.
- **그 외 다방면**: 설정(`screens/settings/*`, figma `780:23`)·분석/점수(`screens/score_screen.dart`, figma `800:23`)·캘린더(`screens/calendar_screen.dart`, `763:24`)·일별기록(`daily_records_screen.dart`)·온보딩/인증·분석결과(`analysis_result_screen.dart` 영양제/식단 결과 심화). 홈 헤더 주간 스트립(figma 노란 헤더 월드롭다운+주간, 라이브는 카드내 캡슐 — 미적용)도 잔여.

### 3.2 Figma 원본 (라이브 MCP 불요)
- PNG export = `mobile/uiux/figma/03_UI_Design/*.png` (예: `03 · Main.png`·`06 · 음식 분석 플로우.png`·`07 · 영양제 분석 플로우.png`·각 화면). 프레임 인덱스 `mobile/uiux/figma/_frames_index.md`.
- 권위 스펙 = `mobile/uiux/implementation-guides/*.md` (01 auth, 02 home, 03 capture, 04 results, 05 chat, 06 today-analysis, 07 records-calendar, 08 settings, 10 parity-audit).
- 디자인 토큰 = `mobile/lib/utils/design_tokens_v2.dart`(AppColor/AppText/AppSpace/AppRadius — hex 단독 금지, 토큰 사용). 디자인시스템 = `mobile/uiux/Lemon Aid Design System/`.
- Figma Dev Mode MCP(`mcp__Figma__*`)는 데스크톱 앱서 "Enable Dev Mode MCP Server" 설정 필요라 이번엔 사용 불가 → **PNG 크롭으로 대조**. 크롭은 **PIL**(`from PIL import Image; im.crop((l,t,r,b))`); macOS `sips -c`는 중앙크롭만이라 offset 불가. 전체 Main PNG=2985×8181.
- 라이브 figma URL(node-id 0-1): https://www.figma.com/design/tabLE08wPC1EQ0XdfgCwII/LemonAid?node-id=0-1

### 3.3 작업 B 진행 방식 (직전 세션 사용자 결정 = figma 1:1, 백엔드 공백은 안전 폴백, 화면별 시각검증)
1. 화면별로: figma PNG 크롭 ↔ 라이브 스크린샷 대조 → 재설계 → **iPhone 17 Pro + Pixel 10 Pro 양쪽** 빌드·설치·캡처 검증.
2. **신뢰도 % 미노출 준수**(figma가 "92% 일치" 보여도 ConfidenceGradeChip 등급 유지 — 가드 테스트 `find.textContaining('%') findsNothing`). 연산은 백엔드(클라 계산 금지).
3. 우선순위 제안: 퀵액션 팔레트 → 챗봇 → 분석/점수 → 설정 → 캘린더/기록 → 온보딩/인증.
4. 기능 보존(특히 영양제·챗봇 기능) 하면서 디자인만 정합. figma에 없는 기능(예: 성분 선택 체크박스)은 유지=하이브리드.

### 3.4 직전 세션 미완 deferred(작업 B 세부, figma-ui-redesign-state 메모리 참조)
- 음식 1:1 심화: 예상 영양소 카드 + 섭취량 세그먼트(⚠️ `analysis_result_screen_test.dart:1040` `find.text('단백질') findsOneWidget` 충돌 → 테스트 갱신 동반).
- 영양제 1:1 심화: 성분 리스트(figma=체크박스 없음 vs 라이브=선택기능) 하이브리드·확인수정 카드 헤더·최종분석 배지(충분/부족).
- 홈 헤더 주간 스트립(`_BrandHeader` in dashboard_screen.dart + 히어로 `_DateNav` 이동).

---

## 4. 적용 중인 규칙 (필수 준수)

- **브랜치/리모트**: `feat/ai-agent-chat-import`. 커밋 후 **양 리모트**(origin=Lemon-Aid-KDT/Lemon-sin, personal=HorangEe02/Project_yeong). 트레일러 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **커밋 타이밍**: 사용자 요청 시만. 커밋 전 **항상 `git status --porcelain` + staged diff 검토**. **foreign 백엔드 WIP(§1.4) 절대 혼입 금지 — 모바일 파일만 파일단위 `git add`.** 논리단위 아토믹 커밋 선호.
- **dart format = 기본 80**(절대 `--line-length=100` 금지). 신규/수정 dart 파일은 `dart format`로 80 정합 후 커밋(이미 클린한 기존파일 reflow 금지 — 내 파일만). `flutter analyze` 0건 + `flutter test` 통과 게이트.
- **OCR 코드 기본값**(config.py paddleocr/local-first)은 의도적 — flip 금지. CLOVA-only는 배포계층(.env/compose). ⚠️ **단 OCR config.py/factory.py는 현재 사용자가 능동 수정중(foreign WIP)** — 작업 A서 충돌 주의.
- **Docker/디스크**: 소스 baked → 코드 반영 시 `docker compose build backend` 필요(빌드 전 `df -h /System/Volumes/Data`+`docker system df` 여유 확인). **모바일 작업엔 백엔드 빌드 불필요.**

---

## 5. 경로 맵

- **모바일 앱 = `mobile/`**(`lemon_aid_mobile`). 화면=`lib/screens/*`(camera/chat/dashboard/score/calendar/daily_records/analysis_result/food_search/settings/...). 공용위젯=`lib/widgets/common/*`(main_shell·quick_action_palette·food_candidate_list·diet_result_cards). 히어로=`lib/widgets/dashboard/health_hero_card.dart`. 기능=`lib/features/*`(chat·dashboard·supplements·nutrition·...). 토큰=`lib/utils/design_tokens_v2.dart`. API=`lib/core/api/api_client.dart`. 라우터=`lib/app.dart`.
- **Figma**: `mobile/uiux/figma/03_UI_Design/*.png` + `mobile/uiux/implementation-guides/*.md` + `mobile/uiux/figma/_frames_index.md`.
- **백엔드 OCR**: `backend/Nutrition-backend/src/{services/supplement_image_analysis.py,services/supplement_parser.py,ocr/factory.py,ocr/providers/,llm/ollama.py,config.py}`. 배포 env=`docker-compose.yml`(+`docker-compose.ocr-models.yml` foreign)·루트 `.env`.

---

## 6. 환경 게이트/함정 (직전 세션 실측)

- **🔴 외장 Corsair 드라이브 VirtioFS 스턱 마운트**: `docker compose up -d`(recreate) 시 `error ... mkdir /host_mnt/Volumes/Corsair EX400U Media: file exists` + 컨테이너 내 `ls /app/data/...` → "Bad file descriptor"/"Not a directory". **해결=Docker Desktop 재시작**(단 외장 드라이브라 VM 재init이 **매우 느림 — 10~15분**, 인내 필요). 이번 세션서 `/recommendations/latest` 500(KDRIs 마운트 깨짐)이 이걸로 해결됨(→200). ⚠️ Docker 재시작 폴링 시 `docker info`는 데몬 미준비면 **무한 hang**(macOS엔 `timeout` 없음) → **`curl -s -m 4 --unix-socket ~/.docker/run/docker.sock http://localhost/_ping`(=OK)** 로 non-hanging 체크. ⚠️ `pkill -f '<패턴>'`은 **자기 명령줄도 매치**해 자살(exit 144)하니 `killall <정확한프로세스명>` 사용.
- **Ollama**: 호스트 `localhost:11434` 실행중, 모델(`gemma4:e4b`·`qwen3.5:9b` 등)이 **외장 Corsair 드라이브**에 있어 로드 느림 → 분석 latency ~54s 주범. `OLLAMA_BASE_URL=http://host.docker.internal:11434`.
- **Android 에뮬레이터**: `Pixel_10_Pro` AVD = `android-37.0`(Android 17) 이미지가 **`~/Library/Android/sdk`에만** 있음 → 부팅 시 `ANDROID_SDK_ROOT=~/Library/Android/sdk ~/Library/Android/sdk/emulator/emulator -avd Pixel_10_Pro …`. flutter build apk는 homebrew sdk로 OK. adb=`~/Library/Android/sdk/platform-tools/adb`. 부팅완료=`adb shell getprop sys.boot_completed`=1.
- **iOS 시뮬레이터**: iPhone 17 Pro(iOS 26.5) **UDID `7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB`**(이름선택 금지, 항상 UDID). bundle id `kr.ai.lemonade.mobile.dev`.
- **에뮬레이터 UI 자동화**: `adb shell input tap X Y`(native px). Flutter 위젯은 `uiautomator dump`에 안 뜸 → 스크린샷 좌표 추정. 화면 녹화=`adb shell screenrecord --time-limit N /sdcard/x.mp4` → `adb pull` → ffmpeg(설치됨 v8) GIF(palettegen/paletteuse + setpts 속도조절). 영양제 분석은 동의 게이트(전체 동의→동의하고 시작하기, 1회) + Mac camera bridge 미연결 시 셔터 불가 → 갤러리(`adb push <img> /sdcard/Download/` + media scan)로 이미지 주입.

---

## 7. 빌드·검증 커맨드 (양 디바이스)

```sh
cd mobile
# 게이트
flutter analyze && flutter test
# iOS (iPhone 17 Pro · iOS 26.5)
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  flutter build ios --simulator --debug \
  --dart-define=LEMON_APP_ENV=dev --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1
xcrun simctl install 7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB build/ios/iphonesimulator/Runner.app
xcrun simctl launch 7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB kr.ai.lemonade.mobile.dev
xcrun simctl io 7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB screenshot /tmp/ios.png
# Android (Pixel 10 Pro · Android 17)
flutter build apk --debug --flavor dev \
  --dart-define=LEMON_APP_ENV=dev --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1
~/Library/Android/sdk/platform-tools/adb install -r build/app/outputs/flutter-apk/app-dev-debug.apk
# 백엔드 dev 스택(영양제/식단 분석 필요 시)
docker compose up -d db backend   # 외장 마운트 스턱이면 Docker Desktop 재시작 선행(§6)
```

---

## 8. 관련 메모리 (auto-load)
`figma-ui-redesign-state`(figma 진행·deferred·foreign WIP), `mobile-env-wiring-state`(bundle id·플레이버), `ocr-analyze-latency-and-docker-caveat`(분석 지연·Docker 외장 마운트), `ocr-pipeline-runtime-state`(파이프라인 라이브 축소부분집합), `ios-simulator-udid-fix`, `local-db-topology`, `oneshot-ocr-fusion-impl`.

---

## 9. 다음 세션 시작 프롬프트 (복사용)

```
핸드오프 outputs/todo-list/2026-06-16/2026-06-16-ocr-and-figma-crossscreen-handoff.md 참고해서 cold-start.

작업 A: 영양제 OCR이 다시 정상 동작 안 함(분석 결과 성분이 비어 나옴 + ~54s 느림). 확인·원인분석 후 수정.
  - 먼저 foreign 백엔드 OCR WIP(config.py/ocr factory.py/docker-compose.ocr-models.yml) git diff로 파악(빈-결과 원인일 수 있음).
  - 클린 단일 성분표 이미지 vs 앞면/크롭 혼합 다중이미지로 재현 + 백엔드 로그로 OCR원문 vs 파싱 실패 구분.
  - latency 근본완화(Ollama 모델 외장→내장 이전/사전워밍업)도 검토.

작업 B: Figma(https://www.figma.com/design/tabLE08wPC1EQ0XdfgCwII/LemonAid?node-id=0-1)가 홈에만 적용됨.
  퀵액션 팔레트(quick_action_palette.dart)·챗봇(chat_screen.dart+features/chat)·그 외 다방면(설정/분석/캘린더/온보딩 등)을
  figma 1:1(백엔드 공백은 안전폴백)로 적용. 화면별 iPhone 17 Pro(7B2E1A72…·iOS 26.5)+Pixel 10 Pro(Android 17) 빌드 검증.
  신뢰도 % 미노출 준수.

선반영(미커밋): 모바일 게이지 두께수정 + 업로드 타임아웃 120s(health_hero_card.dart·api_client.dart) — 커밋 여부 확인.
규칙: dart format 기본 80(--line-length=100 금지), 커밋은 요청 시 + 양 리모트 + foreign 백엔드 WIP 파일단위 격리, 트레일러 Claude Opus 4.8 (1M context).
```
