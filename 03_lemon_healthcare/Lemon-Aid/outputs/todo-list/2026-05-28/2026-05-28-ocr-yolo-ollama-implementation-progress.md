# 2026-05-28 OCR + YOLO + Ollama 구현 진행 요약

## 기준 정보

- 작업 repo: `Lemon-Aid`
- 작업 브랜치: `feat/mobile-ios-xcode-simulator-run`
- 기준 계획: `outputs/todo-list/2026-05-28/2026-05-28-ocr-yolo-ollama-gap-plan.md`
- 팀 원격: `origin/feat/mobile-ios-xcode-simulator-run`
- 개인 기록 원격: `HorangEe02/Project_yeong/feat/mobile-ios-xcode-simulator-run`
- 보안 기준: `.env`, token, raw OCR text, provider raw payload, image bytes, object URI는 문서/커밋에 포함하지 않는다.

## 브랜치/커밋 범위

- `0647446 feat(ocr): 다중 이미지 분석 세션 정렬`
- `e39ee3a feat(mobile): 분석 결과 수동 보정 연결`
- `cdad9ce feat(supplement): 분석 preview Ollama 설명 연결`
- `b53b196 feat(ocr): provider 구조화 benchmark 보강`
- `bd382b5 fix(mobile): Xcode Flutter UIUX 경로 정렬`
- 이번 추가 구현: 음식 YOLO local `best.pt`를 식단 이미지 endpoint의 review-only 후보 생성 경로로 연결
- 이번 추가 확인 대상: Android emulator dev flavor 실행, AVD camera provider 원인 분리, iPhone 17 Pro Xcode simulator 실행

## 수행한 작업

### 다중 이미지 분석 흐름

- 백엔드에 다중 이미지 분석 session endpoint와 단기 호환 `analyze-multi` endpoint가 연결되어 있다.
- 모바일 repository/controller/camera screen은 여러 장 이미지와 role metadata를 전송한다.
- `front_label`, `supplement_facts`, `intake_method`, `precautions`, `barcode`, `unknown` 계열 role을 backend contract와 맞춰 사용한다.

### OCR/YOLO 진단 metadata

- 분석 preview에 raw OCR text 없이 pipeline metadata를 제공한다.
- 주요 metadata는 `image_count`, `image_role`, `ocr_provider`, `ocr_text_present`, `ocr_confidence_bucket`, `roi_count`, `section_count`, `parser_contract_version`, `missing_required_sections`이다.
- YOLO는 OCR 전처리 및 review metadata용 ROI로 취급하고, 제품명/성분/효능 판단에는 직접 사용하지 않는다.

### Provider layout 및 parser V3

- Google Vision, PaddleOCR, CLOVA provider는 provider-neutral `OCRResult.pages` contract로 layout을 정렬한다.
- parser/review 흐름은 성분 후보뿐 아니라 `label_sections`, `intake_method`, `precautions`, `functional_claims`, `missing_required_sections`를 다룬다.
- provider benchmark는 다음 구조화 지표를 산출한다.
  - text presence rate
  - ingredient exact match
  - amount/unit exact match
  - intake-method extraction rate
  - precaution extraction rate
  - functional-claim extraction rate
  - section type recall
  - ingredient false hallucination rate

### Ollama 설명 연결

- 등록 전 analysis preview에 대해 안전한 로컬 Ollama 설명 endpoint가 추가되어 있다.
- 설명 payload는 sanitized analysis fields만 사용하며 raw OCR text, provider payload, image bytes, object URI를 전달하지 않는다.
- LLM 결과가 실패하거나 안전 검증에 걸리면 deterministic fallback 설명을 사용한다.

### 모바일 17 Pro 스타일 flow

- 17 Pro 스타일 카메라/분석 결과 UI에서 다중 이미지 추가, provider 선택, missing section 안내, manual correction, 등록 전 Ollama 설명 호출 흐름을 연결했다.
- Android 우선 smoke 흐름에서 카메라 사용이 불안정한 emulator 환경은 gallery/picker fallback을 유지한다.
- Android `dev` flavor와 iOS simulator 모두 같은 Flutter shell을 사용한다.
- Android flavor가 `dev`, `staging`, `prod`로 나뉘어 있으므로 emulator 실행은 `--flavor dev`를 지정해야 한다.

