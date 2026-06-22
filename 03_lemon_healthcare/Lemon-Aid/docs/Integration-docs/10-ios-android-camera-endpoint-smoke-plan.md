# 10. iOS and Android Camera Endpoint Smoke Plan

- Date: 2026-05-25
- Branch: `feat/db-internal-learning-pipeline`
- Scope: iOS Simulator, physical iPhone, Android Studio Emulator, physical
  Android camera connection paths for the real Lemon-Aid OCR endpoint

## 1. Official References Checked

| Area | Official source | Implementation implication |
| --- | --- | --- |
| Flutter camera plugin | https://pub.dev/packages/camera | Use `availableCameras`, `CameraController`, `CameraPreview`, lifecycle disposal/re-init, and sanitized `CameraException` handling. |
| Flutter image picker | https://pub.dev/packages/image_picker | Keep gallery fallback and Android lost-data recovery for OCR endpoint tests when direct camera is unavailable. |
| Flutter CLI | https://docs.flutter.dev/reference/flutter-cli | Use `flutter devices`, `flutter run`, `flutter test`, and `flutter analyze` as the supported run/verification surface. |
| iOS camera permission | https://developer.apple.com/documentation/avfoundation/requesting-authorization-to-capture-and-save-media | Keep `NSCameraUsageDescription` in `ios/Runner/Info.plist`. |
| iOS photo library permission | https://developer.apple.com/documentation/BundleResources/Information-Property-List/NSPhotoLibraryUsageDescription | Keep `NSPhotoLibraryUsageDescription` for gallery fallback. |
| Android Emulator camera | https://developer.android.com/studio/run/emulator-use-camera | Android Emulator supports camera functionality and virtual-scene image import for camera apps. |
| Android Emulator extended controls | https://developer.android.com/studio/run/emulator-extended-controls | Use Extended controls > Camera for virtual scene image reload/import during emulator tests. |
| Android Emulator host loopback | https://developer.android.com/studio/run/emulator-networking-address | Android Emulator reaches the local backend through `10.0.2.2`, not host `127.0.0.1`. |

I could not find an official Apple documentation page that explicitly states a
general "iOS Simulator camera is unsupported" rule for all current simulator
versions. The implementation therefore treats `camera.availableCameras()` as
the runtime source of truth. When iOS reports no cameras, the app guides the
operator to gallery fallback or physical iPhone testing.

## 2. Runtime Strategy

The app now probes camera availability inside the supplement capture flow:

1. `CameraReadinessProbe.check()` calls Flutter `camera.availableCameras()`.
2. The result is reduced to a sanitized `CameraReadinessSnapshot`.
3. The capture surface shows platform-specific guidance:
   - iOS with no camera: use gallery fallback on Simulator, or run on a
     physical iPhone for direct capture.
   - Android with no camera: enable an AVD camera in Android Studio, then
     refresh the probe; gallery fallback remains available.
   - Any runtime with cameras: enable direct capture.
4. Both gallery and direct-capture images call the same endpoint path:
   `BackendLemonAidRepository.analyzeSupplementImage(...)`.

No mobile YOLO or Ollama endpoints were added. YOLO ROI and multimodal/local
LLM behavior remain backend runtime settings.

## 3. Endpoint Contract

The camera/gallery test path must keep this exact backend request:

- `POST /api/v1/supplements/analyze`
- multipart field: `image`
- form fields:
  - `client_request_id`
  - `ocr_provider`
- debug OCR provider values:
  - `configured`
  - `paddleocr`
  - `google_vision`
  - `clova`

The app may add only safe transport headers:

- `Authorization: Bearer <jwt>` when a test/staging JWT is provided
- `X-Lemon-Dev-Gateway-Token` only for local ngrok gateway smoke

## 4. iOS Environment Plan

### 4.1 iOS Simulator

Purpose: verify app identity, navigation, gallery-to-OCR endpoint flow, review,
registration, and local LLM explanation UI without physical camera hardware.

Run:

```bash
cd mobile
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  flutter run -d <ios-simulator-udid> --no-resident \
  --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Expected result:

- capture tab opens in the 5-tab shell;
- camera probe either reports no camera or an unavailable/error state without
  crashing;
- gallery button remains enabled;
- selecting a gallery label image reaches OCR preview/review;
- `분석하기` sends the real `/supplements/analyze` request.

If using the local token-gated gateway instead of direct backend:

```bash
cd mobile
flutter run -d <ios-simulator-udid> --no-resident \
  --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8010/api/v1 \
  --dart-define=LEMON_DEV_GATEWAY_TOKEN=<local-smoke-token>
```

### 4.2 Physical iPhone

Purpose: verify direct camera capture and the full OCR/YOLO/Ollama backend path.

Preflight:

```bash
flutter devices
python backend/scripts/check_mobile_ngrok_camera_readiness.py \
  --require-gateway \
  --require-ngrok \
  --require-physical-device
