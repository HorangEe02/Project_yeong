# dev-guides/09 — Supplement Registration API Current Status

작성일: 2026-05-13

이 문서는 현재 FastAPI 라우터와 서비스에 연결된 영양제 intake/registration API만 설명한다. 과거 통합 설계 예시는 `docs/Nutrition-docs/previous-version/dev-guide-09-supplement-registration-api-design-example.md`로 이동했다.

## Endpoint Map

| Method | Path | Handler | Scope | Consent |
| --- | --- | --- | --- | --- |
| `POST` | `/api/v1/supplements/analyze` | `analyze_supplement_label` | `supplement:write` | `ocr_image_processing` |
| `POST` | `/api/v1/supplements/analyses/{analysis_id}/ocr-text` | `parse_supplement_analysis_ocr_text_preview` | `supplement:write` | `ocr_image_processing` |
| `POST` | `/api/v1/supplements` | `create_user_supplement` | `supplement:write` | `sensitive_health_analysis` |
| `GET` | `/api/v1/supplements` | `list_user_supplements` | `supplement:read` | route contract only |
| `GET` | `/api/v1/supplements/{supplement_id}` | `get_user_supplement` | `supplement:read` | route contract only |
| `DELETE` | `/api/v1/supplements/{supplement_id}` | `delete_user_supplement` | `supplement:delete` | route contract only |

## Intake Flow

`POST /api/v1/supplements/analyze`는 사용자 확인 전 preview를 만든다.

```text
supplements.py
  -> require_user_consent(OCR_IMAGE_PROCESSING)
  -> analyze_supplement_image
  -> read_and_validate_supplement_image
  -> create_supplement_analysis_intake
  -> optional OCR/parser adapter path
  -> supplement_analysis_run_to_preview
```

기본 호출에는 OCR, parser, vision adapter가 주입되지 않는다. 따라서 현재 API는 이미지 파일 검증과 preview 저장까지가 기본 보장 범위다.

OCR provider가 아직 연결되지 않은 환경에서도 `POST /api/v1/supplements/analyses/{analysis_id}/ocr-text`로 OCR text를 기존 preview에 attach할 수 있다. 이 endpoint는 OCR text를 normalize하고 HMAC hash만 저장한 뒤, local `OllamaSupplementParser` structured output을 `parsed_snapshot`으로 갱신한다. raw OCR text와 raw model response는 저장하지 않는다.

## Registration Flow

`POST /api/v1/supplements`는 사용자가 확인한 supplement payload를 저장한다.

```text
supplements.py
  -> require_user_consent(SENSITIVE_HEALTH_ANALYSIS)
  -> create_user_supplement_from_confirmation
  -> UserSupplement 저장
  -> UserSupplementIngredient 저장
  -> optional source preview confirmed 처리
```

등록 서비스는 `backend/src/services/supplement_registration.py`에 있으며, DB 모델은 `backend/src/models/db/supplement.py`에 있다.

## Storage Contract

| 모델 | 용도 |
| --- | --- |
| `SupplementAnalysisRun` | 확인 전 preview, image hash, OCR metadata hash, parsed snapshot |
| `SupplementProduct` | reference supplement product |
| `SupplementProductIngredient` | reference product ingredient |
| `UserSupplement` | 사용자가 확인한 supplement |
| `UserSupplementIngredient` | 사용자가 확인한 ingredient |

raw image bytes와 raw OCR text는 이 flow에서 DB에 저장하지 않는다.

## Error Contract

주요 실패 경로는 다음과 같다.

- missing scope: `403`
- missing consent: `403 consent_required`
- unsupported image media type: `415`
- oversized image: `413`
- duplicate idempotency key with different image: `409`
- OCR text blank/too long/provider invalid/confidence invalid: `422`
- OCR text parser unavailable or invalid structured output: `502`
- expired or invalid preview confirmation: `409`
- invalid confirmation payload: `422`

## 검증 포인트

- `tests/integration/api/test_supplement_intake_api.py`
- `tests/integration/api/test_supplement_ocr_text_api.py`
- `tests/unit/services/test_supplement_image_analysis.py`
- `tests/unit/services/test_supplement_registration.py`
