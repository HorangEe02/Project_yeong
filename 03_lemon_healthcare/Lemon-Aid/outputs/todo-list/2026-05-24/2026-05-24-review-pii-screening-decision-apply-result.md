# Review PII Screening Decision Apply 결과

## 요약

- local-only review PII screening manifest에 operator decision JSONL을 적용하는 gate를 추가했다.
- `cleared` decision과 필수 no-PII attestations가 모두 있는 row만 후속 OCR manifest로 승격한다.
- `contains_personal_data`, `needs_redaction`, decision 없음, 알 수 없는 decision key, free-text note, raw/local path literal은 fail-closed 처리한다.
- `reviewer_id`는 `operator_` prefix가 있는 사람/operator ID만 허용한다. EX400U Ollama/Gemma4 같은 로컬 모델 suggestion은 직접 `cleared` 승격 권한이 없다.
- CLI 실패도 Python traceback 대신 redacted JSON summary만 출력/저장한다.
- 이 단계는 OCR/LLM 호출, DB write, 외부 전송을 하지 않는다.

## 구현 파일

- `backend/scripts/apply_naver_tampermonkey_review_pii_screening_decisions.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_apply_naver_tampermonkey_review_pii_screening_decisions.py`
- `.gitignore` (`outputs/generated/ocr-eval/` 신규 산출물 ignore 확인/보강)

## 실제 empty-decision 적용 결과

출력은 ignored local artifact로만 유지한다.

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/review-pii-screening-local-only/
```

| 항목 | 값 |
| --- | ---: |
| manifest_row_count | 126,526 |
| decision_row_count | 0 |
| pending_count | 126,526 |
| cleared_row_count | 0 |
| unmatched_decision_count | 0 |
| external_transfer_allowed_rows | 0 |
| db_write_performed | false |
| external_transfer_performed | false |
| raw_ocr_text_stored | false |
| raw_provider_payload_stored | false |
| raw_model_response_stored | false |
| local_path_literals_stored | false |

## 보안 점검

- privacy gate: `file_count=2`, `json_value_count=20`, `finding_count=0`, `passed=true`
- CLI 실패 summary privacy gate: `file_count=1`, `json_value_count=23`, `finding_count=0`, `passed=true`
- raw OCR text/provider payload/model response/request header/image bytes/secret key 저장 없음
- `/private`, `/Users`, `/Volumes`, `file://` 로컬 절대경로 literal 없음
- CLI 실패 summary는 `manifest_name`, `decisions_name`, safe `error_code`, bounded safe `error_message`만 남기며 traceback과 로컬 경로 literal을 출력하지 않는다.
- 후속 OCR manifest는 empty-decision 기준 0 rows이며, 사람 검수 전에는 어떤 review 이미지도 처리 대상으로 승격하지 않는다.
- 모델/자동화가 작성한 `reviewer_id=ollama_gemma4` 형태의 decision은 `operator_` prefix gate에서 실패한다.

## Ollama 경로 확인

- 다음 로컬 멀티모달 screening 단계의 모델 경로는 `/Volumes/Corsair EX400U Media/.ollama/models`로 확인했다.
- `OLLAMA_MODELS='/Volumes/Corsair EX400U Media/.ollama/models' ollama list`에서 `gemma4:latest`, `gemma4:e4b`, `gemma4:26b`, `gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M` 등이 인식된다.
- 이번 gate는 Ollama를 호출하지 않았고, 모델 raw response를 저장하지 않는다.

## 검증

- focused tests: `63 passed`
- apply script unit tests: `9 passed` (`operator_` reviewer gate 포함)
- black check: pass
- ruff check: pass
- strict privacy scan: pass

## 다음 단계

사람 또는 EX400U 경로의 로컬 멀티모달 모델이 review 이미지 PII screening decision JSONL을 생성하더라도, 이 gate를 통해 `cleared`와 필수 attestations가 없는 row는 OCR/DB workflow로 넘어가지 않는다.