```

Run through ngrok gateway:

```bash
cd mobile
flutter run -d <ios-device-id> \
  --dart-define=LEMON_API_BASE_URL=https://<ngrok-host>/api/v1 \
  --dart-define=LEMON_DEV_GATEWAY_TOKEN=<local-smoke-token>
```

Manual checks:

1. Open capture tab.
2. Confirm the probe shows an iOS camera connected.
3. Capture the full supplement label.
4. Analyze, review OCR-derived fields, register.
5. Request local LLM explanation only when backend Ollama settings are enabled.

## 5. Android Environment Plan

### 5.1 Android Studio Emulator

Purpose: verify direct camera or virtual-scene camera behavior and local backend
loopback without public tunnel exposure.

Android Studio setup:

1. Open Device Manager.
2. Edit the target AVD.
3. Set Back camera or Front camera to Virtual scene or a host webcam.
4. Boot the emulator.
5. If using virtual-scene images, open Extended controls > Camera and add/reload
   a PNG or JPEG test label image.

Run:

```bash
cd mobile
flutter run -d emulator-5554 --flavor dev \
  --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1
```

Expected result:

- camera probe reports Android camera connected when AVD camera is configured;
- direct shutter opens live preview and captures an image;
- gallery fallback still works if the AVD camera is disabled;
- both paths reach `/api/v1/supplements/analyze`.

### 5.2 Physical Android

Purpose: verify actual camera behavior through the same backend contract as
iPhone physical smoke.

Run through ngrok gateway:

```bash
cd mobile
flutter run -d <android-device-id> --flavor dev \
  --dart-define=LEMON_API_BASE_URL=https://<ngrok-host>/api/v1 \
  --dart-define=LEMON_DEV_GATEWAY_TOKEN=<local-smoke-token>
```

Manual checks match the physical iPhone path.

## 6. Implementation Notes

- `mobile/lib/features/supplements/camera_readiness.dart` keeps camera probing
  isolated and unit-testable.
- `SupplementFlowScreen` disables direct shutter when the probe reports no
  camera or blocked permission, but leaves gallery fallback enabled.
- The live camera screen still uses `CameraController(enableAudio: false)` and
  disposes/reinitializes on lifecycle changes.
- `image_picker.retrieveLostData()` remains in place for Android MainActivity
  destruction recovery.
- The UI never logs image bytes, raw OCR text, provider raw payloads, object
  URIs, bearer tokens, gateway tokens, or ngrok URLs.

## 7. Verification Gates

Mobile:

```bash
cd mobile
flutter pub get
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

Backend contract slice if endpoint behavior changes:

```bash
PYTHONPATH=Nutrition-backend:.. /private/tmp/lemon-p1-quality-venv/bin/python \
  -m pytest \
  Nutrition-backend/tests/integration/api/test_supplement_intake_api.py \
  Nutrition-backend/tests/integration/api/test_supplement_intake_image_safety.py \
  Nutrition-backend/tests/unit/scripts/test_dev_mobile_ngrok_backend_gateway.py \
  Nutrition-backend/tests/unit/scripts/test_check_mobile_ngrok_camera_readiness.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  -q --no-cov
```

Security:

```bash
git diff --check
detect-secrets scan --exclude-files '^\.env$' $(git diff --name-only)
git status --short --ignored .env
```

## 8. Current Machine Probe

Observed on 2026-05-25 after implementation:

- `flutter devices` initially saw `iPhone 17 Pro` Simulator and no booted
  Android emulator.
- `flutter emulators` lists `lemon_pixel_8_api_36` and
  `plusultra_pixel_8_api_36` as available Android emulators.
- Direct Android SDK launch of `lemon_pixel_8_api_36` brought up
  `emulator-5554`.
- `adb shell getprop sys.boot_completed` returned `1`.
- `adb shell pm list features` included:
  - `android.hardware.camera`
  - `android.hardware.camera.any`
  - `android.hardware.camera.front`
  - `android.hardware.camera.autofocus`
  - `android.hardware.camera.flash`
- `flutter run -d emulator-5554 --no-resident --flavor dev
  --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` built,
  installed, and launched the app on the Android Emulator.
- Host backend preflight returned HTTP `200` for `/health` and
  `/api/v1/me/privacy/consents`.
- Flutter reports the user's physical iPhone over wireless discovery, but it is
  not currently ready for deployment until the device is unlocked, attached or
  paired on the same LAN, and opted into Developer Mode.

This means the iOS Simulator run path, Android Emulator run path, Android camera
feature exposure, and host backend preflight are verified locally. A
physical-phone camera smoke still needs the device trust/Developer Mode setup
and a live backend or token-gated ngrok gateway.
