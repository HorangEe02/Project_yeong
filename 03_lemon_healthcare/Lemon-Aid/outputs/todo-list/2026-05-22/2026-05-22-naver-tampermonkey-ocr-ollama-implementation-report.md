# Naver Tampermonkey OCR to Ollama 구현 결과 - 2026-05-22

## 구현 범위

계획서 `2026-05-22-naver-tampermonkey-ocr-ollama-plan.md` 기준으로 다음을 구현했다.

- `backend/scripts/build_naver_tampermonkey_ocr_manifest.py`
  - 네이버 Tampermonkey 크롤링 이미지 tree scan
  - Unicode NFC 정규화 기반 `상세페이지`/`리뷰` 분류
  - 카테고리/상품/상품ID/image metadata/sha256 manifest 생성
  - 리뷰 이미지는 기본 external transfer 차단
  - 리뷰 기본 manifest는 `contains_personal_data=null`, `pending_local_screening`으로 두고 local PaddleOCR PII screening 전용으로 생성
- `backend/scripts/run_naver_tampermonkey_ocr_eval.py`
  - 기존 `collect_supplement_ocr_observations.py`를 provider별로 실행하는 wrapper
  - `paddleocr`, `clova`, `google_vision` alias 지원
  - 외부 provider는 `--allow-external-providers` 없이는 실행 불가
  - 리뷰 이미지는 `--allow-review-external` 없이는 외부 provider 실행 불가
  - `--resume`으로 완료된 provider observation을 재사용해 중복 외부 전송 방지
- `backend/scripts/evaluate_naver_tampermonkey_ocr.py`
  - ground truth 없는 crawl 이미지용 coverage/readiness metric 집계
  - provider/section/category/product/MIME/size bucket별 `text_non_empty`, latency, Ollama parse 성공률 집계
  - review local-only 산출물의 `pii_candidate_flags` 집계
  - raw OCR text/provider payload/model response 저장 차단
- `backend/scripts/collect_supplement_ocr_observations.py`
  - 현재 `SupplementStructuredParseResult` 스키마의 `ingredient_candidates`를 redacted observation으로 변환하도록 보완
  - `pending_local_screening` review row는 PaddleOCR local-only만 허용하고 LLM handoff는 `skipped_pii_screening_required`로 skip
  - local OCR text에서 이메일/전화/주문번호/주소 후보를 bounded flag로만 기록
  - raw OCR text와 raw model response는 계속 저장하지 않음

공식 문서 확인:

- PaddleOCR 3.x OCR pipeline: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- NAVER Cloud CLOVA OCR: https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
- NAVER Cloud CLOVA General OCR: https://api.ncloud-docs.com/docs/en/ai-application-service-ocr-ocr
- Google Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- Google Cloud Vision `images:annotate` REST: https://docs.cloud.google.com/vision/docs/reference/rest/v1/images/annotate
- Google Cloud Vision 인증/API key: https://docs.cloud.google.com/vision/product-search/docs/auth
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- Ollama vision/API image input: https://docs.ollama.com/capabilities/vision

## 실제 데이터 산출물

생성 위치:

```text
outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/
```

생성된 파일:

- `inventory.json`
- `manifest-detail-smoke-30.jsonl`
- `manifest-detail-smoke-1.jsonl`
- `manifest-review-local-smoke-30.jsonl`
- `inventory-review-local.json`
- `paddle-detail-smoke-1/supplement-ocr-observations.jsonl`
- `paddle-detail-smoke-1-report/naver-ocr-provider-comparison.json`
- `paddle-detail-smoke-1-report/naver-ocr-provider-comparison.md`
- `runner-paddle-detail-smoke-1-gemma4-v2/paddleocr-observations/supplement-ocr-observations.jsonl`
- `runner-paddle-detail-smoke-1-gemma4-v2/naver-ocr-provider-comparison.json`
- `runner-paddle-detail-smoke-1-gemma4-v2/naver-ocr-provider-comparison.md`
- `runner-paddle-detail-smoke-30-gemma4/paddleocr-observations/supplement-ocr-observations.jsonl`
- `runner-paddle-detail-smoke-30-gemma4/naver-ocr-provider-comparison.json`
- `runner-paddle-detail-smoke-30-gemma4/naver-ocr-provider-comparison.md`
- `runner-paddle-review-local-smoke-30/paddleocr-observations/supplement-ocr-observations.jsonl`
- `runner-paddle-review-local-smoke-30/naver-ocr-provider-comparison.json`
- `runner-paddle-review-local-smoke-30/naver-ocr-provider-comparison.md`
- `runner-clova-detail-smoke-30-gemma4/clova-observations/supplement-ocr-observations.jsonl`
- `runner-clova-detail-smoke-30-gemma4/naver-ocr-provider-comparison.json`
- `runner-clova-detail-smoke-30-gemma4/naver-ocr-provider-comparison.md`
- `runner-google-detail-smoke-30-gemma4/google_vision-observations/supplement-ocr-observations.jsonl`
- `runner-google-detail-smoke-30-gemma4/naver-ocr-provider-comparison.json`
- `runner-google-detail-smoke-30-gemma4/naver-ocr-provider-comparison.md`
- `runner-detail-smoke-30-provider-comparison/naver-ocr-provider-comparison.json`
- `runner-detail-smoke-30-provider-comparison/naver-ocr-provider-comparison.md`

