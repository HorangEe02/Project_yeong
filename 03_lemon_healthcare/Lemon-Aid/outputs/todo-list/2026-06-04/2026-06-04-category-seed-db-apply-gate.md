# Supplement Category Seed DB Apply Gate

## Summary

- category seed DB apply 가능 여부를 제품/브랜드 DB write와 분리해서 판단하는 gate를 추가했습니다.
- 입력은 taxonomy staging summary와 category-only import dry-run summary입니다.
- 이 gate는 DB 접속, DB write, 원본 row 읽기, 이미지 스캔, OCR/LLM 호출을 수행하지 않습니다.

## Actual Result

- Status: `ready_for_category_seed_db_apply`
- Category seed apply allowed: `true`
- Product apply allowed: `false`
- Product-category apply allowed: `false`
- Category seed rows: `43`
- Brand candidate rows: `388`
- Planned category upserts: `43`
- Planned product upserts: `0`

## Conditions

- Category rows are seedable: `true`
- Brand rows remain review-gated: `true`
- Dry-run has no product manifest: `true`
- Dry-run has no product rows: `true`
- Dry-run plans only category upserts: `true`
- Dry-run performed no DB write: `true`
- Dry-run ready for DB write: `true`

## Interpretation

카테고리 seed만 DB에 적용할 준비는 됐습니다. 하지만 제품/브랜드 및 product-category mapping은 아직 허용하지 않습니다. 실제 적용을 진행한다면 category-only apply 명령과 category verifier를 별도로 실행하고, 제품/브랜드 저장은 strict brand review와 approved product dry-run이 끝난 뒤 진행해야 합니다.

## Verification

- `cd backend && .venv/bin/python -m ruff check scripts/gate_supplement_category_seed_db_apply.py Nutrition-backend/tests/unit/scripts/test_gate_supplement_category_seed_db_apply.py`
- `cd backend && .venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_gate_supplement_category_seed_db_apply.py Nutrition-backend/tests/unit/scripts/test_build_supplement_taxonomy_db_staging.py Nutrition-backend/tests/unit/scripts/test_import_supplement_taxonomy_approved_manifest.py`
- Actual gate report generated as a temporary redacted artifact.
