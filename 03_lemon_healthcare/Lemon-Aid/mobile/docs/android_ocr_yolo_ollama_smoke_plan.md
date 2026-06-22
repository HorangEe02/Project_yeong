# Android OCR + YOLO + Ollama Smoke Plan

This plan keeps the backend-connected Flutter app as the source of truth and
uses the teammate UIUX branch only for visual assets and camera interaction
patterns.

## Implementation Boundary

- Keep `LEMON_API_BASE_URL`, `LEMON_API_TOKEN`, `LEMON_DEV_GATEWAY_TOKEN`, and
  `LEMON_CERTIFICATE_PINS`.
- Keep `BackendLemonAidRepository.analyzeSupplementImage()`.
- Keep `POST /api/v1/supplements/analyze` with multipart field `image` and
  form fields `client_request_id` and `ocr_provider`.
- Keep supplement review, confirmation, registration, and local LLM explanation
  flow.
- Do not import source-branch mock analysis screens or source auth services.

## Android Studio Run

1. Start the local backend on the host Mac at `127.0.0.1:8000`.
2. Start the target emulator from Android Studio or Android Studio's built-in
   Terminal. This matters for host webcam access on macOS: when the emulator was
   launched by Codex, Android CameraService registered `webcam1` but the provider
   repeatedly failed with `Unable to obtain video frame from the camera`.
3. For live Mac camera preview inside the Lemon Aid camera screen, pass
   `LEMON_ENABLE_EMULATOR_LIVE_CAMERA=true`.
4. From `mobile/`, run the dev flavor against the Android emulator host alias:

```bash
flutter run -d emulator-5554 --flavor dev \
  --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1 \
  --dart-define=LEMON_ENABLE_EMULATOR_LIVE_CAMERA=true
```

`10.0.2.2` is the Android Emulator alias for the host loopback interface.
The current app has Android product flavors, so `--flavor dev` is required for
debug smoke runs.
The emulator command-line `-camera-back webcamN` option maps an AVD camera to a
host webcam. On this Mac, `webcam1` maps to `MacBook Pro 카메라`.

On this Mac, Docker can occupy the default emulator adb port pair `5554/5555`.
If `emulator-5554` remains offline, start the AVD on port `5560` and run:

```bash
/opt/homebrew/share/android-commandlinetools/emulator/emulator \
  -avd lemon_pixel_8_api_36 -port 5560
./scripts/run-android-dev.sh
```

If the launcher shows duplicate Lemon Aid icons, remove the stale non-dev
package from the emulator:

```bash
adb -s emulator-5560 uninstall com.example.lemon_aid_mobile
```

The dev package is `com.example.lemon_aid_mobile.dev`. Android does not always
pin newly installed apps to the home screen; open the app drawer and drag the
Lemon Aid icon to the home screen for the demo launcher layout.

## Provider Scenarios

- `configured`: validates the backend-selected OCR provider.
- `paddleocr`: validates local PaddleOCR routing.
- `google_vision`: validates Google Vision routing; credential failures should
  be treated separately from mobile endpoint failures.
- `clova`: validates CLOVA OCR routing.

YOLO ROI and Ollama vision/parser behavior remain backend runtime settings.
The mobile app only reports the pipeline metadata returned by the backend and
does not create separate YOLO or Ollama endpoints.

## Expected Evidence

- The app reaches the 5-tab shell.
- The camera tab can use gallery fallback or direct AVD camera capture.
- Direct AVD camera capture is considered ready only when the Android Camera app
  and Lemon Aid camera screen both show the Mac camera feed and logcat has no
  `camera.provider.ranchu` frame acquisition errors.
- Tapping `분석하기` calls the current repository flow, not a mock result route.
- Preview metadata shows actual OCR provider, YOLO ROI state, parser state, and
  clean retention state.
- Registration remains blocked until user review confirms usable ingredients.

## References

- Flutter CLI: https://docs.flutter.dev/reference/flutter-cli
- Android Emulator networking: https://developer.android.com/studio/run/emulator-networking-address
- Android Emulator command-line camera options: https://developer.android.com/studio/run/emulator-commandline
- Flutter camera plugin: https://pub.dev/packages/camera
