# OCR/Text Supplement Analysis Plan

작성일: 2026-05-13

## 결론

먼저 완성할 범위는 이미지 자체 분석이 아니다. P1 이후 첫 구현 단위는 `OCR/text -> structured supplement parse -> user confirmation` 흐름이다.

권장 방향은 다음과 같다.

1. 기존 `POST /api/v1/supplements/analyze`의 FastAPI file upload와 intake preview를 유지한다.
2. YOLO, multimodal image-to-text, 이미지 학습 업로드는 이번 범위에서 제외한다.
3. OCR provider가 만든 text 또는 수동 OCR text를 `parse_supplement_analysis_ocr_text`로 구조화한다.
4. 구조화 결과는 항상 `requires_confirmation` preview로 반환하고, `POST /api/v1/supplements`에서 사용자가 확인한 값만 저장한다.
5. raw image bytes, raw OCR text, raw model response는 DB에 저장하지 않는다.

## 공식 문서 확인

- FastAPI file uploads: <https://fastapi.tiangolo.com/tutorial/request-files/>
- FastAPI request forms and files: <https://fastapi.tiangolo.com/tutorial/request-forms-and-files/>
- Pydantic models: <https://docs.pydantic.dev/latest/concepts/models/>
- Ollama Chat API: <https://docs.ollama.com/api/chat>
- Ollama structured outputs: <https://docs.ollama.com/capabilities/structured-outputs>

공식 FastAPI 문서 기준 설계 반영 사항:

- file upload를 받으려면 `python-multipart`가 필요하다.
- 이미지처럼 큰 파일은 `bytes`보다 `UploadFile`이 적합하다. `UploadFile`은 spooled file을 사용하고 `filename`, `content_type`, async `read/seek/close`를 제공한다.
- 파일과 form field를 함께 받을 때는 `File`과 `Form`을 사용한다.
- multipart/form-data 요청에서는 같은 operation에 JSON body를 동시에 기대하면 안 된다. 따라서 `client_request_id` 같은 메타데이터는 `Form`으로 받고, 구조화된 JSON payload는 별도 text endpoint 또는 confirmation endpoint에서 받는다.

## 현재 코드 기준선

| 구간 | 현재 파일 | 현재 상태 |
| --- | --- | --- |
| FastAPI upload endpoint | `backend/src/api/v1/supplements.py` | `POST /api/v1/supplements/analyze`가 `UploadFile` + `Form` 사용 |
| 이미지 검증 | `backend/src/services/supplement_intake.py` | MIME, magic bytes, pixel, byte size 검증 후 preview 저장 |
| OCR adapter 계약 | `backend/src/ocr/base.py` | `OCRAdapter`, `OCRImageInput`, `OCRResult` 존재 |
| OCR preprocessor | `backend/src/ocr/preprocessing.py` | RGB PNG normalization helper 존재 |
| no-op provider | `backend/src/ocr/providers/noop.py` | 외부 호출 없이 empty text 반환 |
| OCR/image orchestration | `backend/src/services/supplement_image_analysis.py` | adapter 주입 시 OCR/parser 호출 가능 |
| parser service | `backend/src/services/supplement_parser.py` | OCR text normalize, HMAC hash, structured parse 저장 |
| parser schema | `backend/src/models/schemas/supplement_parser.py` | Pydantic structured output schema 존재 |
| local LLM parser | `backend/src/llm/ollama.py` | local-only Ollama Chat API + JSON schema validation |
| user confirmation | `backend/src/services/supplement_registration.py` | confirmed payload만 `UserSupplement`로 저장 |

현재 gap은 외부 OCR provider adapter와 upload route의 provider dependency 주입이다. OCR provider 없이 OCR text를 기존 preview에 attach하는 API는 구현되어 있으며, 기본 image upload runtime은 여전히 intake-only다.

## 구현 반영 상태

| 항목 | 상태 |
| --- | --- |
| `SupplementOCRTextParseRequest` schema | 구현됨 |
| `POST /api/v1/supplements/analyses/{analysis_id}/ocr-text` | 구현됨 |
| OCR text normalization + HMAC hash | 구현됨 |
| local Ollama structured parser 연결 | 구현됨 |
| parser error -> stable API error mapping | 구현됨 |
| OCR low confidence -> `low_confidence_fields` | 구현됨 |
| raw OCR text/model response 저장 금지 테스트 | 구현됨 |
| external OCR provider adapter | 미구현 |
| upload route OCR provider dependency | 미구현 |

## 브레인스토밍 결과

