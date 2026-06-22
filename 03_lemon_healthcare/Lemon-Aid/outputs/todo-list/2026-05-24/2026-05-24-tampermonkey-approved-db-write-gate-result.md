# Tampermonkey Approved DB Write Gate Result

## Summary

- `naver-tampermonkey-approved-db-import-v1`을 실제 `SupplementProduct` / `SupplementProductIngredient` DB write로 연결하는 runner를 추가했다.
- 기본 실행은 preflight-only이며 DB session을 열지 않는다.
- 실제 write는 `--execute-db-write`가 있고 아래 증거 파일이 모두 일치할 때만 가능하다.
  - approved import JSONL
  - dry-run plan JSONL
  - dry-run summary JSON
  - artifact privacy check summary JSON
  - reviewer approval log JSON
- 증거 파일은 SHA-256으로 서로 묶이고, reviewer approval log는 allowlist field만 허용한다.

## Changed Files

- `backend/scripts/run_naver_tampermonkey_approved_db_import.py`
  - approved input과 dry-run plan을 재계산 비교해 drift를 차단한다.
  - privacy summary가 `passed=true`, `finding_count=0`, `db_write_performed=false`, `external_transfer_performed=false`일 때만 통과한다.
  - reviewer approval log는 `approved_input_sha256`, `dry_run_plan_sha256`, `dry_run_summary_sha256`, `privacy_summary_sha256`가 실제 파일 digest와 일치해야 한다.
  - DB write path는 source key 기준 product upsert 후 child ingredient를 replace한다.
  - CLI 실패 summary는 basename과 bounded error만 출력하고 traceback, DB URL, local path literal은 출력하지 않는다.
- `backend/Nutrition-backend/tests/unit/scripts/test_run_naver_tampermonkey_approved_db_import.py`
  - matching evidence preflight, hash mismatch, failed privacy summary, default no-write, fake session write path, CLI redaction을 검증한다.

## Official References

- SQLAlchemy AsyncIO / `AsyncSession`: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- SQLAlchemy ORM DML guide: https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html
- SQLAlchemy PostgreSQL dialect / `ON CONFLICT` reference: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html

## Security Review

- 이 runner는 기본값으로 DB write를 수행하지 않는다.
- 실제 DB write는 `--execute-db-write` 없이는 실행되지 않는다.
- approval log에 free-text note, local path, raw payload, secret-like key가 들어오면 recursive unsafe-payload gate에서 실패한다.
- generated summary에는 DB URL, SQL text, absolute path, raw OCR text, provider payload, request headers, model raw response, image bytes를 저장하지 않는다.
- approved row라도 dry-run 재계산 결과와 저장된 dry-run plan이 byte-level JSON object 기준으로 달라지면 실패한다.
- PostgreSQL `ON CONFLICT` 기반 단일 statement upsert는 추후 동시 importer가 생길 때 고려하고, 현재 operator-runner는 기존 ORM style에 맞춰 session transaction 안에서 source key 조회 후 update/insert를 수행한다.

## Verification

```bash
PYTHONPATH=backend:backend/Nutrition-backend /private/tmp/lemon-p1-quality-venv/bin/python -m pytest \
  backend/Nutrition-backend/tests/unit/scripts/test_run_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_dry_run_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_run_naver_tampermonkey_review_import_gate.py \
  backend/Nutrition-backend/tests/unit/scripts/test_check_ocr_artifact_privacy.py \
  -q --no-cov
```

Result:

```text
35 passed in 0.38s
```

```bash
/private/tmp/lemon-p1-quality-venv/bin/python -m black --check \
  backend/scripts/run_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_run_naver_tampermonkey_approved_db_import.py

/private/tmp/lemon-p1-quality-venv/bin/python -m ruff check \
  backend/scripts/run_naver_tampermonkey_approved_db_import.py \
  backend/Nutrition-backend/tests/unit/scripts/test_run_naver_tampermonkey_approved_db_import.py
```

Result:

```text
black: 2 files would be left unchanged
ruff: All checks passed
```

## Next Steps

1. Non-empty approved artifact가 생기면 privacy summary와 reviewer approval log를 생성해 preflight-only로 먼저 실행한다.
2. 실제 DB write는 reviewer approval log와 dry-run evidence를 별도 리뷰한 뒤 `--execute-db-write`로 1회 실행한다.
3. 동시 importer나 대량 batch가 필요해지면 PostgreSQL `ON CONFLICT` 기반 atomic upsert로 교체한다.
