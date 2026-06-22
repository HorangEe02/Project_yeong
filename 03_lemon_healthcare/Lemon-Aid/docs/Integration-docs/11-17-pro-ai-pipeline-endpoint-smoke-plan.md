# 11. 17 Pro AI Pipeline Endpoint Smoke Plan

- Date: 2026-05-25
- Branch: `feat/db-internal-learning-pipeline`
- Scope: iPhone 17 Pro Simulator UIUX plus backend OCR, YOLO ROI, and Ollama
  endpoint verification

## 1. Official References Checked

| Area | Official source | Implementation implication |
| --- | --- | --- |
| Flutter CLI | https://docs.flutter.dev/reference/flutter-cli | Use `flutter run`, `flutter analyze`, and `flutter test` for the mobile gate. |
| Flutter camera plugin | https://pub.dev/packages/camera | Keep camera availability as runtime truth; the simulator may fall back to gallery. |
| Flutter image picker | https://pub.dev/packages/image_picker | Keep gallery fallback and Android lost-data recovery on the same upload path. |
| Flutter package environment warning | https://pub.dev/packages/flutter_dotenv | Do not bundle `.env` or ngrok tokens as Flutter assets. |
| Android emulator host loopback | https://developer.android.com/studio/run/emulator-networking-address | Android Emulator uses `10.0.2.2` to reach the host backend. |
| Docker Desktop host gateway | https://docs.docker.com/desktop/features/networking/networking-how-tos/ | Development containers may reach a host-local Ollama server through `host.docker.internal`. |
| Ollama model listing API | https://docs.ollama.com/api/tags | Parser readiness checks `/api/tags` before sending OCR text to the local model. |

## 2. Endpoint Contract

The 17 Pro UIUX app must keep a single real analysis path:

- `POST /api/v1/supplements/analyze`
- multipart field: `image`
- form fields:
  - `client_request_id`
  - `ocr_provider`
- debug provider selectors:
  - `configured`
  - `paddleocr`
  - `google_vision`
  - `clova`

The mobile app does not add fake YOLO or Ollama endpoints:

- YOLO ROI is tested by enabling backend `ENABLE_VISION_CLASSIFIER`; the preview
  response exposes safe `pipeline_metadata.vision_roi_used`.
- Ollama vision assist is tested through the same analyze endpoint when backend
  multimodal settings select `ollama_vision_assist`.
- Ollama recommendation wording is tested through
  `/api/v1/supplements/recommendations/explain` with `use_local_llm=true`.

## 3. 17 Pro UIUX Smoke Flow

1. Run the backend locally with the desired OCR provider and optional YOLO/Ollama
   runtime settings.
   - If backend runs in Docker Desktop and Ollama runs on the Mac host, use
     `OLLAMA_BASE_URL=http://host.docker.internal:11434` in `development`.
     Keep `ALLOW_EXTERNAL_LLM=false`; the backend treats this Docker Desktop
     alias as local only outside staging/production.
2. Run the iPhone 17 Pro Simulator:

```bash
cd mobile
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  flutter run -d <iphone-17-pro-udid> --no-resident \
  --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

3. Open the 5-tab 17 Pro shell and enter the capture tab.
4. Select a provider in the OCR selector.
5. Use gallery fallback on Simulator, or direct camera on a physical iPhone.
6. Tap analyze and confirm the preview card shows:
   - requested provider;
   - actual backend OCR provider;
   - YOLO ROI `used` or `off`;
   - parser `used` or `pending`;
   - raw image/OCR retention `clean`.
7. Review OCR-derived fields and register the supplement.
8. Run recommendation refresh, then tap:
   - `Explain` for deterministic wording;
   - `Ollama` for local LLM wording.
9. Confirm the explanation chip reports whether Ollama wording was accepted.

Before interpreting `Parser: pending` as OCR model failure, run the sanitized
preflight with the local parser gate:

```bash
python backend/scripts/check_mobile_ngrok_camera_readiness.py \
  --require-ollama \
  --ollama-model qwen3.5:9b
```

`ollama_model_present=True` confirms the local parser model is visible through
Ollama `/api/tags`; it does not prove OCR accuracy, but it removes the common
runtime blocker where PaddleOCR output cannot reach structured parsing.

## 4. Physical iPhone / Ngrok Path

Use the token-gated gateway only for physical-device smoke:

```bash
cd mobile
flutter run -d <ios-device-id> \
  --dart-define=LEMON_API_BASE_URL=https://<ngrok-host>/api/v1 \
  --dart-define=LEMON_DEV_GATEWAY_TOKEN=<local-smoke-token>
```

Keep `NGROK_AUTHTOKEN`, `LEMON_DEV_GATEWAY_TOKEN`, provider credentials, OCR
payloads, object URIs, and tunnel URLs out of tracked files and staged diffs.

## 5. Expected Backend Runtime Matrix

| Test | Backend setting focus | Expected preview signal |
| --- | --- | --- |
| Paddle OCR | `OCR_PRIMARY_PROVIDER=paddleocr` | `ocr_provider=paddleocr_local` |
| Google Vision | `OCR_PRIMARY_PROVIDER=google_vision` with credentials | `ocr_provider=google_vision_document` |
| CLOVA | `OCR_PRIMARY_PROVIDER=clova` and `ENABLE_CLOVA_OCR=true` | `ocr_provider=clova_ocr` |
| YOLO ROI | `ENABLE_VISION_CLASSIFIER=true` | `vision_roi_used=true` when ROI is selected |
| Ollama vision assist | `ENABLE_MULTIMODAL_LLM=true` with assist policy enabled | `ocr_provider=ollama_vision_assist` when selected as OCR fallback |
| Ollama explanation | `use_local_llm=true` on explanation request | explanation `llm_used=true` when accepted |

## 6. Verification Gates

Mobile:

```bash
cd mobile
flutter pub get
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

Backend focused slice:

```bash
PYTHONPATH=Nutrition-backend:.. /private/tmp/lemon-p1-quality-venv/bin/python \
  -m pytest \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/integration/api/test_supplement_analyze_paddleocr_default.py \
  Nutrition-backend/tests/unit/scripts/test_dev_mobile_ngrok_backend_gateway.py \
  Nutrition-backend/tests/unit/scripts/test_check_mobile_ngrok_camera_readiness.py \
  -q --no-cov
```

Security:

```bash
git diff --check
detect-secrets scan --exclude-files '^\.env$' $(git diff --name-only)
git status --short --ignored .env
```
