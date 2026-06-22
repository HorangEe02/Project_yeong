# Supplement Operator Review Batch Files

Schema: `supplement-operator-review-batch-file-export-markdown-v1`

이 문서는 batch 파일명과 row range만 표시합니다. fixture id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로는 포함하지 않습니다.

- Batch file count: `18`
- Exported row count: `808`
- Next batch: `brand_product_review:001`

| Batch | Queue | Batch file | Source editable file | Start row | End row | Rows |
| --- | --- | --- | --- | ---: | ---: | ---: |
| brand_product_review:001 | brand_product_review | brand_product_review-001.jsonl | decisions.todo.jsonl | 1 | 50 | 50 |
| brand_product_review:002 | brand_product_review | brand_product_review-002.jsonl | decisions.todo.jsonl | 51 | 100 | 50 |
| brand_product_review:003 | brand_product_review | brand_product_review-003.jsonl | decisions.todo.jsonl | 101 | 150 | 50 |
| brand_product_review:004 | brand_product_review | brand_product_review-004.jsonl | decisions.todo.jsonl | 151 | 200 | 50 |
| brand_product_review:005 | brand_product_review | brand_product_review-005.jsonl | decisions.todo.jsonl | 201 | 250 | 50 |
| brand_product_review:006 | brand_product_review | brand_product_review-006.jsonl | decisions.todo.jsonl | 251 | 300 | 50 |
| brand_product_review:007 | brand_product_review | brand_product_review-007.jsonl | decisions.todo.jsonl | 301 | 350 | 50 |
| brand_product_review:008 | brand_product_review | brand_product_review-008.jsonl | decisions.todo.jsonl | 351 | 388 | 38 |
| review_pii_screening:001 | review_pii_screening | review_pii_screening-001.jsonl | decisions.todo.jsonl | 1 | 50 | 50 |
| review_pii_screening:002 | review_pii_screening | review_pii_screening-002.jsonl | decisions.todo.jsonl | 51 | 100 | 50 |
| review_pii_screening:003 | review_pii_screening | review_pii_screening-003.jsonl | decisions.todo.jsonl | 101 | 150 | 50 |
| review_pii_screening:004 | review_pii_screening | review_pii_screening-004.jsonl | decisions.todo.jsonl | 151 | 200 | 50 |
| review_pii_screening:005 | review_pii_screening | review_pii_screening-005.jsonl | decisions.todo.jsonl | 201 | 215 | 15 |
| yolo_section_annotation:001 | yolo_section_annotation | yolo_section_annotation-001.jsonl | annotation.todo.jsonl | 1 | 50 | 50 |
| yolo_section_annotation:002 | yolo_section_annotation | yolo_section_annotation-002.jsonl | annotation.todo.jsonl | 51 | 100 | 50 |
| yolo_section_annotation:003 | yolo_section_annotation | yolo_section_annotation-003.jsonl | annotation.todo.jsonl | 101 | 150 | 50 |
| yolo_section_annotation:004 | yolo_section_annotation | yolo_section_annotation-004.jsonl | annotation.todo.jsonl | 151 | 200 | 50 |
| yolo_section_annotation:005 | yolo_section_annotation | yolo_section_annotation-005.jsonl | annotation.todo.jsonl | 201 | 205 | 5 |

## Merge Rule

1. Batch JSONL은 operator-local working copy입니다.
2. 검수 완료 row를 큐별 원본 editable JSONL에 reconcile한 뒤 기존 queue preflight를 다시 실행합니다.
3. preflight가 통과하기 전에는 DB apply, OCR teacher transfer, YOLO dataset promotion을 진행하지 않습니다.