| 선택지 | 장점 | 리스크 | 판단 |
| --- | --- | --- | --- |
| A. 이미지 업로드 즉시 OCR+parse까지 한 번에 처리 | 모바일 UX가 단순하다 | OCR provider 미연결 상태에서 전체 flow가 막힌다 | 2단계 구현에 적합 |
| B. preview 생성 후 OCR text attach endpoint로 parse | OCR provider 없이도 text parsing과 confirmation을 먼저 완성 가능 | endpoint가 하나 늘어난다 | 1단계 권장 |
| C. text-only analysis row를 새로 만든다 | 이미지 없이 parser 테스트 가능 | `SupplementAnalysisRun`은 현재 image metadata가 필수라 migration 필요 | 지금은 비권장 |
| D. YOLO/multimodal 먼저 붙인다 | 미래 고도화 방향과 맞다 | P1 안정화 전 회귀 범위가 커진다 | 이번 범위 제외 |

권장 구현은 B -> A 순서다.

1. 먼저 기존 image preview row에 OCR text를 붙여 structured parse를 수행하는 route를 추가한다.
2. 그 다음 `POST /api/v1/supplements/analyze`에 실제 OCR adapter dependency를 연결해 업로드 한 번으로 OCR+parse까지 수행한다.
3. 사용자 확인 저장은 기존 `POST /api/v1/supplements`를 그대로 사용한다.

## 목표 플로우

### 1단계: OCR text attach 기반

```text
POST /api/v1/supplements/analyze
  multipart/form-data:
    image: UploadFile
    client_request_id: Form | null
  -> require ocr_image_processing consent
  -> validate image
  -> create SupplementAnalysisRun preview
  -> return requires_confirmation preview with low_confidence_fields=["label_text"]

POST /api/v1/supplements/analyses/{analysis_id}/ocr-text
  application/json:
    ocr_text
    ocr_provider
    ocr_confidence
  -> require supplement:write
  -> require ocr_image_processing consent
  -> normalize OCR text
  -> HMAC hash OCR text
  -> local Ollama structured parse
  -> update parsed_snapshot
  -> return requires_confirmation preview

POST /api/v1/supplements
  application/json:
    user-confirmed supplement payload
  -> require sensitive_health_analysis consent
  -> store only confirmed fields
  -> mark preview confirmed
```

### 2단계: upload one-shot OCR 기반

```text
POST /api/v1/supplements/analyze
  -> require ocr_image_processing consent
  -> validate image
  -> normalize image for OCR
  -> OCRAdapter.extract_text
  -> parse_supplement_analysis_ocr_text
  -> return requires_confirmation preview
```

2단계에서도 status는 자동 저장이 아니라 `requires_confirmation`을 유지한다.

## API 상세 설계

### 기존 유지: `POST /api/v1/supplements/analyze`

요청:

| 필드 | 위치 | 타입 | 설명 |
| --- | --- | --- | --- |
| `image` | multipart file | `UploadFile` | JPEG, PNG, WebP 라벨 이미지 |
| `client_request_id` | multipart form | `str | None` | idempotency key |

응답:

- `202 Accepted`
- `SupplementAnalysisPreview`
- status는 `requires_confirmation`

주의:

- multipart 요청에서는 JSON body를 섞지 않는다.
- OCR provider가 미주입이면 intake-only preview를 반환한다.
- OCR provider가 주입되어도 raw image는 저장하지 않는다.

### 신규 권장: `POST /api/v1/supplements/analyses/{analysis_id}/ocr-text`

목적:

- 외부 OCR adapter 구현 전에도 OCR text parsing과 user confirmation 경로를 완성한다.
- 테스트와 운영 디버깅에서 image OCR provider 장애와 parser 문제를 분리한다.

요청 schema 후보:

```json
{
  "ocr_text": "비타민 D 1000\n1정당 비타민 D 25 ug",
  "ocr_provider": "manual",
  "ocr_confidence": 0.91
}
```

응답:

- `200 OK`
- `SupplementAnalysisPreview`

에러:

| Status | code | 조건 |
| --- | --- | --- |
| `403` | `consent_required` | `ocr_image_processing` 동의 없음 |
| `404` | `supplement_analysis_not_found` | owner-visible preview 없음 |
| `409` | `supplement_analysis_not_parseable` | expired, confirmed, failed, hash conflict |
| `422` | `invalid_ocr_text` | blank, too long, confidence out of range, provider invalid |
| `502` | `parser_unavailable` | local Ollama 요청 실패 |
| `502` | `parser_schema_invalid` | structured output schema 검증 실패 |

### 기존 유지: `POST /api/v1/supplements`

