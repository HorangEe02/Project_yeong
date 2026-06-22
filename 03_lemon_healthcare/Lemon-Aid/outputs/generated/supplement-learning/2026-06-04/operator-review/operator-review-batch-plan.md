# Supplement Operator Review Batch Plan

Schema: `supplement-operator-review-batch-plan-markdown-v1`

이 문서는 redacted summary만 기반으로 합니다. 원본 이미지, OCR 원문, provider payload, 로컬 경로, 제품 폴더 literal은 포함하지 않습니다.

- Batch size: `50`
- Batch count: `18`
- Pending operator action count: `808`
- Next queue: `brand_product_review`

| Batch | Queue | Editable file | Start row | End row | Pending rows |
| --- | --- | --- | ---: | ---: | ---: |
| brand_product_review:001 | brand_product_review | decisions.todo.jsonl | 1 | 50 | 50 |
| brand_product_review:002 | brand_product_review | decisions.todo.jsonl | 51 | 100 | 50 |
| brand_product_review:003 | brand_product_review | decisions.todo.jsonl | 101 | 150 | 50 |
| brand_product_review:004 | brand_product_review | decisions.todo.jsonl | 151 | 200 | 50 |
| brand_product_review:005 | brand_product_review | decisions.todo.jsonl | 201 | 250 | 50 |
| brand_product_review:006 | brand_product_review | decisions.todo.jsonl | 251 | 300 | 50 |
| brand_product_review:007 | brand_product_review | decisions.todo.jsonl | 301 | 350 | 50 |
| brand_product_review:008 | brand_product_review | decisions.todo.jsonl | 351 | 388 | 38 |
| review_pii_screening:001 | review_pii_screening | decisions.todo.jsonl | 1 | 50 | 50 |
| review_pii_screening:002 | review_pii_screening | decisions.todo.jsonl | 51 | 100 | 50 |
| review_pii_screening:003 | review_pii_screening | decisions.todo.jsonl | 101 | 150 | 50 |
| review_pii_screening:004 | review_pii_screening | decisions.todo.jsonl | 151 | 200 | 50 |
| review_pii_screening:005 | review_pii_screening | decisions.todo.jsonl | 201 | 215 | 15 |
| yolo_section_annotation:001 | yolo_section_annotation | annotation.todo.jsonl | 1 | 50 | 50 |
| yolo_section_annotation:002 | yolo_section_annotation | annotation.todo.jsonl | 51 | 100 | 50 |
| yolo_section_annotation:003 | yolo_section_annotation | annotation.todo.jsonl | 101 | 150 | 50 |
| yolo_section_annotation:004 | yolo_section_annotation | annotation.todo.jsonl | 151 | 200 | 50 |
| yolo_section_annotation:005 | yolo_section_annotation | annotation.todo.jsonl | 201 | 205 | 5 |

## Completion Rule

1. 배치별 row range를 사람이 검수합니다.
2. 큐별 preflight를 다시 실행해 blank/pending/invalid count가 0인지 확인합니다.
3. preflight가 통과한 큐만 다음 apply 또는 promotion 단계로 넘깁니다.
