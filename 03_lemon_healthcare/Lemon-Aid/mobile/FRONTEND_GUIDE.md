# Lemon Aid Mobile Frontend Guide

This guide documents the backend-connected mobile app on
`feat/db-internal-learning-pipeline` after selectively importing UIUX assets
from `origin/feat/mobile-dashboard-redesign`.

## Runtime Contract

- Package name: `lemon_aid_mobile`
- State model: Riverpod providers wrapping the existing `AppController`
- Navigation: source-branch-style `go_router` five-tab shell
- API base config: `LEMON_API_BASE_URL`, which must end with `/api/v1`
- Optional local token config: `LEMON_API_TOKEN`; never embed it in release builds
- Optional local gateway config: `LEMON_DEV_GATEWAY_TOKEN`; never embed it in release builds
- Release pin config: `LEMON_CERTIFICATE_PINS`

For Android emulator testing against a local backend, use:

```bash
flutter run --flavor dev \
  --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1
```

For a physical device, use an HTTPS gateway or tunnel that points to the same
backend `/api/v1` routes. Do not put ngrok basic-auth credentials or API tokens
in `--dart-define` values that might be reused for release builds.

## Simulator App Identity

When comparing iOS Simulator screens, verify the installed bundle first. The
UIUX source branch can leave a separate app installed as `com.lemonaid.lemonAid`,
while this branch runs as `com.example.lemonAidMobile`. If iPhone 17 Pro and
iPhone 17 appear to show different Lemon-Aid apps, they may simply be launching
different bundles.

```bash
flutter devices --machine
xcrun simctl get_app_container <simulator-udid> com.example.lemonAidMobile app
xcrun simctl listapps <simulator-udid> | rg "com.example.lemonAidMobile|com.lemonaid.lemonAid|CFBundle"
```

Install the current branch on the target simulator before taking screenshots:

```bash
flutter run -d <simulator-udid> --no-resident \
  --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Do not use the source branch bundle as proof that the current backend-connected
flow regressed. Keep the app-ID migration as a separate release decision.

## Device Camera and ngrok Smoke

The supplement capture screen now uses the Flutter `camera` plugin for direct
device preview and capture. The gallery path still uses `image_picker`, so iOS
simulator testing can use gallery images when a hardware camera is unavailable.

For Android emulator live camera testing on this Mac, start the emulator from
Android Studio or Android Studio's built-in Terminal so the emulator process is
owned by Android Studio. A Codex-launched emulator can appear connected but fail
to deliver host webcam frames. Run the app with:

```bash
flutter run -d emulator-5554 --flavor dev \
  --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1 \
  --dart-define=LEMON_ENABLE_EMULATOR_LIVE_CAMERA=true
```

The expected runtime evidence is that the Android Camera app and the Lemon Aid
camera screen both show the MacBook Pro camera feed, and `camera.provider.ranchu`
does not report `Unable to obtain video frame from the camera`.

Use this local-only flow when a physical phone needs to call a backend running on
the developer machine:

1. Start the backend on `127.0.0.1:8000`.
2. Start the local Host-rewriting gateway:

```bash
export LEMON_DEV_GATEWAY_TOKEN=<random-local-smoke-token>
python backend/scripts/dev_mobile_ngrok_backend_gateway.py \
  --listen-port 8010 \
  --backend-url http://127.0.0.1:8000 \
  --require-token
```

3. Start a fresh public tunnel to the gateway:

```bash
ngrok http 8010 --web-addr 127.0.0.1:4041
```

4. Run Flutter against the HTTPS tunnel:

```bash
flutter run -d <ios-device-id> \
  --dart-define=LEMON_API_BASE_URL=https://<ngrok-host>/api/v1 \
  --dart-define=LEMON_DEV_GATEWAY_TOKEN=${LEMON_DEV_GATEWAY_TOKEN}
```

For Android physical devices, add the dev flavor:

```bash
flutter run -d <android-device-id> --flavor dev \
  --dart-define=LEMON_API_BASE_URL=https://<ngrok-host>/api/v1 \
  --dart-define=LEMON_DEV_GATEWAY_TOKEN=${LEMON_DEV_GATEWAY_TOKEN}
