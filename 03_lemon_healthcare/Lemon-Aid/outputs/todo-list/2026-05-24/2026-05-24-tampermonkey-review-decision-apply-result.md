# Tampermonkey Review Decision Apply Result

## Summary

- Review UI 또는 operator가 작성한 structured decision JSONL을 `naver-tampermonkey-review-ingest-v1`에 병합하는 apply workflow를 추가했다.
- 병합 output은 다시 review-decision validator 규칙을 통과해야만 생성된다.
- 현재는 사람이 검수한 decision batch가 없으므로 empty decision batch를 적용했고, 86개 row 모두 pending으로 유지되는 것을 확인했다.

## Changed Files

- `backend/scripts/apply_naver_tampermonkey_review_decisions.py`
  - `review_task_id` 기준으로 decision JSONL을 review ingest row에 병합한다.
  - duplicate decision, unmatched decision, 기존 decision overwrite를 기본 차단한다.
  - `--overwrite-existing`, `--allow-unmatched-decisions`, `--require-reviewed`는 명시 opt-in으로만 동작한다.
  - 병합 후 `validate_naver_tampermonkey_review_decisions` 규칙을 재사용해 output 전체를 검증한다.
  - raw OCR/provider/model payload, secret key, image bytes, local path literal, product directory literal key를 재귀적으로 차단한다.
- `backend/Nutrition-backend/tests/unit/scripts/test_apply_naver_tampermonkey_review_decisions.py`
  - valid decision attach, partial pending, strict reviewed mode, unmatched/duplicate decision fail, overwrite gate, unsafe payload 차단, PII-pending approval 차단 테스트를 추가했다.

## Generated Local Artifacts

Ignored local artifact:

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/review-ingest-with-decisions-empty-gemma4-e4b-live.jsonl
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/review-ingest-with-decisions-empty-gemma4-e4b-live.jsonl.summary.json
```

핵심 summary:

| Metric | Value |
| --- | ---: |
| review_row_count | 86 |
| decision_row_count | 0 |
| matched_decision_count | 0 |
| unmatched_decision_count | 0 |
| pending_count | 86 |
| decision_status_counts.pending | 86 |
| require_reviewed | false |
| overwrite_existing | false |
| allow_unmatched_decisions | false |
| raw_ocr_text_stored | false |
| raw_provider_payload_stored | false |
| raw_model_response_stored | false |
| local_path_literals_stored | false |
| free_text_review_notes_stored | false |
| clinical_recommendations_stored | false |

## Security Review

- decision JSONL은 review ingest에 없는 `review_task_id`를 기본적으로 허용하지 않는다.
- 같은 `review_task_id`가 decision file에 중복되면 실패한다.
- 기존 decision이 있는 row를 덮어쓰려면 `--overwrite-existing`이 필요하다.
- PII-pending review row에 approved decision을 붙이면 병합 후 validation에서 실패한다.
- 병합 output은 raw OCR text, provider payload, request headers, model raw response, image bytes, secret key, local path literal, free-text note를 저장하지 않는다.

## Verification

```bash
PYTHONPATH=backend /private/tmp/lemon-p1-quality-venv/bin/python -m pytest \
  backend/Nutrition-backend/tests/unit/scripts/test_apply_naver_tampermonkey_review_decisions.py \
  backend/Nutrition-backend/tests/unit/scripts/test_validate_naver_tampermonkey_review_decisions.py \
  backend/Nutrition-backend/tests/unit/scripts/test_dry_run_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_review_ingest.py \
  backend/Nutrition-backend/tests/unit/scripts/test_merge_naver_tampermonkey_ocr_observations_into_db_staging.py \
  backend/Nutrition-backend/tests/unit/scripts/test_build_naver_tampermonkey_db_labeling_staging.py \
  -q --no-cov
```

Result:

```text
45 passed in 0.33s
```

```bash
/private/tmp/lemon-p1-quality-venv/bin/python -m black --check \
  backend/scripts/apply_naver_tampermonkey_review_decisions.py \
  backend/Nutrition-backend/tests/unit/scripts/test_apply_naver_tampermonkey_review_decisions.py \
  backend/scripts/validate_naver_tampermonkey_review_decisions.py \
  backend/Nutrition-backend/tests/unit/scripts/test_validate_naver_tampermonkey_review_decisions.py

/private/tmp/lemon-p1-quality-venv/bin/python -m ruff check \
  backend/scripts/apply_naver_tampermonkey_review_decisions.py \
  backend/Nutrition-backend/tests/unit/scripts/test_apply_naver_tampermonkey_review_decisions.py \
  backend/scripts/validate_naver_tampermonkey_review_decisions.py \
  backend/Nutrition-backend/tests/unit/scripts/test_validate_naver_tampermonkey_review_decisions.py
```

Result:

```text
black: 4 files would be left unchanged
ruff: All checks passed
```

## Next Steps

1. 실제 사람이 검수한 decision JSONL이 생기면 `apply -> validate --require-reviewed -> approved export -> dry-run` 순서로 실행한다.
2. non-empty approved dry-run이 생긴 뒤에만 실제 SQLAlchemy upsert job을 구현한다.
3. review 이미지 126,526개는 이 decision workflow에 들어오기 전에 local-only PII screening을 먼저 완료한다.
