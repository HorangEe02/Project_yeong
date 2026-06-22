# 2026-06-04 Learning Dependency Audit

## Summary

- `supplement-learning-dependency-audit-v1` audit를 추가해 현재 operator review batch와 gate 결과를 목표별로 연결했습니다.
- audit는 redacted summary만 읽습니다. 원본 row, 제품명, OCR 원문, provider payload, 이미지 경로, 로컬 경로는 읽거나 출력하지 않습니다.
- 목적은 전체 next batch 하나만 보는 것이 아니라, DB import/OCR benchmark/YOLO dataset 각각이 어떤 queue에 막혔는지 분리해 보는 것입니다.

## Current Evidence

- Status: `blocked_by_operator_review`
- Batch count: `18`
- Pending batch count: `18`
- Total blank rows: `808`

| Outcome | Gate status | Allowed now | Blocking queue | Next batch |
| --- | --- | --- | --- | --- |
| `product_catalog_db_import` | `blocked_by_operator_review` | `false` | `brand_product_review` | `brand_product_review:001` |
| `ocr_teacher_benchmark` | `blocked_by_pii_screening` | `false` | `review_pii_screening` | `review_pii_screening:001` |
| `yolo_section_dataset` | `blocked_by_annotation_review` | `false` | `yolo_section_annotation` | `yolo_section_annotation:001` |

## Recommended Operator Sequence

- `brand_product_review:001`
- `review_pii_screening:001`
- `yolo_section_annotation:001`

## Meaning

- 카테고리/브랜드 DB import는 brand/product review가 먼저 끝나야 합니다.
- CLOVA/Google Vision teacher OCR benchmark는 review image PII screening이 먼저 끝나야 합니다.
- YOLO26 section dataset promotion은 section bbox annotation review가 먼저 끝나야 합니다.
- PaddleOCR 학습은 teacher OCR 비교와 별도 baseline/promotion gate 전까지 계속 차단합니다.

## Verification

- `ruff check` passed for the dependency audit, connected gate/progress/work order scripts, and focused tests.
- `pytest --no-cov` passed for focused dependency/gate/progress/work order tests: `27 passed`.
- Actual audit output: `blocked_by_operator_review`.

## References

- PaddleOCR OCR pipeline: <https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html>
- Google Cloud Vision OCR: <https://cloud.google.com/vision/docs/ocr>
- NAVER Cloud CLOVA OCR API: <https://api.ncloud-docs.com/docs/en/ai-application-service-ocr>
- Ultralytics detection dataset format: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics detection task: <https://docs.ultralytics.com/tasks/detect/>
