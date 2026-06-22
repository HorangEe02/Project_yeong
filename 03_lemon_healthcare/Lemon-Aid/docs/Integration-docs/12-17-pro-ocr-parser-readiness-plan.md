# 12. 17 Pro OCR Parser Readiness Fix Plan

- Date: 2026-05-25
- Branch: `feat/db-internal-learning-pipeline`
- Scope: iPhone 17 Pro OCR upload succeeds, but OCR text is not converted into
  ingredient candidates

## 1. Official References Checked

| Area | Official source | Implementation implication |
| --- | --- | --- |
| Docker Desktop host access | https://docs.docker.com/desktop/features/networking/networking-how-tos/ | A backend container can reach a Mac-hosted local service through `host.docker.internal` in development. |
| Ollama model readiness | https://docs.ollama.com/api/tags | Preflight should check `/api/tags` for the configured parser model before a live OCR smoke. |
| Ollama chat endpoint | https://docs.ollama.com/api/chat | OCR text parsing ultimately depends on `/api/chat`, so model readiness is a real analyze-flow prerequisite. |

## 2. Confirmed Runtime Findings

The iPhone 17 Pro preview proved that the mobile app reached
`POST /api/v1/supplements/analyze`; this was not a disconnected endpoint.

Sanitized backend evidence showed:

- `configured` and `paddleocr` analysis requests returned preview rows.
- Recent audit metadata recorded `ocr_provider=paddleocr_local` and
  `ocr_confidence_present=true`.
- The failure code was `ocr_parse_preview_unavailable`, so the OCR stage had
  produced provider output but the structured parser did not complete.
- The Docker backend could reach the Mac Ollama server at
  `host.docker.internal:11434`, and the configured parser model was present.
- The backend local-only policy previously treated `host.docker.internal` as a
  non-local host, causing parser readiness to fail as `configuration_invalid`.

## 3. Diagnosis

This is primarily a runtime integration/readiness issue, not a model training
issue.

Training or provider tuning becomes relevant only after the active OCR provider
successfully sends text into the parser and the resulting ingredient candidates
are wrong. The observed state happened earlier: OCR provider output existed, but
the local Ollama parser handoff was blocked.

## 4. Implementation Plan

1. Keep the backend privacy boundary fail-closed:
   - allow `host.docker.internal` only when `ENVIRONMENT=development`;
   - keep staging/production limited to loopback hosts unless a separate private
     GPU policy is designed and reviewed.
2. Make the mobile camera preflight detect this failure class:
   - add a sanitized Ollama `/api/tags` probe;
   - report only `ollama_probe`, `ollama_model_present`, and model count;
   - add `--require-ollama` for live OCR/parser smoke runs.
3. Keep mobile endpoints unchanged:
   - the app continues to call `/api/v1/supplements/analyze`;
   - YOLO and Ollama remain backend runtime settings;
   - no raw OCR text, image bytes, model output, tokens, or public tunnel URLs are
     printed by preflight.
4. Rebuild or restart the backend image before simulator retest when the running
   container is not source-mounted.

## 5. Expected Operator Flow

Before a 17 Pro live OCR/parser smoke:

```bash
python backend/scripts/check_mobile_ngrok_camera_readiness.py \
  --require-ollama \
  --ollama-model qwen3.5:9b
```

For physical iPhone over ngrok, combine it with the existing gateway/device
gates:

```bash
python backend/scripts/check_mobile_ngrok_camera_readiness.py \
  --require-gateway \
  --require-ngrok \
  --require-physical-device \
  --require-ollama \
  --ollama-model qwen3.5:9b
```

Expected sanitized success signal includes:

- `backend_health=200`
- `gateway_contract=200` when the gateway is required
- `ollama_probe=ok`
- `ollama_model_present=True`

If the simulator still shows `Parser: pending` after these gates pass, the next
debug target is parser schema/output quality. If `ollama_model_present=False` or
`ollama_probe` is not `ok`, fix runtime setup before investigating OCR model
accuracy.