### 음식 YOLO endpoint 연결

- 팀원이 전달한 local ignored 모델 경로는 repo 기준
  `runs/food_yolo/exp01_yolov8n_baseline_pc1_b48_w8_cache_disk_det_true/weights/best.pt`로 유지한다.
- supplement label ROI용 `ENABLE_VISION_CLASSIFIER`와 음식 탐지용
  `ENABLE_FOOD_YOLO_DETECTOR`를 분리했다.
- `backend/Nutrition-backend/src/vision/food_yolo.py`를 추가해 Ultralytics
  결과를 음식 후보명, confidence, bbox, sanitized model label만 포함하는
  review-only metadata로 정규화한다.
- `/api/v1/meals/analyze-image`는 `ENABLE_FOOD_YOLO_DETECTOR=true`와
  `MEAL_YOLO_MODEL_PATH`가 있을 때만 local food YOLO를 실행한다.
- detector 실패, 빈 후보, 미설정 상태는 stable warning code와 manual-entry
  상태로 degrade하며 raw image bytes나 provider payload는 DB/API 응답에
  저장하지 않는다.
- Docker backend에는 `./runs/food_yolo:/app/runs/food_yolo:ro` read-only
  bind mount와 `MEAL_YOLO_*` 환경변수 placeholder를 추가했다.
- Flutter 17 Pro 카메라의 식단 모드 `분석하기` 버튼은 더 이상 mock/snackbar로
  막히지 않고 `BackendLemonAidRepository.analyzeMealImage()`를 통해
  `POST /api/v1/meals/analyze-image`를 호출한다.
- 식단 분석 결과 화면은 source UIUX 카드 구조를 유지하면서 음식 후보,
  Food YOLO 사용 여부, warning code, manual-entry 필요 여부를 backend
  응답으로 표시한다.
- `/api/v1/meals/{meal_id}/confirm`을 추가해 식단 이미지 preview를
  사용자 확인 식단 기록으로 확정할 수 있게 했다.
  - request: `analysis_id`, `food_items`, optional `meal_type`, optional
    `eaten_at`, `user_confirmed=true`
  - response: confirmed meal record, confirmed food item rows, bounded
    nutrition summary
  - raw image bytes, provider payload, object URI는 저장하거나 응답하지 않는다.
- Flutter 결과 화면의 식단 모드는 더 이상 preview 후 home 이동으로 끝나지
  않고, Food YOLO 후보 또는 직접 입력값을 `confirm` endpoint로 저장한다.
  저장 후 dashboard summary를 refresh한다.

## 검증 결과

- `PYTHONPATH=backend:backend/Nutrition-backend python -m pytest backend/Nutrition-backend/tests/unit/scripts/test_evaluate_ocr_three_tier.py -q --no-cov`
  - 17 passed
- `PYTHONPATH=backend:backend/Nutrition-backend python -m pytest backend/Nutrition-backend/tests/unit/ocr backend/Nutrition-backend/tests/unit/vision backend/Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py backend/Nutrition-backend/tests/unit/services/test_supplement_parser.py -q --no-cov`
  - 165 passed
- `flutter test test/unit/supplement_repository_test.dart test/unit/supplement_models_test.dart test/unit/app_controller_test.dart test/widget/source_camera_screen_test.dart test/widget/analysis_result_screen_test.dart`
  - 24 passed
- `black --check backend/scripts/evaluate_ocr_three_tier.py backend/Nutrition-backend/tests/unit/scripts/test_evaluate_ocr_three_tier.py`
  - passed
- `/private/tmp/lemon-p1-quality-venv/bin/ruff check backend/scripts/evaluate_ocr_three_tier.py backend/Nutrition-backend/tests/unit/scripts/test_evaluate_ocr_three_tier.py`
  - passed
- `git diff --check`
  - passed
- `detect-secrets scan backend/scripts/evaluate_ocr_three_tier.py backend/Nutrition-backend/tests/unit/scripts/test_evaluate_ocr_three_tier.py`
  - no findings
- Android emulator run
  - `flutter run -d emulator-5554 --flavor dev --no-resident --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1`
  - dev debug APK build/install/run passed
