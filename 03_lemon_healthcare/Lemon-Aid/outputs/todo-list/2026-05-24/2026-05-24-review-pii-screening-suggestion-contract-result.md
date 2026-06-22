# Review PII Screening Suggestion Contract 결과

## 요약

- EX400U 로컬 멀티모달 모델이 만든 PII screening 결과를 operator decision과 분리하는 suggestion-only export 계약을 추가했다.
- suggestion artifact는 `decision_importable=false`, `operator_decision_required=true`, `external_transfer_allowed=false`로 고정된다.
- `pii_screening_decision`, `reviewer_id`, `reviewed_at`, `status`, `attest_*`, free-text note, raw OCR/model/provider payload, local path literal은 모두 실패 처리한다.
- CLI 실패도 Python traceback 대신 redacted JSON summary만 출력/저장한다.
- 이 단계는 OCR/LLM 호출, DB write, 외부 전송을 하지 않는다.

## 공식 문서 확인

- Ollama API 기본 로컬 endpoint: https://docs.ollama.com/api
- Ollama Chat API `POST /api/chat`, `messages`, `format`, `stream`: https://docs.ollama.com/api/chat
- Ollama structured outputs는 JSON schema를 `format`에 넣고 결과를 검증하는 흐름을 안내한다: https://docs.ollama.com/capabilities/structured-outputs
- Ollama vision 사용은 image input을 포함한 Chat API 흐름을 안내한다: https://docs.ollama.com/capabilities/vision

이번 작업은 위 로컬 API 흐름으로 생성될 수 있는 결과를 받을 contract만 추가했으며, 실제 Ollama 호출은 수행하지 않았다.

## 구현 파일

- `backend/scripts/export_naver_tampermonkey_review_pii_screening_suggestions.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_review_pii_screening_suggestions.py`

## 실제 empty-suggestion 적용 결과

출력은 ignored local artifact로만 유지한다.

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/review-pii-screening-local-only/
```

| 항목 | 값 |
| --- | ---: |
| manifest_row_count | 126,526 |
| suggestion_row_count | 0 |
| exported_suggestion_count | 0 |
| pending_without_suggestion_count | 126,526 |
| unmatched_suggestion_count | 0 |
| decision_importable_rows | 0 |
| external_transfer_allowed_rows | 0 |
| db_write_performed | false |
| external_transfer_performed | false |
| ocr_or_llm_call_performed | false |
| raw_model_response_stored | false |
| free_text_notes_stored | false |

## 보안 점검

- strict privacy gate: `file_count=2`, `json_value_count=24`, `finding_count=0`, `passed=true`
- CLI 실패 summary privacy gate: `file_count=1`, `json_value_count=27`, `finding_count=0`, `passed=true`
- output row에는 `image_path`를 저장하지 않고 `image_ref_hash`만 남긴다.
- model suggestion은 `likely_clear`를 내더라도 operator decision으로 변환되지 않는다.
- `/private`, `/Users`, `/Volumes`, `file://` 로컬 절대경로 literal을 차단한다.
- CLI 실패 summary는 `manifest_name`, `suggestions_name`, safe `error_code`, bounded safe `error_message`만 남기며 traceback과 로컬 경로 literal을 출력하지 않는다.
- 사람/operator가 별도 `operator_...` reviewer id와 attestation을 가진 decision JSONL을 만들기 전에는 어떤 review 이미지도 후속 OCR/DB workflow로 승격되지 않는다.

## 검증

- suggestion contract unit tests: `13 passed`
- focused review PII tests: `65 passed`
- black check: pass
- ruff check: pass
- strict privacy scan: pass

## 다음 단계

EX400U 경로의 로컬 Ollama/Gemma4 runner는 이 suggestion schema만 출력하게 하고, operator UI 또는 수동 검수가 별도 decision JSONL을 만든 뒤 기존 PII decision apply gate를 통과시킨다.
