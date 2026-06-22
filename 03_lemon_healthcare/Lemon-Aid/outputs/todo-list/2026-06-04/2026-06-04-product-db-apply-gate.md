# 2026-06-04 Product DB Apply Gate

## Summary

- Reviewed product/product-category DB apply 직전 gate를 추가하고 현재 실제 산출물로 실행했습니다.
- 현재 결과는 `blocked_by_product_db_apply_preflight`입니다.
- `product_db_apply_allowed=false`, `product_category_db_apply_allowed=false`입니다.
- 카테고리 seed는 로컬 개발 DB verifier를 통과했지만, 제품/브랜드/product-category 저장은 승인된 제품 manifest가 없어서 계속 차단합니다.

## Current Counts

- Brand candidates: `388`
- Approved decisions: `0`
- Category seed rows: `43`
- Matched categories: `43`
- Missing categories: `0`
- Approved product import rows: `0`
- Planned product upserts: `0`
- Planned product-category upserts: `0`

## Passed Conditions

- Category DB import verified: `true`
- Category count matches dry-run: `true`
- Missing category count is zero: `true`
- DB target preflight ready: `true`
- DB target is local: `true`
- DB target opened no connection: `true`
- DB target performed no write: `true`

## Failed Conditions

- Brand gate is not ready for product manifest creation.
- Brand gate does not allow product import manifest creation.
- Brand gate does not allow DB apply after dry-run yet.
- Approved product dry-run does not require approved products yet.
- Approved product dry-run has no product manifest.
- Approved product count is `0`.

## Safety Notes

- 이 gate는 source images, product folders, raw OCR, provider payload, approved product manifest row payload를 읽지 않습니다.
- 이 gate는 DB connection을 열지 않고 DB write를 수행하지 않습니다.
- 출력에는 DB URL, 자격 증명, raw OCR/provider payload, source local path를 저장하지 않습니다.

## Next Steps

- `brand_product_review:001`부터 operator brand/product review를 완료합니다.
- 승인 row를 기반으로 approved product import manifest를 생성합니다.
- `require_approved_products=true` 조건으로 approved taxonomy import dry-run을 다시 실행합니다.
- category verifier와 local DB target preflight를 재확인합니다.
- product DB apply gate를 다시 실행한 뒤 통과할 때만 제품/브랜드/product-category 저장을 진행합니다.

## References

- Python argparse: https://docs.python.org/3/library/argparse.html
- Python json: https://docs.python.org/3/library/json.html
- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- SQLAlchemy ORM select: https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
