# Tampermonkey DB Import Dry-Run Result

## Summary

- `naver-tampermonkey-approved-db-import-v1`을 실제 DB write 전에 검증하는 dry-run importer를 추가했다.
- 이 단계는 데이터베이스 연결을 열지 않고, `SupplementProduct`와 `SupplementProductIngredient` ORM metadata의 table name, conflict key, string length, amount boundary를 검증한다.
- 현재 approved import artifact는 승인 row가 0개라서 dry-run plan도 0개이다. 이는 정상 fail-closed 상태다.
- CLI 실패도 Python traceback 대신 redacted JSON summary만 출력/저장한다.

## Changed Files

- `backend/scripts/dry_run_naver_tampermonkey_approved_db_import.py`
  - 입력 schema `naver-tampermonkey-approved-db-import-v1`만 허용한다.
  - `SupplementProduct.__table__` / `SupplementProductIngredient.__table__` metadata에서 table name과 String column length를 확인한다.
  - `source_provider + source_product_id` 중복을 DB conflict 전에 실패 처리한다.
  - ingredient `amount`는 ORM `Numeric(14, 6)` 경계에 맞게 non-negative, scale 6 이하, integer digits 8 이하만 허용한다.
  - 출력 plan은 `dry_run_only=true`, `db_write_performed=false`로 고정한다.
  - `source_payload` 원문 대신 deterministic hash만 dry-run plan에 기록한다.
  - 실패 summary는 `input_name`, safe `error_code`, bounded safe `error_message`만 남기며 traceback과 `/private`, `/Users`, `/Volumes` 로컬 경로 literal을 출력하지 않는다.
- `backend/scripts/export_naver_tampermonkey_approved_db_import.py`
  - dry-run에서 발견한 실제 DB 컬럼 경계 문제를 보정했다.
  - `SupplementProduct.source_manifest_version`은 `String(32)`라서, 승인 export의 값은 `naver-tm-review-ingest-v1`로 축약한다.
- `backend/Nutrition-backend/tests/unit/scripts/test_dry_run_naver_tampermonkey_approved_db_import.py`
  - ORM table mapping, empty approved file, duplicate key, column length, import gate, raw/local path, Numeric boundary 테스트를 추가했다.
- `backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py`
  - 축약된 `source_manifest_version` 기대값을 고정했다.

## Generated Local Artifacts

Ignored local artifact:

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/approved-db-import-dry-run-gemma4-e4b-live.jsonl
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/approved-db-import-dry-run-gemma4-e4b-live.jsonl.summary.json
```

핵심 summary:

| Metric | Value |
| --- | ---: |
| input_row_count | 0 |
| planned_product_upsert_count | 0 |
| planned_ingredient_replace_count | 0 |
| planned_ingredient_row_count | 0 |
| product_table | supplement_products |
| ingredient_table | supplement_product_ingredients |
| dry_run_only | true |
| db_write_performed | false |
| raw_ocr_text_stored | false |
| raw_provider_payload_stored | false |
| raw_model_response_stored | false |
| local_path_literals_stored | false |
| clinical_recommendations_stored | false |

## Security Review

- 이 dry-run은 DB session, DB URL, SQL execution을 사용하지 않는다.
- generated dry-run artifact에서 forbidden raw keys와 `/Users`, `/Volumes`, `file://` literal이 없는지 확인했다.
- CLI 실패 summary에서 forbidden raw keys와 `/private`, `/Users`, `/Volumes`, `file://` literal이 없는지 확인했다.
- raw OCR text, provider payload, request headers, model raw response, image bytes, secret key, local path literal, product directory literal key를 재귀적으로 차단한다.
- approved row라도 `import_gate.ready_for_db_import`, `human_review_approved`, `pii_screening_completed`가 모두 true가 아니면 실패한다.
- clinical recommendation flag가 false/forbidden true가 아니면 실패한다.

## Verification

```bash
PYTHONPATH=backend /private/tmp/lemon-p1-quality-venv/bin/python -m pytest \
  backend/Nutrition-backend/tests/unit/scripts/test_dry_run_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py \
  -q --no-cov
```

Result:

```text
14 passed in 0.24s
```

```bash
/private/tmp/lemon-p1-quality-venv/bin/python -m black --check \
  backend/scripts/dry_run_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_dry_run_naver_tampermonkey_approved_db_import.py \
  backend/scripts/export_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py

/private/tmp/lemon-p1-quality-venv/bin/python -m ruff check \
  backend/scripts/dry_run_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_dry_run_naver_tampermonkey_approved_db_import.py \
  backend/scripts/export_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py
```

Result:

```text
black: 4 files would be left unchanged
ruff: All checks passed
```

## References

- SQLAlchemy Declarative Table Configuration: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html

## Next Steps

1. Review UI가 `review_decision`과 safety attestation을 생성하는 contract test를 추가한다.
2. dry-run plan이 non-empty인 승인 artifact를 대상으로 SQLAlchemy upsert job을 별도 PR에서 구현한다.
3. 실제 DB write job은 dry-run summary, privacy scan, reviewer approval log가 모두 있는 경우에만 실행하도록 gate를 둔다.
