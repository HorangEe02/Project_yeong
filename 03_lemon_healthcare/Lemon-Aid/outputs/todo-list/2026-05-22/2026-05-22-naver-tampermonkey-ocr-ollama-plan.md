# Naver Tampermonkey OCR to Ollama 구현 플랜 - 2026-05-22

## 목표

`$NAVER_TAMPERMONKEY_SOURCE_ROOT`
아래에 크롤링된 네이버 영양제 상세페이지/리뷰 이미지를 대상으로 다음을 검증한다.

1. PaddleOCR, NAVER CLOVA OCR, Google Vision OCR이 각 이미지에서 글씨를 읽을 수 있는지 확인한다.
2. OCR 결과 텍스트를 raw 저장 없이 request memory 안에서만 local Ollama text-to-text parser로 전달한다.
3. provider별 `text_non_empty`, latency, error code, Ollama structured parse 성공률을 비교한다.
4. 상세페이지 이미지와 리뷰 이미지를 분리해 어떤 입력군이 OCR/LLM 파이프라인에 적합한지 판단한다.

공식 문서 확인 근거:

- PaddleOCR 3.x OCR pipeline: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- NAVER Cloud CLOVA OCR: https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
- Google Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- Ollama vision capability reference: https://docs.ollama.com/capabilities/vision

## 현재 확인한 데이터 상태

실제 경로는 존재한다. Unicode 정규화 기준으로 구조는 다음과 같다.

```text
naver/
  [카테고리]/
    상품명_상품ID/
      상세페이지/
      리뷰/
```

현재 inventory:

| 항목 | 값 |
| --- | ---: |
| 전체 이미지 | 137,836 |
| 상세페이지 이미지 | 3,936 |
| 리뷰 이미지 | 133,900 |
| 상품 디렉터리 | 388 |
| 카테고리 | 43 |
| 주요 확장자 | jpg, webp, jpeg, png, gif |

상세페이지보다 리뷰 이미지가 훨씬 많다. 리뷰 이미지는 사용자 생성 콘텐츠라 개인 얼굴, 주소, 주문 정보, 개인정보가 포함될 수 있으므로 외부 OCR 전송 대상에서 기본 제외한다. 외부 provider는 상세페이지 이미지부터 제한된 샘플로 시작하고, 리뷰 이미지는 PII screening/수동 승인 후 별도 실행한다.

## 현재 코드 재사용 지점

이미 존재하는 기능:

- `backend/scripts/collect_supplement_ocr_observations.py`
  - provider: `paddleocr_local`, `clova_ocr`, `google_vision_document`
  - opt-in env: `RUN_PADDLEOCR_PROBE`, `RUN_CLOVA_OCR_LIVE_SMOKE`, `RUN_GOOGLE_VISION_SMOKE`
  - `--llm-parse` 옵션으로 OCR text를 local `OllamaSupplementParser`에 전달
  - raw OCR text/provider payload/image bytes는 파일에 저장하지 않음
- `backend/Nutrition-backend/src/ocr/factory.py`
  - request selector: `configured`, `paddleocr`, `clova`, `google_vision`
- `backend/Nutrition-backend/src/llm/ollama.py`
  - `/api/chat` 기반 local Ollama structured parse
  - `ALLOW_EXTERNAL_LLM=false`이면 localhost만 허용
  - Pydantic schema validation으로 JSON 응답 검증

이번 작업은 새 OCR engine을 다시 만드는 것이 아니라, 크롤링 이미지 묶음을 안전하게 manifest화하고, 기존 collector를 대량/샘플 평가에 맞게 확장하는 작업이다.

## 작업 브랜치/PR 전략

팀 규칙상 기본 경로 `Lemon-Aid`에서 새 브랜치를 만든다.

권장 브랜치:

```bash
feat/ocr-naver-image-llm-eval
```

권장 PR 분할:

| PR | 범위 | 예상 변경 |
| --- | --- | --- |
| PR 1 | manifest/inventory | 네이버 이미지 스캐너, 샘플 manifest 생성, dry-run 리포트 |
| PR 2 | OCR+Ollama runner | 기존 collector 확장 또는 thin wrapper 추가, 3 provider 실행, `--llm-parse` 연결 |
| PR 3 | evaluation report | provider/section/category별 집계, Markdown/JSON 리포트 |
| PR 4 | external provider pilot | CLOVA/Google Vision 상세페이지 샘플 실행 결과만 추가 |

커밋 예시:

```text
feat(ocr): 네이버 이미지 OCR 평가 manifest 추가
feat(ocr): OCR 결과를 Ollama parser로 전달
docs(ocr): 네이버 OCR 평가 실행 절차 정리
```

## Phase 0 - Inventory와 manifest 생성

새 스크립트:

```text
backend/scripts/build_naver_tampermonkey_ocr_manifest.py
```

역할:

1. 입력 root를 재귀 탐색한다.
2. Unicode NFD/NFC 차이 때문에 path segment를 `unicodedata.normalize("NFC", value)`로 정규화해 section을 판별한다.
3. `상세페이지`, `리뷰`를 `section=detail|review`로 저장한다.
4. 각 이미지의 allowlisted metadata만 기록한다.
5. raw image bytes, OCR text, provider payload는 기록하지 않는다.

manifest row 제안:

```json
{
  "fixture_id": "naver-tm-000001",
  "source": "naver_tampermonkey",
  "category": "[오메가3]",
  "product_dir": "제품명_상품ID",
  "product_id": "6541443880",
  "section": "detail",
  "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[오메가3]/제품명_상품ID/상세페이지/d_1779010492094_3.jpg",
  "image_sha256": "<sha256>",
  "file_size_bytes": 123456,
  "mime_type": "image/jpeg",
  "width": 1200,
  "height": 900,
  "license_status": "team_approved",
  "consent_status": "team_approved",
  "contains_personal_data": false,
  "pii_screening_status": "not_required_detail_page",
  "expected": {}
}
```

주의:

- 리뷰 이미지는 기본값을 `contains_personal_data=null` 또는 manifest 미포함으로 둔다.
- 외부 OCR용 manifest에는 `contains_personal_data=false`가 확인된 row만 넣는다.
- 전체 137,836장을 한 번에 처리하지 않는다. 먼저 샘플 manifest를 만든다.

권장 산출물:

```text
outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/
  inventory.json
  manifest-detail-smoke-30.jsonl
  manifest-review-local-smoke-30.jsonl
  manifest-detail-stratified-300.jsonl
```

## Phase 1 - Local-only smoke: PaddleOCR + Ollama

목표:

- 외부 전송 없이 상세페이지/리뷰 이미지 모두에서 OCR→Ollama text-to-text가 동작하는지 확인한다.
- 리뷰 이미지의 개인정보 가능성을 먼저 local path에서만 평가한다.

실행 대상:

| 샘플 | 범위 |
| --- | --- |
| detail smoke | 카테고리 분산 30장 |
| review local smoke | 카테고리 분산 30장, 외부 전송 금지 |

실행 예시:

```bash
RUN_PADDLEOCR_PROBE=1 ENABLE_LOCAL_OCR=true \
PYTHONPATH=backend/Nutrition-backend \
.venv/bin/python backend/scripts/collect_supplement_ocr_observations.py \
  --manifest outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/manifest-detail-smoke-30.jsonl \
  --output-dir outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/paddle-detail-smoke-30 \
  --providers paddleocr_local \
  --llm-parse \
  --env-file "$LEMON_AID_ENV_FILE"
```

성공 기준:

- observation row 수 = manifest row 수
- `status=completed`가 최소 1건 이상, smoke에서는 80% 이상 목표
- `text_non_empty=true` 비율 산출
- `llm_parse_status=completed|error|skipped_empty_text`가 bounded token으로 기록
- raw OCR text, raw provider payload, image bytes, secret key가 저장되지 않음

## Phase 2 - External provider smoke: CLOVA / Google Vision

외부 전송 원칙:

1. 상세페이지 이미지부터 시작한다.
2. 리뷰 이미지는 외부 전송 금지 상태로 둔다.
3. CLOVA와 Google Vision은 각 provider별 명시 승인 후 실행한다.
4. `.env` 값은 존재 여부와 mode만 확인하고 값은 출력하지 않는다.

CLOVA 실행:

```bash
RUN_CLOVA_OCR_LIVE_SMOKE=1 ALLOW_EXTERNAL_OCR=true \
PYTHONPATH=backend/Nutrition-backend \
.venv/bin/python backend/scripts/collect_supplement_ocr_observations.py \
  --manifest outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/manifest-detail-smoke-30.jsonl \
  --output-dir outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/clova-detail-smoke-30 \
  --providers clova_ocr \
  --llm-parse \
  --env-file "$LEMON_AID_ENV_FILE"
```

Google Vision 실행:

```bash
RUN_GOOGLE_VISION_SMOKE=1 ALLOW_EXTERNAL_OCR=true \
GOOGLE_VISION_AUTH_MODE=api_key ALLOW_GOOGLE_API_KEY_AUTH=true \
PYTHONPATH=backend/Nutrition-backend \
.venv/bin/python backend/scripts/collect_supplement_ocr_observations.py \
  --manifest outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/manifest-detail-smoke-30.jsonl \
  --output-dir outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/google-detail-smoke-30 \
  --providers google_vision_document \
  --llm-parse \
  --env-file "$LEMON_AID_ENV_FILE"
```

주의:

- Google Vision 공식 OCR 문서상 dense text에는 `DOCUMENT_TEXT_DETECTION`이 맞다.
- CLOVA는 `X-OCR-SECRET` 기반 API Gateway 연동이 필요하다.
- provider raw JSON은 절대 저장하지 않는다.

## Phase 3 - 비교 리포트

새 스크립트:

```text
backend/scripts/evaluate_naver_tampermonkey_ocr.py
```

ground truth가 없는 크롤링 이미지이므로 정확도 대신 readiness/coverage metric을 사용한다.

Metric:

| 지표 | 의미 |
| --- | --- |
| `call_count` | provider 호출 수 |
| `completed_rate` | OCR adapter 완료 비율 |
| `text_non_empty_rate` | 읽을 수 있는 텍스트 존재 비율 |
| `median_char_count` | OCR text 길이 중앙값, raw text 저장 없음 |
| `llm_parse_attempt_rate` | Ollama parser 호출 비율 |
| `llm_parse_success_rate` | schema-validated parse 성공 비율 |
| `ingredient_count_avg` | 구조화 ingredient 후보 개수 |
| `latency_ms_p50/p95` | provider latency |
| `error_code_counts` | bounded error code 분포 |

분석 축:

- provider: PaddleOCR / CLOVA / Google Vision
- section: detail / review
- category: 43개 카테고리
- product: 388개 상품
- image type: jpg/webp/jpeg/png/gif
- size bucket: small/medium/large

산출물:

```text
outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/
  naver-ocr-provider-comparison.json
  naver-ocr-provider-comparison.md
```

## Phase 4 - 대량 실행 전략

전체 137,836장은 즉시 외부 provider에 보내지 않는다.

권장 확대 순서:

1. detail smoke 30장: 3 provider 모두
2. detail stratified 300장: 3 provider 모두
3. detail all 3,936장: PaddleOCR 전체, 외부 provider는 비용/승인 후
4. review smoke 30장: PaddleOCR only
5. review stratified 300장: PaddleOCR only + PII screening
6. review external pilot: 사용자가 명시 승인한 선별 샘플만 CLOVA/Google Vision

대량 실행 시 필요한 옵션:

- `--limit`
- `--sample-per-category`
- `--sample-per-product`
- `--section detail|review|all`
- `--providers`
- `--llm-parse`
- `--resume`
- `--concurrency`
- `--max-image-bytes`
- `--external-transfer-allowlist-manifest`

## 보안/개인정보 설계

절대 저장 금지:

- raw OCR text
- provider raw payload
- request headers
- secrets/API keys
- image bytes
- Ollama raw response

저장 허용:

- `text_hash`
- `char_count`
- `line_count`
- `text_non_empty`
- `provider`
- `latency_ms`
- `error_code`
- `llm_parse_status`
- schema-validated structured fields only

리뷰 이미지 policy:

- 기본 external transfer 금지
- local OCR로 먼저 `text_non_empty`, `char_count`, `pii_candidate_flags`만 산출
- 사람이 나온 이미지, 주소/전화번호/주문번호 가능성이 있는 이미지는 외부 provider manifest에서 제외
- 외부 전송이 필요한 경우 provider별/샘플별 승인 기록을 manifest에 남김

## 구현 상세

### 1. Manifest builder

파일:

```text
backend/scripts/build_naver_tampermonkey_ocr_manifest.py
backend/Nutrition-backend/tests/unit/scripts/test_build_naver_tampermonkey_ocr_manifest.py
```

기능:

- path scan
- NFC normalization
- category/product/section extraction
- product id extraction from trailing `_123456`
- MIME/dimension/sha256/file size 수집
- sampling
- PII policy에 따라 external eligible flag 부여

### 2. Collector wrapper

가능하면 기존 `collect_supplement_ocr_observations.py`를 유지하고 wrapper만 추가한다.