```

The gateway rewrites the public ngrok `Host` header to the local backend host so
the backend `ALLOWED_HOSTS` policy does not need to allow arbitrary ngrok hosts.
It must only be used for local development smoke tests. The gateway token is
checked at the gateway and is not forwarded to the backend.

iOS Simulator can validate the app build and gallery-based OCR flow, but direct
camera capture requires a physical iPhone with Developer Mode enabled. Android
emulator local backend smoke should keep using `10.0.2.2`.

Before a physical-device smoke run, use the repo preflight from the project
root:

```bash
python backend/scripts/check_mobile_ngrok_camera_readiness.py \
  --require-gateway \
  --require-ngrok \
  --require-physical-device
```

This check fails closed when the backend, token-gated gateway, matching ngrok
tunnel, or physical device is missing. It prints only sanitized counts and
status flags, including `flutter_devices_probe` when the local Flutter device
probe itself fails. It also checks the launch-time consent API through
`gateway_contract`, because the dashboard can still fail when `/health` is OK
but the database-backed mobile contract is not ready.
`physical_device_ready=True` only confirms that Flutter can see a physical
phone. If `flutter run -d <ios-device-id>` says Developer Mode is required,
enable it on the iPhone under Settings > Privacy & Security, reconnect the
device, and handle any Xcode trust prompt before camera capture testing.
To classify this blocker through the preflight, add:

```bash
python backend/scripts/check_mobile_ngrok_camera_readiness.py \
  --require-gateway \
  --require-physical-device \
  --check-device-deploy \
  --deploy-device-id <ios-device-id> \
  --deploy-timeout-seconds 60
```

If the iOS Simulator shows a dashboard `500`, verify the gateway contract before
testing camera capture:

```bash
curl -i \
  -H "X-Lemon-Dev-Gateway-Token: ${LEMON_DEV_GATEWAY_TOKEN}" \
  http://127.0.0.1:8010/api/v1/me/privacy/consents
```

## Imported UIUX Assets

The app imports reusable assets only:

- `assets/animations/`
- `assets/app_icon/`
- `assets/design_system/`
- `assets/fonts/`
- `assets/icons/`
- `assets/illustrations/`
- `assets/mascot/`

The source branch router, auth services, Riverpod providers, and replacement
Android/iOS project files were not imported.

The detailed import boundary and simulator mismatch diagnosis are tracked in
`docs/Integration-docs/09-mobile-uiux-selective-import-and-simulator-diagnostics.md`.

## Auth and Local Tokens

The backend remains a JWT/OIDC resource server. The app does not call source
branch `/api/v1/auth/login` style endpoints because the current backend does
not expose a password-token issuer.

Debug builds can enter the shell without a token for local backends running
`AUTH_MODE=disabled`. Staging or JWT-backed testing can paste an externally
issued bearer token into the in-app API access panel. Stored tokens are attached
as `Authorization: Bearer <token>` and can be cleared from Settings.

For local ngrok runs, keep secrets in the ignored root `.env`:

```dotenv
NGROK_AUTHTOKEN=<operator-ngrok-agent-token>
LEMON_DEV_GATEWAY_TOKEN=<random-local-smoke-token>
LEMON_API_BASE_URL=https://<ngrok-host>/api/v1
```

Use the ngrok authtoken only with the ngrok agent config, for example:

```bash
set -a
source ../.env
set +a
ngrok config add-authtoken "$NGROK_AUTHTOKEN"
```

Do not add `.env` to Flutter assets. Flutter asset values can be extracted from
the app binary, so client-side env files are only appropriate for non-sensitive
configuration.

## OCR Test Flow

The supplement flow uses the existing backend path:

- `POST /api/v1/supplements/analyze`
- multipart field: `image`
- form fields: `client_request_id`, `ocr_provider`

Debug builds expose these OCR provider selectors:

- `configured`
- `paddleocr`
- `google_vision`
- `clova`

YOLO ROI detection and Ollama vision assist remain backend runtime settings.
The Flutter app does not invent separate YOLO or Ollama endpoints.