Inventory 결과:

| 항목 | 값 |
| --- | ---: |
| files_seen | 137,940 |
| candidate_count | 130,303 |
| detail candidates | 3,777 |
| review candidates | 126,526 |
| category_count | 43 |
| product_dir_count | 388 |

초기 수동 inventory에서 확인한 전체 이미지 수와 차이가 나는 이유는 이번 manifest builder가 OCR 처리 대상으로 `image/jpeg`, `image/png`, `image/webp`만 허용하고, GIF/해석 실패/제한 조건 미달 이미지를 제외하기 때문이다.

## Ollama 모델 경로

사용자 환경의 Ollama 모델은 기본 `~/.ollama`가 아니라 현재 EX400U 외장 경로에 있다.

```text
/Volumes/Corsair EX400U Media/.ollama/models
```

따라서 이번 검증은 별도 포트의 임시 Ollama 서버를 다음 환경으로 실행했다.

```bash
OLLAMA_MODELS="/Volumes/Corsair EX400U Media/.ollama/models" \
OLLAMA_HOST=127.0.0.1:11435 \
ollama serve
```

확인된 모델 중 이번 smoke에는 `gemma4:e4b`를 사용했다. 이 런타임은 localhost만 사용하며 `ALLOW_EXTERNAL_LLM=false`를 유지했다.

## 실제 Smoke 결과

외부 provider 전송 없이 PaddleOCR local과 외장 Ollama 저장소의 `gemma4:e4b`로 상세페이지 30장을 실행했다.

| 지표 | 값 |
| --- | ---: |
| fixture_count | 30 |
| observation_count | 30 |
| provider | `paddleocr_local` |
| status | `completed` 26 / `error` 4 |
| completed_rate | 0.8667 |
| text_non_empty_rate | 0.8667 |
| median_char_count | 187.5 |
| llm_parse_success_rate | 1.0 |
| ingredient_count_avg | 2.4615 |
| latency_ms_p50 | 2352.0 |
| latency_ms_p95 | 5142.0 |
| error_code_counts | `{"ocrerror": 4}` |
| raw_ocr_text_stored | `false` |
| raw_provider_payload_stored | `false` |
| raw_model_response_stored | `false` |

1장 smoke에서 처음 발견된 collector 스키마 매핑 오류는 `parse_result.ingredients`가 아니라 현재 스키마의 `parse_result.ingredient_candidates`를 사용하도록 수정했다. 이후 1장 재실행과 30장 smoke 모두에서 OCR 성공 row의 `llm_parse_status=completed`가 확인됐다.

리뷰 이미지는 개인정보 가능성이 있으므로 외부 전송 없이 PaddleOCR local-only로 30장을 실행했다. `--llm-parse`를 켰지만 `pending_local_screening` row는 LLM handoff 전에 skip하도록 처리했다.

| 지표 | 값 |
| --- | ---: |
| fixture_count | 30 |
| observation_count | 30 |
| provider | `paddleocr_local` |
| status | `completed` 14 / `error` 16 |
| completed_rate | 0.4667 |
| text_non_empty_rate | 0.4667 |
| median_char_count | 227.0 |
| llm_parse_attempt_count | 0 |
| llm_parse_success_rate | `null` |
| pii_candidate_flag_counts | `{"address_candidate": 1}` |
| latency_ms_p50 | 6844.5 |
| latency_ms_p95 | 10186.0 |
| error_code_counts | `{"ocrerror": 16}` |
| raw_ocr_text_stored | `false` |
| raw_provider_payload_stored | `false` |
| raw_model_response_stored | `false` |

사용자가 네이버 상세페이지 30개 fixture의 외부 OCR 전송을 승인한 뒤 CLOVA/Google Vision도 같은 manifest로 실행했다. 리뷰 이미지는 외부 전송하지 않았다.

통합 비교 결과:

| Provider | Calls | Completed | Text non-empty | LLM attempts | LLM success | Median chars | p50 latency ms | p95 latency ms | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `clova_ocr` | 30 | 1.0 | 1.0 | 30 | 1.0 | 181.0 | 1467.0 | 2193.0 | `{}` |
| `paddleocr_local` | 30 | 0.8667 | 0.8667 | 26 | 1.0 | 187.5 | 2352.0 | 5142.0 | `{"ocrerror": 4}` |
| `google_vision_document` | 30 | 0.0 | 0.0 | 0 | `null` | `null` | `null` | `null` | `{"ocr_http_status_401": 30}` |

