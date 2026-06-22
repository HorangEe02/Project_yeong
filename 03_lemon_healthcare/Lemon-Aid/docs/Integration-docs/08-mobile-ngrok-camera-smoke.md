# 08. Mobile ngrok Camera Smoke Runbook

> Status: token-gated simulator gateway smoke verified, physical device/ngrok live smoke pending
> Date: 2026-05-25
> Scope: Flutter supplement label camera capture, local ngrok HTTPS tunnel, and
> backend OCR endpoint smoke on `feat/db-internal-learning-pipeline`

## 1. Objective

This runbook lets the mobile app test the real camera-to-OCR path from a phone
without weakening backend `TrustedHost` rules or committing transient tunnel
URLs. The app still calls the existing backend route:

- `POST /api/v1/supplements/analyze`
- multipart field: `image`
- form fields: `client_request_id`, `ocr_provider`

YOLO ROI and Ollama vision assist remain backend runtime settings. The mobile
app only selects the OCR provider in debug builds.

## 2. Official References Checked

| Area | Source | Design implication |
| --- | --- | --- |
| Flutter camera plugin | https://pub.dev/packages/camera | Use `availableCameras`, `CameraController`, `CameraPreview`, and `takePicture` for direct capture. |
| Flutter camera cookbook | https://docs.flutter.dev/cookbook/plugins/picture-using-camera | Initialize a `CameraController`, display a preview, and handle the returned `XFile` from `takePicture`. |
| Apple camera permission | https://developer.apple.com/documentation/bundleresources/information-property-list/nscamerausagedescription | Keep `NSCameraUsageDescription` in `Info.plist` for camera access. |
| ngrok HTTP endpoints | https://ngrok.com/docs/http | A public HTTPS endpoint forwards requests to a local upstream service. |
| ngrok agent CLI | https://ngrok.com/docs/agent/cli/ | Use `ngrok http <port>` for local HTTP tunnel smoke. |
| Android emulator networking | https://developer.android.com/studio/run/emulator-networking-address | Android emulator reaches the host machine through `10.0.2.2`; physical phones need LAN or HTTPS tunnel access. |

## 3. Local Backend Preflight

Start the backend with the normal local OCR/YOLO/Ollama settings needed for the
test. Verify the backend without exposing any secrets:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/api/v1/me/privacy/consents
```

Expected result: both requests return HTTP `200`. Do not print `.env`, provider
payloads, raw OCR output, image bytes, object URIs, or bearer tokens in logs.

## 4. ngrok Host-Rewriting Gateway

FastAPI `TrustedHost` should not be widened to arbitrary ngrok domains for local
smoke testing. Instead, run the local-only gateway. For public ngrok testing,
require a short-lived operator-generated token:

```bash
export LEMON_DEV_GATEWAY_TOKEN=<random-local-smoke-token>
python backend/scripts/dev_mobile_ngrok_backend_gateway.py \
  --listen-port 8010 \
  --backend-url http://127.0.0.1:8000 \
  --require-token
```

Then verify the gateway:

```bash
curl -sS \
  -H "X-Lemon-Dev-Gateway-Token: ${LEMON_DEV_GATEWAY_TOKEN}" \
  http://127.0.0.1:8010/health
curl -sS \
  -H "X-Lemon-Dev-Gateway-Token: ${LEMON_DEV_GATEWAY_TOKEN}" \
  http://127.0.0.1:8010/api/v1/me/privacy/consents
```

The gateway forwards request bodies but logs only method and status. It does not
forward the development gateway token to the backend and does not log image
bytes, OCR text, provider payloads, object URIs, or secrets.

## 5. Public Tunnel

Start a fresh tunnel to the gateway:

```bash
ngrok http 8010 --web-addr 127.0.0.1:4041
```

Fetch the assigned URL from the local ngrok API:

```bash
curl -sS http://127.0.0.1:4041/api/tunnels
```

Use only the returned HTTPS origin for the current smoke run. Do not commit the
random URL. Do not reuse a tunnel that is protected by basic auth unless the app
has a separate safe auth path; credentials must not be embedded in the app.

## 6. Flutter Runs

For a physical iPhone:

```bash
cd mobile
flutter run -d <ios-device-id> \
  --dart-define=LEMON_API_BASE_URL=https://<ngrok-host>/api/v1 \
  --dart-define=LEMON_DEV_GATEWAY_TOKEN=${LEMON_DEV_GATEWAY_TOKEN}