이 endpoint는 user confirmation 단계다. parser output은 저장 후보일 뿐이며, 클라이언트는 사용자가 확인하거나 수정한 `UserSupplementCreate` payload만 보낸다.

## OCR Adapter 설계

### 계약

`OCRAdapter.extract_text(OCRImageInput) -> OCRResult`를 유지한다.

`OCRImageInput`:

- `image_bytes`: 검증 완료 후 OCR 전용으로만 사용
- `mime_type`: magic bytes로 확인된 MIME
- `width`, `height`: decoded image size
- `label_region`: 이번 범위에서는 항상 `None`; YOLO ROI는 후속 단계

`OCRResult`:

- `text`: OCR raw text. service layer에서 normalize하고 raw 저장 금지
- `provider`: `clova`, `google_vision`, `manual`, `noop` 같은 bounded label
- `confidence`: provider-level confidence. 없으면 `None`

### Preprocessor

`normalize_image_for_ocr`를 OCR adapter 호출 직전에 사용한다.

정책:

- RGB PNG로 재인코딩해 EXIF와 원본 메타데이터를 제거한다.
- `max_side_px`는 설정값으로 분리 가능하게 하되 초기값은 helper default인 `2048`을 유지한다.
- preprocessing 실패는 `422 invalid_image` 또는 adapter-level `ocr_failed`로 변환한다.
- OCR provider에는 원본 bytes가 아니라 normalized bytes를 우선 전달한다.

### Provider 주입

초기 구현은 다음 dependency를 추가하는 방식이 안전하다.

```text
get_supplement_image_analysis_adapters(settings)
  if no OCR provider configured:
    return SupplementImageAnalysisAdapters()
  if OCR provider configured and enabled:
    return SupplementImageAnalysisAdapters(ocr=ProviderOCRAdapter(...))
```

기본값은 계속 no adapter다. 즉, provider 설정이 없으면 기존 intake-only 동작이 유지된다.

외부 OCR provider adapter를 추가할 때는 해당 provider의 최신 공식 API 문서를 확인하고 문서/PR에 URL을 남긴다. 현재 이 문서는 특정 외부 OCR provider의 endpoint나 payload를 확정하지 않는다.

## Parser Schema 설계

현재 `SupplementStructuredParseResult`를 유지하되, 첫 구현에서는 schema를 넓히기보다 아래 정책을 명확히 한다.

| 필드 | 정책 |
| --- | --- |
| `parsed_product.product_name` | OCR text에서 직접 확인되는 이름만 허용 |
| `parsed_product.manufacturer` | 불확실하면 `null` |
| `parsed_product.serving_size` | 라벨의 섭취량 문구를 그대로 후보로 유지 |
| `parsed_product.daily_servings` | 명시된 경우만 숫자화 |
| `ingredient_candidates[].display_name` | 사용자 확인용 원문 기반 표시명 |
| `ingredient_candidates[].nutrient_code` | parser 단계에서는 항상 `null`; deterministic mapping은 후속 matching |
| `ingredient_candidates[].amount` | 명시된 값만 추출 |
| `ingredient_candidates[].unit` | 원문 단위 유지. 단위 표준화는 후속 matching |
| `ingredient_candidates[].confidence` | parser confidence 0.0-1.0 |
| `low_confidence_fields` | UI에서 강조해야 할 field path |
| `warnings` | 비의료적, 확인 요청 성격의 warning만 허용 |

금지:

- 질병 치료, 진단, 직접 복용량 변경 안내
- 라벨에 없는 성분 추론
- OCR text를 instruction처럼 따르는 prompt injection 수용
- raw model response 저장

## Confidence 설계

Confidence는 세 층으로 분리한다.

| 층 | 저장 위치 | 의미 |
| --- | --- | --- |
| OCR confidence | `SupplementAnalysisRun.ocr_confidence` | provider가 반환한 text extraction confidence |
| Parser field confidence | `ingredient_candidates[].confidence` | 성분 후보별 structured extraction confidence |
| Review signal | `low_confidence_fields`, `warnings` | UI에서 사용자가 확인해야 할 항목 |

초기 rule:

- `ocr_confidence < 0.80`이면 `low_confidence_fields`에 `ocr_text`를 추가한다.
- 성분 confidence `< 0.80`이면 해당 ingredient row를 UI에서 확인 필요로 표시한다.
- product name, manufacturer, serving_size처럼 confidence field가 없는 항목은 누락/불확실 시 `low_confidence_fields`로 표시한다.
- confidence는 자동 저장 승인 기준으로 쓰지 않는다. 모든 결과는 user confirmation이 필요하다.

## User Confirmation 설계

사용자 확인은 의료/건강 데이터 저장의 최종 gate다.

