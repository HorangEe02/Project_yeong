# brand_product_review:006

Schema: `supplement-operator-review-workpack-markdown-v1`

이 파일은 redacted operator workpack입니다. row id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로를 포함하지 않습니다.

## Batch

- Queue: `brand_product_review`
- Batch file: `brand_product_review-006.jsonl`
- Batch review CSV: `brand_product_review-006.review.csv`
- Source editable file: `decisions.todo.jsonl`
- Row range: `251-300`
- Pending rows: `50`

## Source Bundle Files

- `decisions.todo.jsonl`
- `review-index.html`
- `README.md`
- `review.csv`

## Queue Guide

- `브랜드 및 제품명 검수 batch입니다.`
- `review index 또는 CSV를 보고 manufacturer와 product가 라벨 또는 안전한 catalog 근거로 확인되는지 판단합니다.`
- `제품 폴더 literal을 manufacturer로 그대로 쓰지 않습니다.`

## Decision Schema Guide

- Decision object:
  - `brand_review_decision`
- Allowed decisions:
  - `approve`
  - `reject`
  - `needs_review`
  - `not_a_brand`
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
- Allowed reason codes:
  - `reviewed_label_or_catalog`
  - `not_brand`
  - `unclear_brand`
  - `duplicate_product`
  - `needs_catalog_lookup`
  - `unsafe_text`
  - `category_mismatch`
  - `low_confidence_folder_name`
- Invalid if:
  - `free_text_notes_present`
  - `local_path_or_url_literal_present`
  - `raw_ocr_or_provider_payload_copied`
  - `folder_literal_used_without_review`

## Checklist

- `fill_reviewed_manufacturer`
- `fill_reviewed_product_name`
- `set_approve_or_reject_decision`
- `keep_db_import_attestation_explicit`

## Completion Rule

1. Batch JSONL을 검수합니다.
2. Reconcile 도구로 queue-level copy를 생성합니다.
3. reviewed-only extract를 실행해 blank stub이 섞인 전체 queue와 부분 manifest preview 입력을 분리합니다.
4. Batch progress preflight와 brand decision preflight를 다시 실행합니다.
5. strict preflight 통과 전에는 product DB import manifest나 DB apply를 진행하지 않습니다.