```

For a physical Android phone:

```bash
cd mobile
flutter run -d <android-device-id> --flavor dev \
  --dart-define=LEMON_API_BASE_URL=https://<ngrok-host>/api/v1 \
  --dart-define=LEMON_DEV_GATEWAY_TOKEN=${LEMON_DEV_GATEWAY_TOKEN}
```

For iOS Simulator build/gallery smoke:

```bash
cd mobile
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  flutter build ios --simulator --debug \
  --dart-define=LEMON_API_BASE_URL=https://<ngrok-host>/api/v1
```

For Android emulator local backend smoke without ngrok:

```bash
cd mobile
flutter run -d emulator-5554 --flavor dev \
  --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1
```

### 6.1 Simulator Bundle Identity Check

If two simulators show different Lemon-Aid screens, first confirm that they are
running the same bundle. On 2026-05-25, the iPhone 17 Pro Simulator was showing
a stale/source-branch app with bundle ID `com.lemonaid.lemonAid`, while the
iPhone 17 Simulator was showing this branch's app with bundle ID
`com.example.lemonAidMobile`.

Use these checks before comparing UI:

```bash
flutter devices --machine
xcrun simctl get_app_container <simulator-udid> com.example.lemonAidMobile app
xcrun simctl listapps <simulator-udid> | rg "com.example.lemonAidMobile|com.lemonaid.lemonAid|CFBundle"
```

Install this branch on a specific simulator before taking screenshots:

```bash
cd mobile
flutter run -d <simulator-udid> --no-resident \
  --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Do not treat `com.lemonaid.lemonAid` and `com.example.lemonAidMobile` as the
same app during UI review. Removing the stale simulator app is optional and
deletes simulator-local data for that bundle.

## 7. Manual Test Steps

1. Connect a physical phone and confirm it appears in `flutter devices`.
2. Open the supplement capture flow.
3. Select the debug OCR provider: `configured`, `paddleocr`, `google_vision`, or
   `clova`.
4. Tap camera, align the full supplement label inside the guide, and capture.
5. Analyze the image.
6. Review OCR text and low-confidence fields before saving.
7. Register the supplement.
8. Request local LLM explanation through the existing recommendation explanation
   flow when Ollama is enabled on the backend.

## 8. Readiness Preflight

Before a physical-device camera test, run the sanitized readiness preflight:

```bash
python backend/scripts/check_mobile_ngrok_camera_readiness.py \
  --require-gateway \
  --require-ngrok \
  --require-physical-device \
  --require-ollama \
  --ollama-model qwen3.5:9b
```

For a non-blocking status check while setup is still in progress, omit the
`--require-*` flags. The script prints counts and booleans only; it does not
print public ngrok URLs, gateway tokens, bearer tokens, OCR payloads, image
bytes, object URIs, or raw Flutter stderr. `flutter_devices_probe` distinguishes
normal device visibility from sanitized Flutter tool failures such as
`permission_error`, `timeout`, or `unavailable`. `gateway_contract` checks the
same consent endpoint the app calls on launch, so a healthy `/health` response
cannot hide a database-backed mobile contract failure.
`ollama_model_present=True` means the local Ollama `/api/tags` response includes
the configured parser model; it does not print model names or raw model output.
`physical_device_ready=True` means Flutter can see at least one physical phone;
`device_deploy_probe=not_checked` means the script has not installed or launched
the app, so Developer Mode, signing, and trust prompts still need the `flutter
run` step below.

After Flutter can see a physical phone, optionally run a sanitized deploy probe:

```bash
python backend/scripts/check_mobile_ngrok_camera_readiness.py \
  --require-gateway \
  --require-physical-device \
  --check-device-deploy \
  --deploy-device-id <ios-device-id> \
  --deploy-timeout-seconds 60
```

The deploy probe invokes `flutter run --no-resident` and reports only statuses
such as `launched`, `developer_mode_or_trust_required`, `signing_error`, or
`timeout`; it does not print raw Flutter output, gateway tokens, or public URLs.

## 9. Known Limits