- iOS simulator run
  - `flutter run -d 71FB0384-0C75-4CC4-925A-2A6598CAE89A --no-resident --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1`
  - Xcode build/install/run passed
- iOS simulator screenshot
  - `simctl io ... screenshot /private/tmp/lemon-ios-xcode-home.png`
  - 17 Pro 스타일 home shell 확인

## Runtime smoke 결과

- Docker backend는 source bind mount가 아니라 image-only 구조라서 최신 checkout 기준으로 `docker compose up -d --build backend`를 실행했다.
  - `lemon-aid-backend-1`: healthy
  - `lemon-aid-db-1`: healthy
  - `lemon-aid-redis-1`: healthy
- `/health`
  - HTTP 200
- `/ready`
  - OCR providers: `configured`, `paddleocr`, `google_vision`, `clova` configured
  - `ENABLE_VISION_CLASSIFIER=false` 상태라 `YOLO ROI: off`는 정상
  - `ENABLE_MULTIMODAL_LLM=false` 상태라 vision assist는 off
- `/openapi.json`
  - `/api/v1/supplements/analyze-multi`: present
  - `/api/v1/supplements/analysis-sessions`: present
  - `/api/v1/supplements/analysis-sessions/{analysis_group_id}/images`: present
  - `/api/v1/supplements/analysis-sessions/{analysis_group_id}/finalize`: present
  - `/api/v1/supplements/analyses/{analysis_id}/explain`: present
- 단일 이미지 OCR smoke
  - 첫 fixture는 upload limit 초과로 HTTP 413이어서 더 작은 fixture로 재시도했다.
  - `ocr_provider=paddleocr`: HTTP 202, provider `paddleocr_local`, OCR text present, confidence bucket `medium`, ingredient 후보 0개
  - `ocr_provider=clova`: HTTP 202, provider `clova_ocr`, OCR text present, confidence bucket `high`, ingredient 후보 1개
  - `ocr_provider=configured`: HTTP 202, provider `clova_ocr`, OCR text present, confidence bucket `high`, ingredient 후보 1개
  - `ocr_provider=google_vision`: HTTP 202, recoverable `intake-only`, OCR text not present, automatic text extraction unavailable warning
- Google Vision direct adapter check
  - backend container 내부에서 같은 fixture로 adapter를 직접 호출했다.
  - 결과: `OCRError`, Google Vision HTTP 401
  - 판정: route/selector 문제가 아니라 현재 runtime credential/API key 권한 문제로 분리한다.
- 다중 이미지 OCR smoke
  - `/api/v1/supplements/analyze-multi`: HTTP 202
  - `image_count=2`, `preview_count=2`, merged provider `clova_ocr`, merged OCR text present, merged ingredient 후보 1개
  - merged missing section: `intake_method`
- 등록 전 analysis explain smoke
  - `/api/v1/supplements/analyses/{analysis_id}/explain`: HTTP 200
  - `use_local_llm=true`, `llm_used=true`, explanation bullet 6개, blocked terms 0개

### Runtime smoke 판정

- endpoint 연결 문제는 아니다. backend 최신 이미지 기준으로 단일/다중 이미지 endpoint와 등록 전 설명 endpoint가 모두 응답한다.
- PaddleOCR은 OCR text는 있으나 ingredient 후보가 0개라 parser/section 품질 개선 대상이다.
- CLOVA/configured는 같은 fixture에서 ingredient 후보 1개를 만들었다.
- Google Vision은 현재 HTTP 401 credential/API key 권한 문제로 분리됐다. route는 실패를 intake-only로 안전하게 degrade한다.
- YOLO ROI와 multimodal vision assist는 runtime flag가 꺼져 있어 이번 smoke에서는 off가 정상이다.

## Android/iOS 앱 실행 판정

- Android 첫 실행에서 flavor 미지정 `flutter run`은 launch activity 확인 단계에서 실패했다.
  - 원인: Android Gradle 설정이 `dev`, `staging`, `prod` product flavor를 사용한다.
  - 조치: Android Studio/Flutter run config에는 `--flavor dev`를 지정한다.
