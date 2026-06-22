# Tampermonkey Review Decision Validation Result

## Summary

- Review UI가 작성할 `review_decision` payload를 approved export 전에 검증하는 read-only validator를 추가했다.
- pending row는 기본 허용하고, `--require-reviewed`를 켜면 모든 row가 reviewed 상태여야 통과한다.
- 현재 86개 review ingest artifact는 아직 사람이 검수하지 않았으므로 `pending=86`으로 검증된다.
- CLI 실패도 Python traceback 대신 redacted JSON summary만 출력/저장한다.

## Changed Files

- `backend/scripts/validate_naver_tampermonkey_review_decisions.py`
  - 입력 schema `naver-tampermonkey-review-ingest-v1`만 허용한다.
  - decision status는 `approved`, `rejected`, `needs_changes`만 허용한다.
  - 모든 decision은 `reviewer_id`, `reviewed_at`을 요구한다.
  - `approved` decision은 PII clearance, 3개 safety attestation, reviewed ingredients를 요구한다.
  - `rejected` / `needs_changes` decision은 structured `reason_codes`를 요구하고 import ingredients를 허용하지 않는다.
  - `review_note`, `comments`, `notes` 같은 free-text note 필드는 차단한다.
  - raw OCR/provider/model payload, secret key, image bytes, local path literal, product directory literal key를 재귀적으로 차단한다.
  - 실패 summary는 `input_name`, safe `error_code`, bounded safe `error_message`만 남기며 traceback과 `/private`, `/Users`, `/Volumes` 로컬 경로 literal을 출력하지 않는다.
- `backend/Nutrition-backend/tests/unit/scripts/test_validate_naver_tampermonkey_review_decisions.py`
  - pending 허용, strict reviewed 모드, approved attestation, PII-pending approval 차단, rejected reason code, free-text/raw/local path 차단, CLI 실패 redaction 테스트를 추가했다.

## Generated Local Artifacts

Ignored local artifact:

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/review-decision-validation-gemma4-e4b-live.summary.json
```

핵심 summary:

| Metric | Value |
| --- | ---: |
| row_count | 86 |
| pending_count | 86 |
| decision_status_counts.pending | 86 |
| approved_ingredient_count | 0 |
| require_reviewed | false |
| raw_ocr_text_stored | false |
| raw_provider_payload_stored | false |
| raw_model_response_stored | false |
| local_path_literals_stored | false |
| free_text_review_notes_stored | false |
| clinical_recommendations_stored | false |

## Security Review

- review UI가 free-text note로 raw OCR, 개인 정보, 로컬 경로를 우발 저장하는 경로를 차단했다.
- CLI 실패 summary에서 forbidden raw keys와 `/private`, `/Users`, `/Volumes`, `file://` literal이 없는지 확인했다.
- approved decision은 `attest_pii_screening_completed`, `attest_no_raw_ocr_text`, `attest_not_clinical_recommendation`가 모두 true일 때만 valid하다.
- PII-pending review row는 approval 자체가 실패한다.
- rejected/needs_changes decision은 reason code만 허용해 구조화된 검수 이력으로 제한했다.
- 이 validator는 read-only이며 DB session, OCR call, LLM call을 수행하지 않는다.

## Verification

```bash
PYTHONPATH=backend /private/tmp/lemon-p1-quality-venv/bin/python -m pytest \
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
40 passed in 0.31s
```

```bash
/private/tmp/lemon-p1-quality-venv/bin/python -m black --check \
  backend/scripts/validate_naver_tampermonkey_review_decisions.py \
  backend/Nutrition-backend/tests/unit/scripts/test_validate_naver_tampermonkey_review_decisions.py \
  backend/scripts/dry_run_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_dry_run_naver_tampermonkey_approved_db_import.py \
  backend/scripts/export_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py

/private/tmp/lemon-p1-quality-venv/bin/python -m ruff check \
  backend/scripts/validate_naver_tampermonkey_review_decisions.py \
  backend/Nutrition-backend/tests/unit/scripts/test_validate_naver_tampermonkey_review_decisions.py \
  backend/scripts/dry_run_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_dry_run_naver_tampermonkey_approved_db_import.py \
  backend/scripts/export_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py
```

Result:

```text
black: 6 files would be left unchanged
ruff: All checks passed
```

## Next Steps

1. Review UI가 `review_decision`을 JSONL에 병합하는 operator workflow를 만든다.
2. 승인된 non-empty artifact가 생기면 `approved-db-import-v1` export와 dry-run plan을 다시 실행한다.
3. DB write importer는 `review_decision` validation과 dry-run plan이 모두 통과한 artifact만 입력으로 받게 한다.
