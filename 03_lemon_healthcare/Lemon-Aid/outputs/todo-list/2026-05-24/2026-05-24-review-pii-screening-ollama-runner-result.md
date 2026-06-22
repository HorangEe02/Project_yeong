# Review PII Screening Ollama Runner 결과

## 요약

- review PII screening manifest를 입력으로 EX400U 로컬 Ollama vision model에 보낼 수 있는 suggestion runner를 추가했다.
- runner output은 `pii_screening_suggestion` input schema만 생성하며, 사람/operator decision이나 attestation을 만들지 않는다.
- `ollama_base_url`은 `http://127.0.0.1` / `localhost` / `::1` host만 허용한다.
- image bytes와 base64 request payload는 요청 메모리에서만 사용하고 output/summary에 저장하지 않는다.
- non-dry-run에서 100건 초과 batch는 `--allow-large-run`이 있어야 진행된다.
- CLI 실패도 Python traceback 대신 redacted JSON summary만 출력/저장한다.
- 이번 검증은 dry-run 전체 계획 검증 후 EX400U 로컬 Ollama `gemma4:e4b` sample 1건 실제 호출까지 수행했다.
- sample 실행과 export 결과에는 raw image, request payload, raw model response, local path literal을 저장하지 않았다.

## 공식 문서 확인

- Ollama Chat API는 `POST /api/chat` endpoint, `messages`, `format`, `stream` body field를 문서화한다: https://docs.ollama.com/api/chat
- Ollama structured outputs는 JSON schema를 `format`에 전달하고 결과를 검증하는 방식을 안내한다: https://docs.ollama.com/capabilities/structured-outputs
- Ollama vision REST API는 `images` array에 base64 image data를 전달하는 방식을 안내한다: https://docs.ollama.com/capabilities/vision

## 구현 파일

- `backend/scripts/run_naver_tampermonkey_review_pii_screening_suggestions.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_run_naver_tampermonkey_review_pii_screening_suggestions.py`

## EX400U 모델 경로 확인

현재 `OLLAMA_MODELS='/Volumes/Corsair EX400U Media/.ollama/models' ollama list`에서 다음 모델들이 확인된다.

- `gemma4:e4b`
- `gemma4:latest`
- `gemma4:26b`
- `gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M`
- `gemma-4-26B-A4B-it-GGUF:UD-Q3_K_M`

## 실제 dry-run 결과

출력은 ignored local artifact로만 유지한다.

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/review-pii-screening-local-only/
```

| 항목 | 값 |
| --- | ---: |
| manifest_row_count | 126,526 |
| selected_row_count | 126,526 |
| suggestion_row_count | 0 |
| decision_importable_rows | 0 |
| external_transfer_allowed_rows | 0 |
| dry_run | true |
| large_run_threshold | 100 |
| large_run_approved | false |
| model | gemma4:e4b |
| ollama_base_host | 127.0.0.1 |
| db_write_performed | false |
| external_transfer_performed | false |
| request_payload_stored | false |
| raw_image_stored | false |
| raw_model_response_stored | false |
| free_text_notes_stored | false |

## 실제 sample 실행 결과

EX400U 모델 경로를 명시해 로컬 Ollama server를 띄운 뒤 1건만 실행했다.

```text
OLLAMA_MODELS='/Volumes/Corsair EX400U Media/.ollama/models'
OLLAMA_HOST=127.0.0.1:11435
model=gemma4:e4b
```

| 항목 | 값 |
| --- | ---: |
| dry_run | false |
| manifest_row_count | 126,526 |
| selected_row_count | 1 |
| suggestion_row_count | 1 |
| large_run_threshold | 100 |
| large_run_approved | false |
| status_suggestion_counts.needs_operator_review | 1 |
| operator_decision_required_rows | 1 |
| decision_importable_rows | 0 |
| request_payload_stored | false |
| raw_image_stored | false |
| raw_model_response_stored | false |
| external_transfer_performed | false |

## suggestion export 결과

sample suggestion은 곧바로 exporter를 통과시켜 non-importable review suggestion artifact로만 생성했다.

| 항목 | 값 |
| --- | ---: |
| exported_suggestion_count | 1 |
| pending_without_suggestion_count | 126,525 |
| decision_importable_rows | 0 |
| operator_decision_required_rows | 1 |
| ocr_or_llm_call_performed | false |
| external_transfer_performed | false |
| raw_model_response_stored | false |
| free_text_notes_stored | false |

## 보안 점검

- strict privacy gate: `file_count=2`, `json_value_count=23`, `finding_count=0`, `passed=true`
- sample/export strict privacy gate: `file_count=4`, `json_value_count=88`, `finding_count=0`, `passed=true`
- runner는 remote Ollama URL을 실패 처리한다.
- manifest의 `$NAVER_TAMPERMONKEY_SOURCE_ROOT/...` token path만 resolve하며, output에는 local path나 image path를 쓰지 않는다.
- model response에 `raw_model_response`, local path literal, 비허용 token이 있으면 실패한다.
- model response에 허용되지 않은 임의 필드가 있으면 실패한다.
- model response token list는 허용 token만 저장하며 중복 token은 제거한다.
- non-dry-run 100건 초과 처리는 `--allow-large-run` 없이는 모델 호출 전에 실패한다.
- CLI 실패 summary는 `manifest_name`, safe `error_code`, bounded safe `error_message`만 남기며 traceback과 `/private`, `/Users`, `/Volumes` 로컬 경로 literal을 출력하지 않는다.
- runner output은 기존 suggestion exporter를 통과해야만 non-importable review suggestion artifact가 된다.
- EX400U Ollama server는 sample 실행 및 privacy scan 후 종료했다.

## 검증

- runner unit tests: `11 passed`
- focused review PII tests: `62 passed`
- black check: pass
- ruff check: pass
- strict privacy scan: pass

## 다음 단계

추가 실행은 `OLLAMA_MODELS='/Volumes/Corsair EX400U Media/.ollama/models'`로 로컬 Ollama server를 띄운 뒤 `--limit`을 명시해 batch size를 단계적으로 늘린다. 100건 초과 batch는 별도 `--allow-large-run`을 붙인 운영 명령으로만 실행한다. 생성된 model suggestion JSONL은 반드시 suggestion exporter를 거쳐야 하며, 사람/operator decision apply gate를 통과하기 전에는 OCR/DB workflow로 승격하지 않는다.