- Android `dev` flavor 실행은 성공했다.
  - API base는 emulator host loopback인 `http://10.0.2.2:8000/api/v1`를 사용했다.
  - 17 Pro 스타일 home shell, 하단 `+` action palette, `영양제 촬영` 진입을 확인했다.
- Android camera fallback 모드는 정상이다.
  - live preview 플래그가 꺼진 기본 실행에서는 앱이 emulator 안내 문구를 보여주고, 셔터는 Android 카메라 앱 촬영 fallback으로 동작한다.
- Android live preview 검정 화면의 1차 원인은 앱 코드가 아니라 AVD camera provider 설정이다.
  - `webcam1` back camera 상태에서는 emulator provider가 프레임을 얻지 못했다.
  - `-camera-back virtualscene`으로 재기동하면 virtual scene camera가 활성화된다.
- Android virtual scene camera 재실행 후 실제 분석 review 화면까지 도달했다.
  - snackbar는 preview ready 상태를 표시했다.
  - 이 결과는 카메라 선택 이후 mobile -> backend analyze endpoint 연결이 살아 있음을 의미한다.
- iOS는 현재 Mac의 Xcode/iPhone 17 Pro simulator에서 Flutter app build/install/run이 통과했다.
  - 17 Pro 스타일 home shell과 하단 `+` UI가 iOS simulator에서도 확인됐다.
  - iOS simulator는 물리 카메라가 없으므로 실제 촬영 smoke는 gallery 또는 실제 iPhone/ngrok flow로 분리한다.

## Xcode native iOS 작업 공간 편입

- `mobile/ios-native`에 있던 SwiftUI OCR smoke 기능 소스를
  `mobile/Lemon-Aid-ios/Lemon-Aid` 앱 target으로 선별 이식했다.
- `mobile/Lemon-Aid-ios/.git`은 팀 repo 일반 폴더 편입을 위해
  `/private/tmp/lemon-aid-ios-nested-git-backup-20260528`로 백업 이동했다.
- 기존 Xcode SwiftData 기본 템플릿은 제거하고 `RootView` + `AppState` +
  `LemonAidAPI` 흐름으로 앱 entry를 교체했다.
- `Info.plist`에는 카메라/사진 선택 권한과 local backend 연결용 ATS 설정을
  병합했다.
- `mobile/Lemon-Aid-ios/README.md`에 Xcode project, scheme, endpoint 계약,
  local environment variable 주입 방식을 정리했다.
- 임시 원본 `mobile/ios-native` 폴더는 중복 혼동을 줄이기 위해
  `/private/tmp/lemon-ios-native-source-backup-20260528`로 백업 이동했다.

### Xcode native iOS 검증 결과

- `plutil -lint mobile/Lemon-Aid-ios/Lemon-Aid/Info.plist mobile/Lemon-Aid-ios/Lemon-Aid/Lemon_Aid.entitlements`
  - passed
- `xcodebuild -project mobile/Lemon-Aid-ios/Lemon-Aid.xcodeproj -scheme Lemon-Aid -configuration Debug -sdk iphonesimulator -destination 'platform=iOS Simulator,id=7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB' -derivedDataPath /private/tmp/lemon-aid-ios-xcode-derived CODE_SIGNING_ALLOWED=NO build`
  - build succeeded
- `simctl install 7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB /private/tmp/lemon-aid-ios-xcode-derived/Build/Products/Debug-iphonesimulator/Lemon-Aid.app`
  - install succeeded
- `SIMCTL_CHILD_LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1 simctl launch 7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB yeongs.Lemon-Aid`
  - launch succeeded
- screenshot:
  - `/private/tmp/lemon-aid-ios-native-shell.png`
  - 17 Pro 스타일 native home shell 확인

## Xcode Flutter UIUX parity 정렬

- Xcode에서 Android Studio 앱과 같은 UIUX를 확인하려면 native SwiftUI smoke
  shell이 아니라 Flutter iOS Runner workspace를 사용해야 한다.
  - UIUX 원본: `mobile/lib`
  - Xcode workspace: `mobile/ios/Runner.xcworkspace`
  - scheme: `Runner`
- `mobile/Lemon-Aid-ios/Lemon-Aid.xcodeproj`는 OCR/YOLO/Ollama endpoint
  진단용 native smoke shell로 유지한다. Flutter dashboard, 하단 `+` action
  palette, camera/review flow를 이 프로젝트에 손으로 재구현하지 않는다.
