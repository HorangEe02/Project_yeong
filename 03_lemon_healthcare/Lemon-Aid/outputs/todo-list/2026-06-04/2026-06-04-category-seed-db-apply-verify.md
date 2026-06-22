# Category Seed DB Apply And Verify

## Summary

- 로컬 개발 Docker Compose DB에서 supplement category seed apply를 실행했습니다.
- Alembic migration을 head까지 적용한 뒤 category seed rows만 DB에 upsert했습니다.
- Verifier 기준 category 43개가 모두 DB에서 확인됐습니다.
- 제품/브랜드/product-category rows는 operator review 전이므로 저장하지 않았습니다.

## Execution Guard

- DB target preflight: `ready_for_local_category_seed_apply`
- Runtime environment: `development`
- Database host class: `local`
- Product DB apply allowed: `false`
- Product-category DB apply allowed: `false`
- Raw OCR/provider payload/local source path: not stored or printed.

## Apply Result

- Schema: `supplement-taxonomy-approved-db-import-v1`
- Apply requested: `true`
- DB write performed: `true`
- Category seed rows: `43`
- Planned category upserts: `43`
- Inserted categories: `10`
- Updated categories: `33`
- Approved product import rows: `0`
- Inserted products: `0`
- Updated products: `0`
- Inserted product-category rows: `0`
- Updated product-category rows: `0`

## Verify Result

- Schema: `supplement-taxonomy-db-import-verification-v1`
- DB import verified: `true`
- Expected category count: `43`
- Matched category count: `43`
- Missing category count: `0`
- Expected product count: `0`
- Matched product count: `0`
- Expected product-category count: `0`
- Matched product-category count: `0`

## Commands

- Docker Compose DB startup:
  - `docker compose up -d db`
- Container network apply/verify:
  - `docker compose run --rm ... backend sh -lc '/opt/venv/bin/alembic upgrade head && /opt/venv/bin/python scripts/import_supplement_taxonomy_approved_manifest.py --taxonomy-staging <staging-jsonl> --apply --summary <apply-summary-json> && /opt/venv/bin/python scripts/verify_supplement_taxonomy_db_import.py --taxonomy-staging <staging-jsonl> --fail-on-missing --summary <verify-summary-json>'`

## Notes

- `db` service does not publish a host port, so host-side importer could not connect to `localhost`.
- The successful path runs inside the backend container network with current worktree scripts mounted read-only.
- The first host-side apply attempt failed before DB write because no host PostgreSQL listener was available.

## References

- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- SQLAlchemy ORM select: https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

## Remaining Blocker

- Brand/product DB import is still blocked by blank operator review rows.
- OCR benchmark is still blocked by PII screening review.
- YOLO section dataset is still blocked by annotation review.
