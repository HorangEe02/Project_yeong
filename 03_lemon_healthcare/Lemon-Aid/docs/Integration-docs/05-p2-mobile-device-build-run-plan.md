# 05. P2 Mobile Device Build and Simulator Run Plan

> Status: local smoke completed
> Date: 2026-05-16
> Scope: Android debug build/emulator run and iOS simulator debug build/run for `mobile/flutter_app`
> Implementation stance: debug builds and simulator/emulator smoke are proven locally; release signing and physical devices remain out of scope

## 1. Objective

The P2 Flutter MVP must be proven on real mobile toolchains, not only through
`flutter analyze` and widget tests.

Completed local gates:

1. Flutter quality gate.
2. iOS Simulator debug build and run.
3. Android debug APK build and emulator run.
4. Backend-connected smoke for consent, dashboard, supplement image intake,
   OCR text parse, user-confirmed supplement registration, and dashboard refresh.

Release packaging, app-store signing, TestFlight, Play Store bundles, and
physical-device signing remain separate follow-up gates.

## 2. Official References Checked

| Area | Source | Design implication |
| --- | --- | --- |
| Flutter Android setup validation | https://docs.flutter.dev/platform-integration/android/setup | Use `flutter doctor`, `flutter emulators`, and `flutter devices`; Android SDK licenses and emulator/device visibility are required before run smoke. |
| Android virtual devices | https://developer.android.com/tools/avdmanager | AVD creation can be done with SDK CLI tools when Android Studio is not installed. |
| Android emulator host loopback | https://developer.android.com/studio/run/emulator-networking-address | Android emulator must call the host backend through `10.0.2.2`, not `127.0.0.1`. |
| Android cleartext HTTP | https://developer.android.com/privacy-and-security/risks/cleartext-communications | Debug HTTP to `10.0.2.2` needs an explicit debug-only cleartext allowance because the app targets API 36. |
| Flutter Android build outputs | https://docs.flutter.dev/deployment/android | Use debug APK first; defer signed app bundles until runtime smoke is stable. |
| Flutter iOS setup validation | https://docs.flutter.dev/platform-integration/ios/setup | Use a full Xcode install and iOS Simulator runtime; this machine uses `DEVELOPER_DIR` instead of global `xcode-select`. |
| Flutter iOS project settings | https://docs.flutter.dev/deployment/ios | Use simulator debug builds first; signing/team settings are later release work. |
| Apple Xcode simulator/device run | https://developer.apple.com/documentation/xcode/running-your-app-in-simulator-or-on-a-device | Simulator and physical device are separate gates. |
| Gradle Java compatibility | https://docs.gradle.org/current/userguide/compatibility.html | Pin Flutter to JDK 17 for the generated Android Gradle project. |

## 3. Current Local State

Observed on 2026-05-16 from `mobile/flutter_app`:

| Check | Result | Impact |
| --- | --- | --- |
| `flutter doctor -v` | `No issues found!` with `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer` | Flutter, Android, Xcode, Chrome, and network resources are usable. |
| Flutter/Dart | Flutter `3.41.9`, Dart `3.11.5` | Matches the generated app constraints. |
| Android SDK | `/opt/homebrew/share/android-commandlinetools` | Flutter config now points here. |
| Android packages | platform-tools, emulator `36.5.11`, platform `android-36`, build-tools `36.0.0`, system image `android-36;default;arm64-v8a` | Enough for debug APK build and emulator smoke. |
| Android first build additions | NDK `28.2.13676358`, Build-Tools `35.0.0`, CMake `3.22.1` | Installed automatically during the first Gradle build. |
| Android AVD | `lemon_pixel_8_api_36` | Appears in `flutter emulators` and boots headlessly. |
| JDK | Flutter `jdk-dir` is `/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home` | Avoids Java 25/Gradle compatibility risk. |
| iOS runtime | iOS `26.3`, `iPhone 17` simulator | Appears in `flutter devices` when booted. |
| Xcode | Xcode `26.3`, Build `17C528` | Works through `DEVELOPER_DIR`; global `xcode-select -p` still points to CommandLineTools. |
| CocoaPods | `1.16.2` | `pod install` passed during iOS build. |
| Android cleartext | `android/app/src/debug/AndroidManifest.xml` sets `usesCleartextTraffic=true` | Debug-only HTTP to `10.0.2.2` is allowed; release manifest is unchanged. |

## 4. Execution Results

### Flutter Quality Gate

Commands:

```sh
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
```

Result:

- `dart format`: `Formatted 20 files (0 changed)`
- `flutter analyze`: `No issues found`
- `flutter test`: `All tests passed`

### iOS Simulator Build and Run

Commands:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  flutter build ios --simulator --debug \
  --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1

DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  flutter run -d C98610F7-7B4C-4202-A18C-498F43A20AA0 \
  --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Result:

- Built `build/ios/iphonesimulator/Runner.app`.
- App launched on `iPhone 17`.
- Backend-connected run hit:
  - `GET /api/v1/me/privacy/consents` -> `200`
  - `GET /api/v1/dashboard/summary?days=30` -> `200`