- `mobile/scripts/prepare-ios-flutter-uiux-xcode.sh`를 추가해 Xcode 실행 전
  Flutter iOS build 설정과 `--dart-define` 값을 준비할 수 있게 했다.
  - 기본 local simulator API base: `http://127.0.0.1:8000/api/v1`
  - 선택 값: `LEMON_API_TOKEN`, `LEMON_DEV_GATEWAY_TOKEN`,
    `LEMON_CERTIFICATE_PINS`
  - `.env`나 token 값을 Flutter asset으로 bundle하지 않는다.
- `mobile/README.md`와 `mobile/Lemon-Aid-ios/README.md`에 Xcode에서 어떤
  project/workspace를 열어야 하는지 명시했다.
- iOS Runner splash가 secure storage bootstrap 지연 시 멈출 수 있어
  `TokenSessionController.bootstrap()`에 timeout/fallback을 추가했다.
  - debug/local smoke: token storage가 지연되면 dev bypass로 shell 진입
  - release: token storage 실패 시 token 없이 login 경로 유지

### Xcode Flutter UIUX parity 검증 결과

- `dart format --output=none --set-exit-if-changed lib/features/auth/token_session.dart test/unit/token_session_test.dart`
  - passed
- `flutter test test/unit/token_session_test.dart`
  - 5 passed
- `./scripts/prepare-ios-flutter-uiux-xcode.sh`
  - `flutter pub get` passed
  - `flutter build ios --simulator --debug` passed
- `xcodebuild` equivalent through XcodeBuildMCP with
  `workspacePath=mobile/ios/Runner.xcworkspace`, `scheme=Runner`,
  `CODE_SIGNING_ALLOWED=NO`
  - build succeeded
- XcodeBuildMCP simulator install/launch
  - simulator: iPhone 17 Pro iOS 26.5
  - bundle id: `com.example.lemonAidMobile`
  - install succeeded
  - launch succeeded
- XcodeBuildMCP screenshot 확인
  - Flutter splash 확인
  - 17 Pro 스타일 home shell 확인
  - 하단 중앙 `+` action palette 확인

### iOS 26.5 Flutter Runner 재정렬

- Flutter iOS Runner의 deployment target을 iOS 26.5로 재정렬했다.
  - `mobile/ios/Runner.xcodeproj/project.pbxproj`
  - `mobile/ios/Podfile`
  - `mobile/ios/Podfile.lock`
- CocoaPods target도 `post_install`에서 `IPHONEOS_DEPLOYMENT_TARGET=26.5`로
  맞춰 Xcode workspace 빌드와 Flutter CLI 빌드가 같은 기준을 쓰게 했다.
- Xcode에서 다른 UI가 보인 원인은 `mobile/Lemon-Aid-ios/Lemon-Aid.xcodeproj`
  native smoke shell을 실행했기 때문이다. Android Studio와 같은 UIUX는
  `mobile/ios/Runner.xcworkspace`의 `Runner` scheme이 기준이다.
- `mobile/scripts/prepare-ios-flutter-uiux-xcode.sh`를 정리해 Xcode 실행 전
  Flutter iOS simulator build와 dart-define 준비를 한 번에 수행하도록 했다.
- iOS 26.5 simulator에서 native smoke bundle `yeongs.Lemon-Aid`를 제거하고
  Flutter bundle `com.example.lemonAidMobile`을 설치/실행해 혼동을 줄였다.

### iOS 26.5 Flutter Runner 재검증 결과

- `LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1 ./scripts/prepare-ios-flutter-uiux-xcode.sh`
  - `flutter pub get` passed
  - `flutter build ios --simulator --debug` passed
- XcodeBuildMCP build/install/launch
  - workspace: `mobile/ios/Runner.xcworkspace`
  - scheme: `Runner`
  - simulator: iPhone 17 Pro iOS 26.5
  - bundle id: `com.example.lemonAidMobile`
  - result: succeeded
