# 2026-06-04 Operator Workpack Decision Guide

## Summary

- Operator workpack Markdown에 queue별 decision schema guide를 추가했습니다.
- 목적은 `brand_product_review:001` 같은 batch를 사람이 작성할 때 invalid decision을 줄이고, reconcile 전에 어떤 값이 필요한지 명확히 보이게 하는 것입니다.
- workpack 생성은 source rows, source images, raw OCR, provider payload, DB record를 읽지 않습니다.
- 출력은 batch key, file name, row range, allowed decision token, required field token, required attestation token만 포함합니다.

## Brand Product Review Guide

- Decision object: `brand_review_decision`
- Allowed decisions: `approve`, `reject`, `needs_review`, `not_a_brand`
- Required fields:
  - `reviewer_id_operator_prefix`
  - `reviewed_at_safe_token`
  - `reviewed_manufacturer`
  - `reviewed_product_name`
  - `reason_codes`
- Required approval attestations:
  - `attest_brand_product_review_completed`
  - `attest_not_using_product_folder_literal_as_manufacturer`
  - `attest_product_name_reviewed_from_label_or_safe_catalog`
  - `attest_no_raw_ocr_or_provider_payload_copied`
  - `attest_db_import_allowed`
- Invalid if:
  - free-text notes are added
  - local path or URL literal is added
  - raw OCR or provider payload is copied
  - product folder literal is used without review

## Current Regenerated Workpack

- Workpack status: `ok`
- Batch count: `18`
- Workpack file count: `19`
- Next batch: `brand_product_review:001`
- Source rows read: `false`
- Source image read: `false`
- DB write: `false`
- OCR provider or LLM call: `false`

## Next Steps

- Operator fills `brand_product_review:001` with reviewed manufacturer and product name decisions.
- Run batch file preflight for that single batch.
- If complete, run reconcile to produce queue-level copies.
- Run queue-level brand decision preflight.
- Only after product manifest dry-run and product DB apply gate pass, proceed to product/brand DB storage.

## References

- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- SQLAlchemy ORM select: https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
