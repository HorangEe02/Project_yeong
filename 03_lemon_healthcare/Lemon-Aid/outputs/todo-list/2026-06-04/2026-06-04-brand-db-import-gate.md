# Brand DB Import Gate

## Summary

- brand/product review가 완료되기 전 DB import 단계로 넘어가지 않도록 redacted gate report를 추가했습니다.
- gate는 brand decision preflight JSON만 읽고, decision row payload, 원본 이미지, OCR 원문, provider payload, LLM output, DB record는 읽지 않습니다.
- partial apply 가능 상태가 되더라도 strict review가 아니면 product import manifest 생성과 DB apply를 차단합니다.

## Implemented Files

- `backend/scripts/gate_supplement_brand_db_import.py`
  - 입력 schema `supplement-brand-review-decision-preflight-v1` 검증
  - strict review completion 여부 검증
  - product import manifest 생성 허용 여부와 DB apply 허용 여부 분리
  - 출력 schema `supplement-brand-db-import-gate-v1`
- `backend/Nutrition-backend/tests/unit/scripts/test_gate_supplement_brand_db_import.py`
  - blank review 차단
  - strict ready preflight만 manifest 생성 허용
  - partial apply readiness 차단
  - unsafe preflight payload fail-closed
  - CLI JSON/Markdown redaction 검증

## Current Actual Gate

- Status: `blocked_by_operator_review`
- Brand candidates: `388`
- Blank decisions: `388`
- Approved decisions: `0`
- Product import manifest allowed: `false`
- DB apply allowed now: `false`
- DB apply allowed after dry-run: `false`

## Verification

```bash
cd backend
.venv/bin/python -m ruff check scripts/gate_supplement_brand_db_import.py Nutrition-backend/tests/unit/scripts/test_gate_supplement_brand_db_import.py scripts/preflight_supplement_brand_review_decisions.py scripts/apply_supplement_brand_review_decisions.py scripts/import_supplement_taxonomy_approved_manifest.py Nutrition-backend/tests/unit/scripts/test_preflight_supplement_brand_review_decisions.py Nutrition-backend/tests/unit/scripts/test_apply_supplement_brand_review_decisions.py Nutrition-backend/tests/unit/scripts/test_import_supplement_taxonomy_approved_manifest.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_gate_supplement_brand_db_import.py Nutrition-backend/tests/unit/scripts/test_preflight_supplement_brand_review_decisions.py Nutrition-backend/tests/unit/scripts/test_apply_supplement_brand_review_decisions.py Nutrition-backend/tests/unit/scripts/test_import_supplement_taxonomy_approved_manifest.py
```

Actual result:

- `ruff check`: passed
- `pytest --no-cov`: 28 tests passed
- Current gate CLI status: `blocked_by_operator_review`

## Security Review

- No DB write was performed.
- No OCR/provider/LLM call was performed.
- No source images or source rows were read by the gate.
- No raw OCR/provider payload, local absolute path, source ref, or product directory literal is included in the gate output.

## Next Step

1. Complete `brand_product_review:001`.
2. Reconcile operator batch files.
3. Rerun batch progress preflight.
4. Rerun strict brand decision preflight.
5. Rerun this DB import gate.

## Official References

- Python argparse: https://docs.python.org/3/library/argparse.html
- Python json: https://docs.python.org/3/library/json.html
- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