### Android Debug Build and Run

Commands:

```sh
flutter build apk --debug \
  --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1

/opt/homebrew/share/android-commandlinetools/emulator/emulator \
  -avd lemon_pixel_8_api_36 -no-window -no-audio -no-snapshot -no-metrics

flutter run -d emulator-5554 \
  --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1
```

Result:

- Built `build/app/outputs/flutter-apk/app-debug.apk`.
- App installed and launched on `emulator-5554`.
- Backend-connected run hit:
  - `GET /api/v1/me/privacy/consents` -> `200`
  - `GET /api/v1/dashboard/summary?days=30` -> `200`

Notes:

- `flutter emulators --launch lemon_pixel_8_api_36` returned success but did not
  leave a running emulator process in this Codex environment. The direct
  `emulator -avd ...` command is the reliable local run path.
- Android backend calls require both `10.0.2.2` as the client base URL and
  backend `ALLOWED_HOSTS` including `10.0.2.2`.

### Backend-Connected API Smoke

Temporary environment:

- Repo-local Python venv: `yeong-Lemon-Aid/.venv`
- PostgreSQL: temporary `postgres:16` Docker container with
  `POSTGRES_USER=lemon`, `POSTGRES_PASSWORD=lemon`, `POSTGRES_DB=lemon`
- Migrations: `alembic upgrade 0004_create_p1_supplement_health`
- Backend command:

```sh
ALLOWED_HOSTS='["localhost","127.0.0.1","testserver","10.0.2.2"]' \
  ../.venv/bin/python -m uvicorn src.main:app \
  --app-dir Nutrition-backend \
  --host 127.0.0.1 \
  --port 8000
```

Verified responses:

| Step | Endpoint | Result |
| --- | --- | --- |
| Health | `GET /health` | `200` |
| Consent state | `GET /api/v1/me/privacy/consents` | `200` |
| Grant OCR consent | `POST /api/v1/me/privacy/consents/ocr_image_processing` | `201` |
| Grant health-analysis consent | `POST /api/v1/me/privacy/consents/sensitive_health_analysis` | `201` |
| Dashboard before registration | `GET /api/v1/dashboard/summary?days=30` | `200`, `registered_count=0` |
| Image intake | `POST /api/v1/supplements/analyze` | `202`, `status=requires_confirmation` |
| Manual OCR parse | `POST /api/v1/supplements/analyses/{analysis_id}/ocr-text` | `200`, candidate `Vitamin D 25 ug` |
| User-confirmed registration | `POST /api/v1/supplements` | `201` |
| Dashboard after registration | `GET /api/v1/dashboard/summary?days=30` | `200`, `registered_count=1` |

Important finding:

- The first `POST /api/v1/supplements/analyze` smoke exposed a real
  transaction bug: consent reads can auto-begin the request session, then
  `create_supplement_analysis_intake()` attempted another `session.begin()`.
- Fixed by changing supplement intake persistence to explicit
  `commit()/rollback()` and adding focused regression coverage.
- Verification: `15 passed` from:

```sh
../.venv/bin/python -m pytest \
  Nutrition-backend/tests/unit/services/test_supplement_intake.py \
  Nutrition-backend/tests/integration/api/test_supplement_intake_api.py \
  -q --no-cov
```

## 5. Residual Risks and Follow-Up

| Risk | Current state | Next action |
| --- | --- | --- |
| Global Xcode selection | `xcode-select -p` still returns `/Library/Developer/CommandLineTools` | Continue using `DEVELOPER_DIR=...` in runbooks, or manually run sudo `xcode-select --switch` outside Codex. |
| Full Alembic head on stock Postgres | `0005_create_learning_vector_tables` requires pgvector and fails on plain `postgres:16` | Use a pgvector-enabled image for full migration smoke; `0004` is enough for this mobile flow. |
| Android dev HTTP | Debug manifest allows cleartext for local smoke | Keep release manifest unchanged and require HTTPS for production. |
| Android TrustedHost | Backend rejects Android emulator Host header unless `10.0.2.2` is allowed | Include `10.0.2.2` in local `ALLOWED_HOSTS` run commands only. |
| Physical devices | Not tested | Needs LAN backend URL, physical-device permissions, and signing/provisioning gate. |
| CI expansion | Not added | Add Android debug build first; defer emulator/iOS CI until team accepts cost. |

## 6. Recommended Commit Plan

1. `fix(supplements): avoid nested transaction during image intake`
   - Why: backend-connected mobile smoke exposed a real request-session
     transaction conflict after consent checks.
2. `chore(mobile): enable debug emulator HTTP smoke`
   - Why: Android API 36 debug smoke needs explicit local cleartext allowance
     for `10.0.2.2` while release remains HTTPS-oriented.
3. `docs(mobile): record device build and backend smoke evidence`
   - Why: preserve exact local commands, environment caveats, and evidence for
     the team before deciding CI expansion.