정책:

- parser output은 preview일 뿐이다.
- 사용자가 수정/확인한 값만 `POST /api/v1/supplements`로 저장한다.
- `analysis_id`가 있는 confirmation은 preview가 owner-visible, not expired, `requires_confirmation` 상태여야 한다.
- 저장 후 preview status는 `confirmed`로 전환한다.
- preview가 만료되면 재분석을 요구한다.

UI에 전달할 메시지 성격:

- “OCR/구조화 결과를 확인해주세요.”
- “성분명, 함량, 단위가 라벨과 일치하는지 확인해주세요.”

금지 메시지:

- “이 용량으로 복용하세요.”
- “복용량을 늘리세요/줄이세요.”
- “질병 치료에 효과가 있습니다.”

## Privacy And Security

| 항목 | 정책 |
| --- | --- |
| raw image | DB 저장 금지. object storage도 이번 범위 제외 |
| raw OCR text | DB 저장 금지. HMAC-SHA256 hash만 저장 |
| raw model response | DB 저장 금지. Pydantic 검증 후 sanitized snapshot만 저장 |
| consent | analyze와 OCR text attach는 `ocr_image_processing`, confirmation은 `sensitive_health_analysis` |
| audit | action, outcome, provider, confidence 존재 여부만 기록. raw text/value 금지 |
| external LLM | `ALLOW_EXTERNAL_LLM=false` 기본 유지. identifiable OCR text는 local Ollama만 사용 |
| external OCR | provider별 별도 승인 전까지 기본 미주입 |

## 상세 구현 플랜

### OT-S0: 기준선 고정

목표: 기존 intake/registration API가 깨지지 않는 상태에서 시작한다.

작업:

- `tests/integration/api/test_supplement_intake_api.py` 현행 202/403/413/415/409 경로 유지
- `tests/unit/services/test_supplement_parser.py` 현행 raw OCR text 미저장 검증 유지
- `tests/unit/llm/test_ollama_parser.py` local-only guard 유지
- OpenAPI contract에서 기존 `/api/v1/supplements/analyze` path 유지

완료 조건:

- 전체 backend test pass
- AI/vision/learning flags 기본 false 유지

### OT-S1: OCR text attach endpoint 추가

목표: OCR provider 없이도 text parsing과 confirmation preview를 완성한다.

작업:

- [x] `backend/src/models/schemas/supplement_parser.py`에 `SupplementOCRTextParseRequest` 추가
- [x] `backend/src/api/v1/supplements.py`에 `POST /analyses/{analysis_id}/ocr-text` 추가
- [x] `parse_supplement_analysis_ocr_text` 호출
- [x] service exception을 안정적인 HTTP error code로 mapping
- [x] audit event `supplement_ocr_text_parsed`, blocked variants 추가

완료 조건:

- [x] raw OCR text가 응답/DB/audit에 남지 않는다.
- [x] owner mismatch, expired preview, parser failure, invalid confidence가 테스트된다.
- [x] 반환 preview는 user confirmation을 요구한다.

### OT-S2: OCR adapter dependency 연결

목표: `POST /api/v1/supplements/analyze`가 OCR provider 주입 시 OCR+parse까지 실행할 수 있게 한다.

상세 구현 플랜은 `docs/Nutrition-docs/26-ot-s2-ocr-provider-adapter-implementation-plan.md`를 기준으로 한다.

작업:

- `get_supplement_image_analysis_adapters` dependency 추가
- 기본 dependency는 no adapter를 반환해 기존 동작 유지
- OCR provider 설정이 명시된 경우에만 adapter 주입
- `normalize_image_for_ocr`를 provider 호출 전 적용
- adapter 실패는 preview를 failed 처리할지, intake preview + warning으로 반환할지 결정

권장 실패 정책:

- provider timeout/장애는 `202 requires_confirmation` + warning으로 유지하지 않는다.
- OCR 실행을 명시적으로 요청한 환경에서는 `502 ocr_unavailable`로 실패시켜 운영자가 감지하게 한다.
- provider 미설정 환경은 기존 intake-only 성공이다.

완료 조건:

- no adapter 기본 호출은 기존 테스트와 동일하게 통과
- fake OCR adapter 주입 시 parsed snapshot이 채워진다.
- OCR adapter가 empty text를 반환하면 intake-only warning이 유지된다.

### OT-S3: Confidence normalization

목표: OCR/provider/parser confidence를 사용자 확인 UI에서 일관되게 사용한다.

작업:

- provider confidence `None` 또는 0.0-1.0만 허용
- parser ingredient confidence 0.0-1.0 validation 유지
- OCR confidence threshold에 따라 `low_confidence_fields` 보강
- confidence threshold는 상수 또는 Settings로 관리하되 기본값 문서화