- XcodeBuildMCP screenshot
  - `/var/folders/jj/jmmwhm2j6yq4m7x46gjbzz8r0000gn/T/screenshot_optimized_0075a75e-5a4d-4ba0-a105-4668092d5702.jpg`
  - 17 Pro 스타일 Flutter home shell, 하단 5-tab navigation, 중앙 `+` 버튼 확인
- `flutter analyze`
  - No issues found
- `flutter test`
  - 68 passed
- `git diff --check`
  - passed
- `detect-secrets scan` on changed iOS/doc/script files
  - no findings

### 음식 YOLO endpoint 연결 검증 결과

- `PYTHONPATH=backend/Nutrition-backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/services/test_meal_image_analysis.py backend/Nutrition-backend/tests/unit/vision/test_food_yolo.py backend/Nutrition-backend/tests/unit/test_config.py -q --no-cov`
  - 82 passed
- `black --check backend/Nutrition-backend/src/api/v1/meals.py backend/Nutrition-backend/src/config.py backend/Nutrition-backend/src/services/meal_image_analysis.py backend/Nutrition-backend/src/vision/food_yolo.py backend/Nutrition-backend/tests/unit/services/test_meal_image_analysis.py backend/Nutrition-backend/tests/unit/test_config.py backend/Nutrition-backend/tests/unit/vision/test_food_yolo.py`
  - passed
- `ruff check` on the same changed backend Python files
  - passed
- `dart format --output=none --set-exit-if-changed lib test`
  - passed
- `flutter analyze`
  - No issues found
- `flutter test`
  - 65 passed
- `PYTHONPATH=backend/Nutrition-backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/services/test_meal_image_analysis.py -q --no-cov`
  - 11 passed
- `flutter test test/unit/app_controller_test.dart test/unit/supplement_repository_test.dart test/widget/analysis_result_screen_test.dart`
  - 23 passed
- `flutter test`
  - 68 passed
- `flutter analyze`
  - No issues found
- FastAPI import/path check
  - `/api/v1/meals/{meal_id}/confirm` present
- 모바일 endpoint contract 확인
  - supplement: `POST /api/v1/supplements/analyze`, field `image`, fields `client_request_id`, `ocr_provider`
  - meal: `POST /api/v1/meals/analyze-image`, field `image`, fields `client_request_id`, `meal_type`
  - meal confirm: `POST /api/v1/meals/{meal_id}/confirm`, body
    `analysis_id`, `food_items`, `user_confirmed`
  - local Ollama explanation path는 기존 `/supplements/recommendations/explain` 및 analysis explain endpoint를 그대로 유지

## 남은 TODO

- Google Vision provider는 HTTP 401을 해결할 수 있도록 API key 활성화, Vision API 권한, billing/project 제한을 확인한다.
- 실제 촬영 이미지 fixture로 provider benchmark manifest를 생성하고 `b53b196`의 구조화 지표를 비교한다.
- YOLO ROI가 켜진 Docker/runtime에서 `roi_count`, selected ROI, parser 결과가 review UI에 기대대로 반영되는지 확인한다.
- 음식 YOLO는 `ENABLE_FOOD_YOLO_DETECTOR=true`로 Docker backend를 재기동한 뒤
  실제 식단 사진에서 후보명과 bbox가 review-only로 표시되는지 live smoke를 진행한다.
- 식단 confirmation endpoint는 연결됐으므로, 다음 단계는 실제 Android
  emulator/식단 사진에서 후보 확인 후 저장되는 live smoke다.
- Android emulator에서 gallery image -> multi-image batch -> manual correction -> registration -> analysis explanation까지 남은 end-to-end smoke를 진행한다.
- Xcode native iOS는 gallery 입력 기반 OCR smoke를 진행하고, 실제 촬영은 물리 iPhone/ngrok flow에서 검증한다.
- Android Studio run configuration에 `dev` flavor와 `LEMON_API_BASE_URL` dart define을 저장할지 팀 합의가 필요하다.

## 주의할 파일/커밋 제외 항목

- 기존 untracked 항목은 이번 작업 범위에서 건드리지 않는다.
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- 로컬 `.env`, ngrok token, gateway token, provider credential, raw OCR/provider payload, 이미지 원본, object URI는 절대 stage하지 않는다.
- 음식 YOLO `best.pt`는 ignored local artifact이며 supplement label ROI 모델로 오인하지 않는다.
