# Tampermonkey Gemma4 DB Staging 실행 결과 - 2026-05-24

## 범위

- Stage14 detail fixture 86개를 대상으로 PaddleOCR local + Ollama Gemma4 structured parse를 실행했다.
- 생성된 redacted observations를 `naver-tampermonkey-db-labeling-with-ocr-v1` DB staging 후보로 병합했다.
- 이번 작업에서도 raw OCR text, provider payload, request headers, image bytes, Ollama raw model response, `.env`, secret 값은 저장하지 않았다.

## 모델 경로 수정

현재 머신에서 `/Volumes/Corsair EX300U Media`는 마운트되어 있지 않고, 실제 Ollama 모델 저장소는 다음 경로로 확인됐다.

```text
/Volumes/Corsair EX400U Media/.ollama/models
```

따라서 별도 localhost Ollama 서버를 다음 경계로 실행했다.

```text
OLLAMA_MODELS=/Volumes/Corsair EX400U Media/.ollama/models
OLLAMA_HOST=127.0.0.1:11435
OLLAMA_NO_CLOUD=1
```

확인된 사용 모델은 `gemma4:e4b`이다. 기존 `127.0.0.1:11434` 서버는 EX300U 경로를 참조해 `/api/tags`도 실패했으므로 이번 실행에서 사용하지 않았다.

## 공식 문서 확인

- Ollama API는 설치 후 기본적으로 localhost API를 제공한다: https://docs.ollama.com/api/introduction
- Ollama structured outputs는 `format`에 JSON schema를 전달하고 Pydantic 등으로 검증하는 방식을 안내한다: https://docs.ollama.com/capabilities/structured-outputs
- PaddleOCR general OCR pipeline은 이미지에서 텍스트 정보를 추출하는 OCR pipeline과 PP-OCRv5 구성 요소를 문서화한다: https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html

## 실행 산출물

