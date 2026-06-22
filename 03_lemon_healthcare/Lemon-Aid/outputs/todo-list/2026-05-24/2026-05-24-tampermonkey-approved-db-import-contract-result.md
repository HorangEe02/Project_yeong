# Tampermonkey Approved DB Import Contract Result

## Summary

- `naver-tampermonkey-review-ingest-v1` 이후 단계로 `naver-tampermonkey-approved-db-import-v1` export 스크립트를 추가했다.
- 이 스크립트는 DB에 직접 write하지 않는다. 사람이 승인한 row만 reference product import 후보 JSONL로 내보내는 fail-closed handoff이다.
- 현재 86개 detail review ingest artifact는 아직 `review_decision.status=approved`가 없으므로 import 후보는 0개로 생성된다.

## Changed Files

- `backend/scripts/export_naver_tampermonkey_approved_db_import.py`
  - 입력 schema `naver-tampermonkey-review-ingest-v1`만 허용한다.
  - `review_decision.status=approved` row만 출력한다.
  - `attest_pii_screening_completed`, `attest_no_raw_ocr_text`, `attest_not_clinical_recommendation`가 모두 true여야 한다.
  - `contains_personal_data=false`가 아니면 승인 row라도 DB import 후보로 내보내지 않는다.
  - output은 `SupplementProduct` / `SupplementProductIngredient` import에 맞는 product/ingredient 후보, source payload, import gate만 포함한다.
- `backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py`
  - 승인 row export, unapproved skip, strict mode fail, attestation 누락 차단, PII 미해제 차단, raw/local path literal 차단 테스트를 추가했다.

## Generated Local Artifacts

Ignored local artifact:

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/approved-db-import-gemma4-e4b-live.jsonl
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/approved-db-import-gemma4-e4b-live.jsonl.summary.json
```

핵심 summary:

| Metric | Value |
| --- | ---: |
| input_row_count | 86 |
| approved_row_count | 0 |
| skipped_unapproved_count | 86 |
| skipped_rejected_count | 0 |
| raw_ocr_text_stored | false |
| raw_provider_payload_stored | false |
| raw_model_response_stored | false |
| local_path_literals_stored | false |
| clinical_recommendations_stored | false |

## Security Review

- unapproved review queue row는 DB import 후보로 자동 승격되지 않는다.
- 승인 row라도 PII clearance와 3개 safety attestation이 없으면 실패한다.
- raw OCR text, provider payload, request headers, model raw response, image bytes, secret key, `/private`/`/Users`/`/Volumes`/`file://` local path literal, product directory literal key를 재귀적으로 차단한다.
- 출력 source payload는 fixture id, review task id, image hashes, category tags, reviewer id, reviewed timestamp, count metadata만 보존한다.
- 출력 ingredient는 사람이 검수한 `review_decision.ingredients`만 사용한다. LLM 후보를 자동 승격하지 않는다.
- CLI 실패 summary는 traceback이나 입력/output 절대경로 대신 `input_name`, `output_name`, hashed path id, bounded `error_code`/`error_message`만 남긴다.

## Verification

```bash
PYTHONPATH=backend /private/tmp/lemon-p1-quality-venv/bin/python -m pytest \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_review_ingest.py \
  backend/Nutrition-backend/tests/unit/scripts/test_merge_naver_tampermonkey_ocr_observations_into_db_staging.py \
  backend/Nutrition-backend/tests/unit/scripts/test_build_naver_tampermonkey_db_labeling_staging.py \
  -q --no-cov
```

Result:

```text
25 passed in 0.04s
```

```bash
/private/tmp/lemon-p1-quality-venv/bin/python -m black --check \
  backend/scripts/export_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py

/private/tmp/lemon-p1-quality-venv/bin/python -m ruff check \
  backend/scripts/export_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py
```

Result:

```text
black: 2 files would be left unchanged
ruff: All checks passed
CLI failure redaction probe: pass
artifact privacy gate: pass
detect-secrets scan: pass
```

## Next Steps

1. Review UI가 `review_decision`을 작성할 때 위 attestation 필드를 필수 입력으로 강제한다.
2. `naver-tampermonkey-approved-db-import-v1`을 실제 DB upsert job으로 연결하기 전에 dry-run SQLAlchemy importer를 별도 PR로 만든다.
3. review 이미지 126,526개는 local-only PII screening을 먼저 완료한 뒤, approved import 경로로만 승격한다.