Google Vision은 live smoke에서 30건 모두 HTTP 401로 실패했다. 중간에 API key 전달 방식을 바꿔 보는 local experiment가 있었지만, 최종 커밋 코드에서는 Google Cloud API key 일반 문서가 권장하는 `x-goog-api-key` header 방식을 유지했다. 따라서 현재 원인은 전송 방식보다 API key 권한, Vision API 활성화, 결제/API 제한, 또는 key restriction 설정 문제로 보는 것이 맞다. raw provider response는 저장하지 않았고, failure는 bounded error code만 남겼다. 공식 Google Vision REST 문서상 `images:annotate`는 OAuth scope `https://www.googleapis.com/auth/cloud-vision`도 명시하므로, 다음 재시도는 server-side OAuth/ADC 경로와 API-key restriction 상태를 분리해서 검증한다.

중복 외부 호출 방지를 위해 runner에 `--resume`을 추가했다. 기존 `runner-google-detail-smoke-30-gemma4/google_vision-observations/supplement-ocr-observations.jsonl`은 manifest 30개 fixture 전체에 대해 같은 provider의 terminal status를 가지고 있으므로, `--resume --skip-evaluate` 확인 시 `executed_runs=[]`, `resumed_runs=[google_vision]`로 재사용됐다.

## 검증

통과한 명령:

```bash
PYTHONPATH=backend/Nutrition-backend:backend /private/tmp/lemon-p1-quality-venv/bin/python -m pytest \
  backend/Nutrition-backend/tests/unit/scripts/test_build_naver_tampermonkey_ocr_manifest.py \
  backend/Nutrition-backend/tests/unit/scripts/test_evaluate_naver_tampermonkey_ocr.py \
  backend/Nutrition-backend/tests/unit/scripts/test_run_naver_tampermonkey_ocr_eval.py \
  backend/Nutrition-backend/tests/unit/scripts/test_collect_supplement_ocr_observations.py \
  backend/Nutrition-backend/tests/unit/llm/test_ollama_parser.py \
  -q --no-cov
```

결과: `37 passed in 0.75s`

```bash
/private/tmp/lemon-p1-quality-venv/bin/python -m black --check <new scripts and tests>
/private/tmp/lemon-p1-quality-venv/bin/python -m ruff check --ignore RUF001 <new scripts and tests>
git diff --check
```

결과: 모두 통과.

Artifact raw field scan:

- `inventory.json`: pass
- `manifest-detail-smoke-30.jsonl`: pass
- `manifest-detail-smoke-1.jsonl`: pass
- `paddle-detail-smoke-1/supplement-ocr-observations.jsonl`: pass
- `paddle-detail-smoke-1-report/naver-ocr-provider-comparison.json`: pass
- `runner-paddle-detail-smoke-1-gemma4-v2/*`: pass
- `runner-paddle-detail-smoke-30-gemma4/*`: pass
- `manifest-review-local-smoke-30.jsonl`: pass
- `inventory-review-local.json`: pass
- `runner-paddle-review-local-smoke-30/*`: pass
- `runner-clova-detail-smoke-30-gemma4/*`: pass
- `runner-google-detail-smoke-30-gemma4/*`: pass
- `runner-detail-smoke-30-provider-comparison/*`: pass

최신 전체 JSON/JSONL scan 결과:

```text
raw_forbidden=false checked_json_values=10994 files=18
```

## 남은 조건

- CLOVA live smoke는 상세페이지 30장 기준 완료했다.
- Google Vision live smoke는 상세페이지 30장 기준 실행했지만 `ocr_http_status_401`로 모두 실패했다. API key 권한/결제/API enablement 또는 ADC project 설정 확인이 필요하다.
- 리뷰 이미지는 local-only smoke와 bounded PII flag 산출까지 완료했지만, 외부 전송은 PII candidate 검토 후 별도 승인 필요하다.
- 상세페이지 30장 기준 PaddleOCR 자체 실패 4건(`ocrerror`), 리뷰 30장 기준 16건(`ocrerror`)의 이미지 특성 분석이 필요하다.

권장 다음 명령 예시:

```bash
OLLAMA_MODELS="/Volumes/Corsair EX400U Media/.ollama/models" \
OLLAMA_HOST=127.0.0.1:11435 \
ollama serve

OLLAMA_BASE_URL=http://127.0.0.1:11435 \
OLLAMA_MODEL=gemma4:e4b \
LLM_PROVIDER=ollama \
ALLOW_EXTERNAL_LLM=false \
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
MPLCONFIGDIR=/private/tmp/lemon-mpl-cache \
PYTHONPATH=backend/Nutrition-backend \
/private/tmp/lemon-p1-quality-venv/bin/python backend/scripts/run_naver_tampermonkey_ocr_eval.py \
  --manifest outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/manifest-detail-smoke-30.jsonl \
  --output-root outputs/generated/ocr-eval/2026-05-22-naver-tampermonkey/runner-paddle-detail-smoke-30-gemma4 \
  --providers paddleocr \
  --llm-parse \
  --python-executable "$OCR_PYTHON" \
  --env-file "$LEMON_AID_ENV_FILE"
```
