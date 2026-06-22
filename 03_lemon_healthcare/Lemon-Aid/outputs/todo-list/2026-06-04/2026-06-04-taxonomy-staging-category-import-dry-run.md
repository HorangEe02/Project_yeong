# Supplement Taxonomy Staging And Category Import Dry Run

## Summary

- 실제 source folder 구조를 기준으로 taxonomy DB staging을 다시 생성했습니다.
- 생성된 staging을 reviewed product manifest 없이 importer에 넣어 category-only dry-run을 실행했습니다.
- 이 단계는 DB write 없이 category seed rows가 importer 계약을 통과하는지 확인하는 목적입니다.

## Staging Result

- Row count: `431`
- Category seed rows: `43`
- Brand candidate rows: `388`
- Review required rows: `388`
- Approved for DB write rows: `43`
- Source kind counts:
  - review images: `132520`
  - detail page images: `5289`
- Source structure issue counts:
  - missing review dir: `21`
  - missing detail page dir: `1`

## Import Dry Run Result

- Schema: `supplement-taxonomy-approved-db-import-v1`
- Preflight only: `true`
- DB write performed: `false`
- Ready for DB write: `true`
- Planned category upsert count: `43`
- Planned product upsert count: `0`
- Planned product-category upsert count: `0`

## Interpretation

현재 category seed rows는 importer 기준으로 유효합니다. 다만 브랜드/제품 rows는 388개 모두 operator review-gated 상태이므로, product/brand DB 저장은 아직 진행하지 않습니다. 다음 단계는 brand/product review를 완료한 뒤 approved product import manifest를 만들고, require-approved-products dry-run을 별도로 통과시키는 것입니다.

## Verification

- `build_supplement_taxonomy_db_staging.py` actual source run completed.
- `import_supplement_taxonomy_approved_manifest.py` category-only dry-run completed.
- Both reports state `db_write_performed=false`.
