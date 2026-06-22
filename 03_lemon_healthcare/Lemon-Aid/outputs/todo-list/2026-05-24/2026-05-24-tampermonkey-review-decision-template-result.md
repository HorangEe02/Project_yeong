# Tampermonkey Review Decision Template 결과

## 요약

- `naver-tampermonkey-review-ingest-v1`에서 사람 검수용 decision template를 생성하는 exporter를 추가했다.
- template는 `review_decision`을 포함하지 않아 apply/import에 바로 넣을 수 없다.
- DB write, OCR/LLM, external transfer, raw OCR/provider payload 저장은 없다.

## 구현 파일

- `backend/scripts/export_naver_tampermonkey_review_decision_template.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_review_decision_template.py`

## 계약

- status: `approved`, `needs_changes`, `rejected`
- approved 필수 attestation: `attest_pii_screening_completed`, `attest_no_raw_ocr_text`, `attest_not_clinical_recommendation`
- free-text notes, raw OCR text, provider payload, local path literal, clinical recommendation은 금지
- ingredient candidates는 검수 hint일 뿐 자동 승인/DB import에 쓰지 않는다.

## 실제 실행 결과

| 항목 | 값 |
| --- | ---: |
| row_count | 86 |
| rows_with_candidate_hints | 48 |
| total_candidate_hints | 155 |
| max_candidates_per_row | 8 |
| decision_batch_importable | false |
| raw/local forbidden scan | pass |

## 검증

- focused script tests: `38 passed`
- black check: pass
- ruff check: pass
- `git diff --check`: pass

## 다음 단계

template를 Review UI/수동 검수 입력으로 쓰고, 사람이 작성한 decision JSONL은 기존 review import gate를 `--require-reviewed`로 통과시킨다.