완료 조건:

- confidence out-of-range는 422 또는 adapter error로 실패
- low-confidence OCR result가 UI review signal로 드러난다.

### OT-S4: User confirmation contract 강화

목표: parser preview와 최종 저장 payload의 경계를 명확히 한다.

작업:

- `UserSupplementCreate` 예시에 OCR preview에서 수정된 값을 confirmation으로 보내는 예시 추가
- confirmation 시 `analysis_id` preview가 confirmed로 전환되는 테스트 유지/보강
- direct dose-change advice 금지 문구가 OpenAPI examples에 없는지 유지

완료 조건:

- 사용자가 확인한 값만 `UserSupplement`와 `UserSupplementIngredient`에 저장된다.
- preview가 없거나 만료되면 저장이 차단된다.

### OT-S5: 문서와 CI 보정

목표: OCR/Text flow가 P1 안정화 gate 위에 올라가게 한다.

작업:

- `docs/Nutrition-docs/dev-guides/07-ocr-pipeline.md`에 text attach route와 adapter injection 상태 반영
- `docs/Nutrition-docs/dev-guides/08-llm-supplement-parsing.md`에 endpoint 연결 상태 반영
- `docs/Nutrition-docs/dev-guides/09-supplement-registration-api.md`에 confirmation flow 반영
- backend CI에서 기존 black/ruff/mypy/pytest/OpenAPI smoke 유지

완료 조건:

- docs와 code에서 `OllamaAdapter`, `OCRPipeline`, provider 구현 완료 같은 잔여 표현이 생기지 않는다.

## 테스트 플랜

| 테스트 파일 | 추가/보강 항목 |
| --- | --- |
| `tests/integration/api/test_supplement_intake_api.py` | upload route 기본 intake-only 유지, fake OCR adapter path |
| `tests/integration/api/test_supplement_ocr_text_api.py` | 신규 OCR text attach endpoint의 200/403/404/409/422/502 |
| `tests/unit/services/test_supplement_parser.py` | low OCR confidence, provider normalization, parser failure mapping |
| `tests/unit/services/test_supplement_image_analysis.py` | preprocessor + OCR adapter + parser orchestration |
| `tests/unit/models/test_supplement_parser_schema.py` | schema forbids extra fields, confidence bounds |
| `tests/unit/llm/test_ollama_parser.py` | structured output schema, local-only guard, prompt injection sample |

필수 검증 명령:

```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/black --check src tests alembic
.venv/bin/ruff check src tests alembic
.venv/bin/mypy src tests --strict
.venv/bin/python -m pytest -o addopts=''
.venv/bin/python -c "from src.main import create_app; schema=create_app().openapi(); assert '/api/v1/supplements/analyze' in schema['paths']"
```

## 구현 순서 제안

1. `test(api): cover OCR text attach preview parsing`
   - 이유: OCR provider 없이 parser와 confirmation 경계를 먼저 고정한다.
2. `feat(api): add supplement OCR text parse endpoint`
   - 이유: image analysis 이전에 OCR/text 기반 구조화 분석을 사용할 수 있게 한다.
3. `test(ocr): cover adapter-driven upload parsing`
   - 이유: FastAPI upload flow와 OCR adapter 주입의 회귀를 막는다.
4. `feat(ocr): wire OCR adapter dependency for supplement analysis`
   - 이유: provider가 준비된 환경에서 upload 한 번으로 OCR+parse preview를 만들기 위함.
5. `docs(ocr): document OCR text confirmation flow`
   - 이유: 구현된 범위와 아직 제외된 YOLO/multimodal/learning 범위를 명확히 하기 위함.

## 이번 범위에서 제외

- YOLO label detection 실제 inference
- Ollama multimodal image-to-text
- external OCR provider 구체 payload 확정
- raw image object storage
- OCR text cache
- pgvector/embedding upload
- parser 결과 자동 복용 조언

## 완료 정의

OCR/Text 기반 보충제 분석 단계는 아래 조건을 만족하면 완료로 본다.

- 이미지 upload preview 생성이 기존과 동일하게 동작한다.
- OCR text attach endpoint가 structured preview를 생성한다.
- OCR adapter가 주입된 경우 upload route에서 OCR+parse가 실행된다.
- raw OCR text와 raw model response가 저장되지 않는다.
- 모든 structured result는 user confirmation 전에는 저장된 영양제 기록으로 승격되지 않는다.
- 전체 backend test, strict mypy, lint, format, OpenAPI smoke가 통과한다.
