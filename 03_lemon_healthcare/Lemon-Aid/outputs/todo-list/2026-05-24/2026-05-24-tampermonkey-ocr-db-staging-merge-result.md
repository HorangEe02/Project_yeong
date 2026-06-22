# Tampermonkey OCR DB Staging 병합 결과 - 2026-05-24

## 범위

- `2026-05-24-tampermonkey-db-labeling-staging-security-result.md`의 다음 작업 2번인 OCR/Ollama 관측값 병합 스크립트를 추가했다.
- 이 작업은 실제 DB import가 아니라 `db-labeling-staging.jsonl`에 redacted OCR observation summary를 붙이는 opt-in 전처리 단계다.
- raw OCR text, provider payload, request headers, image bytes, Ollama raw model response, `.env`, secret 값은 입력과 출력 양쪽에서 금지한다.

## 변경 파일

- `backend/scripts/merge_naver_tampermonkey_ocr_observations_into_db_staging.py`
  - `naver-tampermonkey-db-labeling-staging-v1` rows와 collector observation JSONL을 `fixture_id` 기준으로 병합한다.
  - 출력 schema는 `naver-tampermonkey-db-labeling-with-ocr-v1`이다.
  - `provider`, `status`, `text_non_empty`, `parser_success`, `char_count`, `line_count`, `latency_ms`, `text_hash`, `llm_parse_status`, bounded `llm_parsed_ingredients`만 allowlist로 전달한다.
  - staging에 없는 observation은 기본 실패 처리하고, 운영자가 명시적으로 `--allow-unmatched-observations`를 줄 때만 count 후 무시한다.
  - PII screening이 끝나지 않은 review row에는 `llm_parsed_ingredients`를 붙이지 못하게 막는다.
- `backend/Nutrition-backend/tests/unit/scripts/test_merge_naver_tampermonkey_ocr_observations_into_db_staging.py`
  - 정상 병합, raw field reject, unmatched observation fail-closed, explicit allow flag, PII-pending review row 차단, bounded PII flag 보존 테스트를 추가했다.

## 공식 문서 확인

- Python `argparse`는 command-line interface에서 required argument와 flag parsing을 제공한다: https://docs.python.org/3/library/argparse.html
- Python `json`은 JSON encoder/decoder 표준 라이브러리이며, 이번 스크립트는 JSONL 각 line을 개별 JSON object로 읽고 쓴다: https://docs.python.org/3/library/json.html

## 런타임 검증

검증 입력:

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/db-labeling-staging.jsonl
```

검증 방식:

- `/private/tmp/lemon-team-merge-observation.jsonl`에 synthetic redacted observation 1 row를 생성했다.
- 실제 stage14 staging 86 rows와 fixture id `naver-tm-detail-000001` 기준으로 병합했다.
- 생성 결과는 `/private/tmp/lemon-team-db-staging-with-ocr.jsonl`와 `/private/tmp/lemon-team-db-staging-with-ocr.summary.json`에만 만들었고 커밋 대상에 포함하지 않았다.

핵심 결과:

| 항목 | 값 |
| --- | ---: |
| staging_row_count | 86 |
| observation_count | 1 |
| matched_observation_count | 1 |
| unmatched_observation_count | 0 |
| rows_with_ocr_observations | 1 |
| rows_with_llm_ingredients | 1 |
| raw_artifacts_stored | false |
| raw_ocr_text_stored | false |
| raw_provider_payload_stored | false |
| raw_model_response_stored | false |

## 보안/유출 점검

- 출력 JSONL과 summary에서 forbidden raw key를 재귀 검사했다.
- `/Volumes/...` 외장 절대경로와 `.env` 문자열이 출력되지 않는지 확인했다.
- review row가 local PII screening pending 상태이면 LLM ingredient 병합을 실패시킨다.
- synthetic 검증 산출물은 `/private/tmp`에 두었고 repo commit 범위에서 제외했다.

검증:

```text
new merge script tests: 6 passed
focused Tampermonkey OCR script tests: 53 passed
black --check: pass
ruff --ignore RUF001: pass
runtime merge smoke: matched_observation_count=1, unmatched_observation_count=0
privacy scan: pass files=2 json_objects=86
```

## 남은 작업

1. 실제 PaddleOCR + local Ollama Gemma4 redacted observations를 생성한 뒤 이 병합 스크립트로 DB staging 후보를 만든다.
2. `naver-tampermonkey-db-labeling-with-ocr-v1`을 DB import job 또는 review UI ingest contract에 연결한다.
3. review 이미지 126,526개는 local-only PII screening artifact를 먼저 만들고, 사람 검수 전 외부 OCR 전송은 계속 금지한다.