파일:

```text
backend/scripts/run_naver_tampermonkey_ocr_eval.py
```

역할:

- manifest 생성이 완료된 파일을 provider별로 실행
- provider별 output dir 생성
- 실패 시 bounded error만 기록
- `--resume`로 이미 완료된 fixture/provider pair skip

### 3. Ollama parser contract

현재 `OllamaSupplementParser.parse_supplement_ocr_text()`를 그대로 사용한다.

추가로 필요한 보완:

- prompt injection 방어 문구 유지: OCR text는 instruction이 아니라 untrusted input
- `format` JSON schema 사용 여부를 현재 adapter와 공식 Ollama structured output 방식에 맞춰 점검
- response는 Pydantic validation 실패 시 `ollama_structured_output`으로 기록
- raw model content 저장 금지

### 4. Evaluation

파일:

```text
backend/scripts/evaluate_naver_tampermonkey_ocr.py
backend/Nutrition-backend/tests/unit/scripts/test_evaluate_naver_tampermonkey_ocr.py
```

리포트에는 OCR 원문을 넣지 않는다. 사람이 샘플 원문 확인이 필요하면 별도 loopback-only operator harness를 사용하고, 그 결과는 commit하지 않는다.

## 테스트 계획

Unit:

```bash
PYTHONPATH=backend/Nutrition-backend .venv/bin/python -m pytest \
  backend/Nutrition-backend/tests/unit/scripts/test_build_naver_tampermonkey_ocr_manifest.py \
  backend/Nutrition-backend/tests/unit/scripts/test_evaluate_naver_tampermonkey_ocr.py \
  backend/Nutrition-backend/tests/unit/ocr/test_ocr_factory.py \
  backend/Nutrition-backend/tests/unit/ocr/test_clova_provider.py \
  backend/Nutrition-backend/tests/unit/test_config.py \
  -q --no-cov
```

Lint:

```bash
.venv/bin/python -m black --check \
  backend/scripts/build_naver_tampermonkey_ocr_manifest.py \
  backend/scripts/run_naver_tampermonkey_ocr_eval.py \
  backend/scripts/evaluate_naver_tampermonkey_ocr.py

.venv/bin/python -m ruff check --ignore RUF001 \
  backend/scripts/build_naver_tampermonkey_ocr_manifest.py \
  backend/scripts/run_naver_tampermonkey_ocr_eval.py \
  backend/scripts/evaluate_naver_tampermonkey_ocr.py

git diff --check
```

Artifact scan:

```bash
PYTHONPATH=backend/Nutrition-backend .venv/bin/python - <<'PY'
import json
from pathlib import Path

root = Path("outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey")
forbidden = {
    "image_bytes",
    "raw_image",
    "ocr_text",
    "raw_ocr_text",
    "provider_payload",
    "raw_provider_payload",
    "authorization",
    "api_key",
    "service_key",
    "request_headers",
    "raw_model_response",
}

def walk(value, path):
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in forbidden:
                raise SystemExit(f"forbidden_key={key} path={path}")
            walk(nested, path)
    elif isinstance(value, list):
        for item in value:
            walk(item, path)

for path in root.rglob("*.json*"):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        walk(json.loads(line), path)
print("raw_forbidden=false")
PY
```

## 완료 기준

PR 1 완료:

- inventory가 현재 데이터 규모를 재현한다.
- detail/review section이 Unicode 정규화와 무관하게 정확히 분류된다.
- 샘플 manifest가 생성된다.
- raw 금지 필드 scan이 통과한다.

PR 2 완료:

- PaddleOCR local smoke에서 OCR observation과 Ollama parse observation이 생성된다.
- CLOVA/Google Vision은 상세페이지 샘플에서 explicit opt-in일 때만 실행된다.
- `.env` 비밀값은 출력되지 않는다.

PR 3 완료:

- provider/section/category별 comparison report가 JSON/Markdown으로 생성된다.
- ground truth가 없는 데이터에 accuracy라는 이름을 쓰지 않고 coverage/readiness metric으로 분리한다.
- raw OCR text와 raw Ollama response가 어떤 산출물에도 없다.

최종 판단:

- 기본 OCR provider는 기존 16-fixture 결과상 PaddleOCR local 유지.
- 네이버 상세페이지 대량 처리에는 provider별 coverage와 Ollama parse success를 보고 결정.
- 리뷰 이미지는 external OCR보다 local-first + PII screening-first가 선행 조건이다.