생성 위치:

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/
```

주요 파일:

- `runner-paddle-detail-86-gemma4-e4b-live/paddleocr-observations/supplement-ocr-observations.jsonl`
- `runner-paddle-detail-86-gemma4-e4b-live/naver-ocr-provider-comparison.json`
- `runner-paddle-detail-86-gemma4-e4b-live/naver-ocr-provider-comparison.md`
- `db-labeling-staging-with-ocr-gemma4-e4b-live.jsonl`
- `db-labeling-staging-with-ocr-gemma4-e4b-live.summary.json`

## 핵심 지표

| 항목 | 값 |
| --- | ---: |
| fixture_count | 86 |
| observation_count | 86 |
| provider | `paddleocr_local` |
| completed_count | 77 |
| error_count | 9 |
| completed_rate | 0.8953 |
| text_non_empty_rate | 0.8953 |
| llm_parse_attempt_count | 77 |
| llm_parse_success_rate | 0.7143 |
| llm_parse_completed | 55 |
| llm_parse_error | 22 |
| rows_with_ocr_observations | 86 |
| rows_with_llm_ingredients | 48 |
| total_merged_ingredients | 166 |
| avg_ingredients_per_nonzero_row | 3.4583 |
| p50_latency_ms | 2155.0 |
| p95_latency_ms | 13783.0 |

오류 분포:

| 항목 | 값 |
| --- | ---: |
| OCR `ocr_low_confidence` | 9 |
| LLM `ollama_client` | 18 |
| LLM `ollama_structured_output` | 4 |

## 보안/유출 점검

- Python/httpx localhost 접근은 sandbox에서 `[Errno 1] Operation not permitted`로 막혔고, 권한 상승 실행에서만 Gemma4 parser가 실제 호출됐다.
- 첫 sandbox 실행 결과는 `llm_parse_success_rate=0.0`으로 폐기 판단했고, 최종 기준은 `runner-paddle-detail-86-gemma4-e4b-live` 결과다.
- 최종 observation/report/merged DB staging 후보 5개 파일을 대상으로 forbidden raw key와 `/Volumes/...`, `.env` 문자열을 검사했다.
- 검사 대상에서 raw OCR text, provider payload, request headers, image bytes, Ollama raw response, secret key 계열 필드는 발견되지 않았다.
- Ollama 서버 로그는 `/api/tags`, `/api/chat` endpoint와 latency 중심으로만 확인했고 OCR 원문은 출력하지 않았다.

검증:

```text
privacy_scan=pass files=5 json_values=172
raw_artifacts_stored=false
raw_ocr_text_stored=false
raw_provider_payload_stored=false
raw_model_response_stored=false
unmatched_observation_count=0
```

## 한계와 다음 작업

1. `llm_parse_success_rate=0.7143`이라 DB 자동 적재용으로 바로 확정하지 않고 review UI 후보로만 사용한다.
2. `ollama_client` 18건에는 중간 Ollama 서버 종료 구간이 섞였을 가능성이 있으므로, 다음 실행에서는 서버 health monitor 또는 provider-level retry를 runner에 추가한다.
3. `ollama_structured_output` 4건은 Gemma4가 schema를 못 맞춘 케이스라 prompt/schema 축소, OCR text length cap, retry with lower context payload를 분리 검토한다.
4. OCR low confidence 9건은 상세페이지 이미지 형태를 별도 분석해 crop/resize 또는 CLOVA 비교 대상으로 분리한다.
5. `naver-tampermonkey-db-labeling-with-ocr-v1`은 아직 DB import job에 연결하지 않았고, 다음 단계에서 review UI ingest contract와 함께 확정한다.

## 후속 보강 - 2026-05-24

`ollama_client` 18건 재발을 줄이기 위해 collector에 bounded retry를 추가했다.

- `OllamaClientError`만 재시도한다.
- 기본 재시도 delay는 `0.25s`, `1.0s`이며 최대 3회 attempt다.
- `OllamaConfigurationError`와 `OllamaStructuredOutputError`는 재시도하지 않는다. 설정 오류와 schema 실패는 반복 호출보다 설정/prompt/schema를 수정해야 하는 문제이기 때문이다.
- observation에는 `llm_parse_attempt_count`, `llm_parse_retry_count` 숫자만 추가한다.
- DB staging merge도 두 숫자 필드만 allowlist로 전달한다.
- OCR 원문, Ollama raw response, provider payload, request header, image bytes, secret 값은 계속 저장하지 않는다.

보강 검증:

```text
test_collect_supplement_ocr_observations.py + test_merge_naver_tampermonkey_ocr_observations_into_db_staging.py: 34 passed
focused Tampermonkey OCR script tests: 55 passed
black --check: pass
ruff --ignore RUF001: pass
git diff --check: pass
```

참고 공식 문서:

- Python `asyncio.sleep()`은 현재 task를 delay 동안 suspend해 다른 task 실행을 허용한다: https://docs.python.org/3/library/asyncio-task.html#sleeping
- Ollama structured outputs는 JSON schema를 `format`에 전달하고 결과를 검증하는 방식을 문서화한다: https://docs.ollama.com/capabilities/structured-outputs

## 후속 보강 2 - structured output prompt 경량화

`ollama_structured_output` 4건을 줄이기 위해 Ollama parser prompt를 경량화했다.

- JSON schema는 계속 Ollama Chat API payload의 `format` 필드로 전달한다.
- user prompt에는 전체 schema 문자열을 다시 붙이지 않고, 짧은 output contract summary만 넣는다.
- OCR text가 `12,000`자를 넘으면 head `8,000`자와 tail `4,000`자를 유지하고 middle만 생략한다.
- 이 생략은 request memory 안에서만 수행되며 raw OCR text나 생략된 middle text를 저장하지 않는다.

기존 `ollama_structured_output` fixture 4건만 재실행한 smoke 결과:

| 항목 | 값 |
| --- | ---: |
| fixture_count | 4 |
| completed_count | 4 |
| llm_parse_success_count | 3 |
| llm_parse_success_rate | 0.75 |
| remaining_ollama_structured_output | 1 |
| ingredient_count_avg | 7.0 |

검증:

```text
test_ollama_parser.py + collector/merge focused tests: 47 passed
LLM parser + Tampermonkey OCR script tests: 68 passed
black --check: pass
ruff --ignore RUF001: pass
structured-output retry smoke privacy scan: pass files=3 json_values=4
```

남은 1건은 prompt 크기보다 실제 schema 적합성 문제일 수 있으므로, 다음 단계에서 schema를 더 완화하지 않고 operator review 대상으로 분리하거나 별도 model fallback 후보로 비교한다.

## 후속 보강 3 - evaluator redaction

provider comparison evaluator가 정상/실패 summary에서 manifest/output 절대경로를 노출하지 않도록 보강했다.

- 정상 summary는 `manifest_name`과 `manifest_path_hash`만 남기고 `manifest` 절대경로는 저장하지 않는다.
- CLI 출력은 `json_name`, `markdown_name`만 출력한다.
- manifest/observation 읽기 실패는 traceback 대신 redacted failure report를 JSON/Markdown으로 생성한다.
- observation/manifest 입력에 `/private`, `/Users`, `/Volumes`, `file://` local path literal이 섞이면 저장 전에 실패한다.

보강 검증:

```text
test_evaluate_naver_tampermonkey_ocr.py: 5 passed
CLI failure redaction probe: pass
artifact privacy gate: pass
detect-secrets scan: pass
```

## 후속 보강 4 - runner dry-run redaction

provider runner wrapper가 dry-run/summary에서 collector command 절대경로, Python 실행 파일 경로, output root 경로, env file 경로를 노출하지 않도록 보강했다.

- 실제 subprocess command는 내부에서만 절대경로를 유지한다.
- 공개 summary의 run plan은 `output_dir_name`, `output_dir_hash`, `python_executable_name`, `python_executable_hash`만 남긴다.
- `--env-file` 값은 filename도 출력하지 않고 `<env_file>` 토큰으로 대체한다.
- wrapper 실패는 traceback 대신 redacted failure summary로 출력한다.

보강 검증:

```text
test_run_naver_tampermonkey_ocr_eval.py: 9 passed
dry-run redaction probe: pass
CLI failure redaction probe: pass
```