| Limit | Current state | Action |
| --- | --- | --- |
| iOS Simulator camera | The app now probes `availableCameras()` at runtime; when no iOS camera is reported, gallery fallback still exercises the same OCR endpoint. | Use a physical iPhone for direct capture when the probe reports no cameras. |
| Android Emulator camera | Android Emulator can use a configured AVD camera or virtual-scene image, but an AVD with cameras disabled will report no usable camera. | Configure Device Manager camera settings, then use the in-app camera refresh button or gallery fallback. |
| Physical iPhone visibility | The device must be unlocked, trusted, paired, and Developer Mode enabled. | Re-run `flutter devices` before smoke. |
| Existing authenticated ngrok tunnel | Basic-auth protected tunnels return `401` to the app unless credentials are embedded. | Start a fresh development tunnel to the local gateway. |
| Release auth | `LEMON_API_TOKEN` and `LEMON_DEV_GATEWAY_TOKEN` are local-smoke only. | Never embed tokens in release builds. |

## 10. Current Verification Evidence

Verified on 2026-05-25 from
`/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`:

| Requirement | Evidence | Result |
| --- | --- | --- |
| Branch and remote | `git status --short --branch`, `git ls-remote origin feat/db-internal-learning-pipeline` | Local branch and remote branch synchronized before this evidence update |
| Local backend | `curl -i http://127.0.0.1:8000/health` | `200`, `{"status":"ok","version":"0.1.0"}` |
| Gateway token enforcement | `curl -i http://127.0.0.1:8010/health` with token-required gateway | `401 Unauthorized` without `X-Lemon-Dev-Gateway-Token` |
| Gateway token rejection | `curl -i -H 'X-Lemon-Dev-Gateway-Token: <wrong-token>' http://127.0.0.1:8010/health` | `401 Unauthorized` |
| Gateway token success | `curl -i -H 'X-Lemon-Dev-Gateway-Token: <local-smoke-token>' http://127.0.0.1:8010/health` | `200` through `LemonAidDevGateway` |
| Gateway unit coverage | `pytest backend/Nutrition-backend/tests/unit/scripts/test_dev_mobile_ngrok_backend_gateway.py -q --no-cov` | `4` tests passed; token opt-in, 401 rejection, Host rewrite, token stripping, and POST body forwarding covered without opening test sockets |
| Readiness preflight unit coverage | `pytest backend/Nutrition-backend/tests/unit/scripts/test_check_mobile_ngrok_camera_readiness.py -q --no-cov` | `9` tests passed; device parsing, sanitized Flutter probe failures, deploy blocker classification, ngrok gateway matching, mobile contract failure, optional incomplete status, required failure status, and sanitized formatting covered |
| Readiness preflight with backend up | `python backend/scripts/check_mobile_ngrok_camera_readiness.py --flutter-bin /opt/homebrew/bin/flutter` | `status=incomplete`, backend `200`, gateway contract `unreachable`, iOS simulator `1`, physical devices `0`, ngrok gateway matches `0` |
| Readiness preflight with live services stopped | `python backend/scripts/check_mobile_ngrok_camera_readiness.py --flutter-bin /opt/homebrew/bin/flutter` | `status=failed`, backend `unreachable`, gateway `unreachable`, gateway contract `unreachable`, `flutter_devices_probe=permission_error`, physical devices `0`, ngrok gateway matches `0` |
| Readiness preflight with local gateway and DB stopped | `python backend/scripts/check_mobile_ngrok_camera_readiness.py --backend-health-url http://127.0.0.1:8001/health --gateway-health-url http://127.0.0.1:8011/health --gateway-contract-url http://127.0.0.1:8011/api/v1/me/privacy/consents --expected-gateway-url http://127.0.0.1:8011 --flutter-bin /opt/homebrew/bin/flutter --require-gateway` | `status=failed`, backend `200`, gateway `200`, gateway contract `500`, iOS simulator `1`, physical devices `0`, ngrok gateway matches `0` |
| Team backend container contract | `curl -i http://127.0.0.1:8000/api/v1/me/privacy/consents` | `200`; confirms the running `lemon-aid-team-backend` container and DB can serve the mobile launch contract |
| Readiness preflight with team backend gateway | `python backend/scripts/check_mobile_ngrok_camera_readiness.py --flutter-bin /opt/homebrew/bin/flutter --require-gateway` with token-gated gateway on `8010` to backend `8000` | `status=incomplete`, backend `200`, gateway `200`, gateway contract `200`, iOS simulator `1`, physical devices `0`, ngrok gateway matches `0` |
| iOS simulator availability | `flutter devices` after booting `iPhone 17` | Simulator visible as `C98610F7-7B4C-4202-A18C-498F43A20AA0` |
| iOS simulator gateway app run | `flutter run -d C98610F7-7B4C-4202-A18C-498F43A20AA0 --no-resident --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8010/api/v1` | App installed and launched; gateway logged sanitized `GET 200` calls |
| iOS simulator token-gated app run | Same simulator run plus `--dart-define=LEMON_DEV_GATEWAY_TOKEN=<local-smoke-token>` | App installed and launched; token-required gateway logged sanitized `GET 200` calls |
| iOS simulator team backend gateway run | `flutter run -d C98610F7-7B4C-4202-A18C-498F43A20AA0 --no-resident --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8010/api/v1 --dart-define=LEMON_DEV_GATEWAY_TOKEN=<local-smoke-token>` | App installed and launched; dashboard rendered live summary without the previous `500` banner |
| iOS simulator screenshot | `xcrun simctl io ... screenshot /private/tmp/lemon-aid-ios-simulator-gateway-smoke.png` | Dashboard rendered live summary updated at `2026-05-25 15:58:15.939646` |
| iOS simulator team backend screenshot | `xcrun simctl io ... screenshot /private/tmp/lemon-aid-ios-simulator-8010-container-gateway.png` | Dashboard rendered live summary updated at `2026-05-25 16:43:24.132563` |
| iOS simulator app mismatch diagnosis | `simctl get_app_container` and `simctl listapps` on iPhone 17 Pro and iPhone 17 simulators | iPhone 17 Pro had stale/source bundle `com.lemonaid.lemonAid`; iPhone 17 had current bundle `com.example.lemonAidMobile` |
| iOS simulator current-branch reinstall | `flutter run -d 71FB0384-0C75-4CC4-925A-2A6598CAE89A --no-resident --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1` | Current branch app installed on iPhone 17 Pro and rendered the backend-connected dashboard/capture flow |
| UIUX selective import decision | `git diff --name-status HEAD..origin/feat/mobile-dashboard-redesign -- mobile` | Whole `mobile/` import rejected because source branch replaces current API/config/features/tests and platform guardrails |
| Physical iPhone visibility | `flutter devices --machine` | Physical iPhone visible as an iOS device; readiness reports `ios_physical=1` and `physical_device_ready=True` |
| Physical iPhone deploy attempt | `flutter run -d <ios-device-id> --no-resident ...` | Blocked before launch: iPhone requires Developer Mode in Settings > Privacy & Security or Xcode trust prompt handling |
| Physical iPhone deploy readiness classification | `python backend/scripts/check_mobile_ngrok_camera_readiness.py --check-device-deploy --deploy-device-id <ios-device-id> --deploy-timeout-seconds 60` | `status=failed`, `ios_physical=1`, `physical_device_ready=True`, `device_deploy_probe=developer_mode_or_trust_required`; no raw Flutter stderr printed |
| Public ngrok tunnel attempt | `ngrok http 8010 --web-addr 127.0.0.1:4041` | Not run: public tunnel opening was rejected by safety approval because it exposes local backend traffic to an external service |
| Flutter regression | `flutter analyze`, `flutter test` | No analyzer issues; `19` tests passed |
| Platform debug builds | `flutter build apk --debug --flavor dev ...`, `flutter build ios --simulator --debug ...` with gateway token define | Android dev APK and iOS simulator app built successfully |
| iOS simulator direct camera | `xcrun simctl help io` | Not supported; available operations are enumerate, poll, recordVideo, screenshot |
| Earlier physical iPhone detection | `flutter devices` before reconnect/trust progress | Previously not detected; now superseded by the physical visibility row above |
| Existing ngrok tunnel | `curl http://127.0.0.1:4040/api/tunnels` | Tunnel points to `http://localhost:8765`, not the backend gateway |
| Existing ngrok backend access | `curl -H 'ngrok-skip-browser-warning: true' <current-ngrok-origin>/health` | `401 Unauthorized`; unsuitable for mobile app without embedding credentials |

Public ngrok live smoke is intentionally not marked complete here. Starting a
fresh public tunnel exposes local backend endpoints through a third-party
service, so it should be run only with explicit operator approval and no secrets,
raw OCR payloads, image bytes, or object URIs in logs.
