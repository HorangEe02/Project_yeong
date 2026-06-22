# Brand Reviewed Decision Extract

## Summary

- `extract_supplement_brand_reviewed_decisions.py`를 추가했습니다.
- 목적은 operator batch reconcile 이후 전체 brand decision queue에 blank stub이 남아 있어도, reviewed-only JSONL을 별도로 추출해 부분 manifest preview 흐름을 안전하게 유지하는 것입니다.
- strict DB import gate는 변경하지 않았습니다. 제품/브랜드/product-category DB 저장은 여전히 전체 brand review strict preflight가 통과해야만 열립니다.

## Actual Current Run

- Input queue: `brand_product_review.reconciled.jsonl`
- Brand candidates: `388`
- Input decision rows: `388`
- Reviewed decision rows: `0`
- Blank decision rows ignored: `388`
- Unmatched decision rows: `0`
- Ready for partial apply: `false`
- Ready for strict apply: `false`
- DB write performed: `false`
- OCR/LLM/provider call performed: `false`

## Follow-up Verification

- Extracted reviewed-only file was accepted by brand decision preflight as a controlled pending state.
- `apply_supplement_brand_review_decisions.py` accepted the empty reviewed-only file and produced an empty product import manifest summary with `pending_count=388`.
- This confirms the current all-blank operator queue no longer has to be passed directly into apply. It can be reduced to reviewed-only input first, without auto-approving or hiding pending work.

## Safety Notes

- The extractor fails closed on non-blank invalid decisions.
- Duplicate fixture decisions and stale unmatched fixture ids are rejected.
- Output summaries are aggregate-only and do not include fixture ids, product names, product folder literals, OCR text, provider payloads, image paths, or local absolute paths.

## Tests

- `cd backend && .venv/bin/python -m ruff check scripts/extract_supplement_brand_reviewed_decisions.py Nutrition-backend/tests/unit/scripts/test_extract_supplement_brand_reviewed_decisions.py`
- `cd backend && .venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_extract_supplement_brand_reviewed_decisions.py`
