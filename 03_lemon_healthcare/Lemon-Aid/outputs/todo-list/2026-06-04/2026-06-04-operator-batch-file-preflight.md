# 2026-06-04 Operator Batch File Preflight

## Summary

- Operator-local batch JSONL 1개를 직접 검증하는 preflight를 추가했습니다.
- 목적은 사람이 `brand_product_review:001` 같은 작은 batch를 채운 직후, 전체 queue reconcile 전에 완료 여부를 빠르게 확인하는 것입니다.
- 이 preflight는 DB write, OCR/LLM 호출, source image 읽기를 수행하지 않습니다.
- 출력은 aggregate count만 포함하고 fixture id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로를 포함하지 않습니다.

## Current Result

- Batch: `brand_product_review:001`
- Queue: `brand_product_review`
- Status: `pending`
- Ready for reconcile: `false`
- Expected rows: `50`
- Actual rows: `50`
- Valid rows: `0`
- Blank rows: `50`
- Pending rows: `0`
- Invalid rows: `0`
- Missing rows: `0`
- Extra rows: `0`
- Reason: `blank_decision=50`

## Why This Matters

- 기존 batch progress preflight는 queue-level decision/annotation 파일을 대상으로 동작합니다.
- 이번 preflight는 operator가 batch 파일 하나를 채운 직후 바로 검증할 수 있어, 잘못된 row count나 blank decision을 reconcile 전에 잡습니다.
- batch가 `complete`가 되어도 바로 DB apply로 가지 않고, 반드시 reconcile, queue-level preflight, downstream gate를 다시 실행합니다.

## Next Steps

- `brand_product_review:001`의 50개 decision을 채웁니다.
- row count를 batch plan과 동일하게 유지합니다.
- batch file preflight를 다시 실행해 `complete` 상태를 확인합니다.
- complete 후 batch reconcile, operator batch progress preflight, brand decision preflight, product DB apply gate 순서로 진행합니다.

## References

- Ultralytics detect dataset format: https://docs.ultralytics.com/datasets/detect/
- Ultralytics detect task: https://docs.ultralytics.com/tasks/detect/
- PaddleOCR pipeline: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- Google Vision OCR: https://cloud.google.com/vision/docs/ocr
- Naver CLOVA OCR: https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
- SQLAlchemy ORM select: https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
