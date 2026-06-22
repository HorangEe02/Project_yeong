# Supplement Taxonomy Persistence Contract Audit

## Summary

- 새 read-only 감사 도구 `audit_supplement_taxonomy_persistence_contract.py`를 추가했습니다.
- 목적은 영양제 카테고리, 제품/브랜드, 제품-카테고리 매핑이 DB에 저장될 수 있는 구조인지 확인하는 것입니다.
- 감사는 ORM metadata, migration, staging/import/verifier script, focused test 존재 여부만 확인합니다.
- DB 접속, DB write, 원본 이미지 스캔, OCR 호출, LLM 호출, 학습 실행은 수행하지 않습니다.

## Result

- Status: `ready_for_reviewed_import_dry_run`
- Reviewed import dry-run allowed: `true`
- DB apply allowed now: `false`
- Blocked reasons: `0`

## Verified Contracts

| Contract | Result |
| --- | --- |
| `supplement_categories` required columns | `pass` |
| `supplement_products` required columns | `pass` |
| `supplement_product_categories` required columns | `pass` |
| product-category foreign keys | `pass` |
| unique constraints and indexes | `pass` |
| taxonomy migration presence/RLS/sanitization | `pass` |
| staging/import/verifier script contracts | `pass` |
| focused tests | `pass` |
| unsafe raw storage columns absent | `pass` |

## Interpretation

현재 구조는 재설계 없이 다음 단계로 갈 수 있습니다. 다만 실제 DB apply는 아직 허용하지 않습니다. 브랜드/제품 operator review가 완료되고, approved product import manifest 생성과 taxonomy import dry-run이 통과한 뒤에만 DB apply를 진행해야 합니다.

## Verification

- `cd backend && .venv/bin/python -m ruff check scripts/audit_supplement_taxonomy_persistence_contract.py Nutrition-backend/tests/unit/scripts/test_audit_supplement_taxonomy_persistence_contract.py scripts/build_supplement_taxonomy_db_staging.py scripts/import_supplement_taxonomy_approved_manifest.py scripts/verify_supplement_taxonomy_db_import.py`
- `cd backend && .venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_audit_supplement_taxonomy_persistence_contract.py Nutrition-backend/tests/unit/scripts/test_build_supplement_taxonomy_db_staging.py Nutrition-backend/tests/unit/scripts/test_import_supplement_taxonomy_approved_manifest.py Nutrition-backend/tests/unit/scripts/test_verify_supplement_taxonomy_db_import.py Nutrition-backend/tests/unit/db/test_models.py Nutrition-backend/tests/unit/db/test_alembic_setup.py`
- Actual audit artifact generated as a temporary redacted report with status `ready_for_reviewed_import_dry_run`.

## References

- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- SQLAlchemy ORM select: https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
