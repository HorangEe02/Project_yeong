# Supplement Operator Review Batch Progress

Schema: `supplement-operator-review-batch-progress-preflight-v1`

이 문서는 operator decision/annotation 파일의 aggregate 진행률만 표시합니다. fixture id, 제품명, OCR 원문, provider payload, 이미지 경로, 로컬 경로는 포함하지 않습니다.

- Batch count: `18`
- Complete batch count: `0`
- Pending batch count: `18`
- Invalid batch count: `0`
- Next incomplete batch: `brand_product_review:001`

| Batch | Status | Valid | Blank | Pending | Invalid | Missing |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| brand_product_review:001 | pending | 0 | 50 | 0 | 0 | 0 |
| brand_product_review:002 | pending | 0 | 50 | 0 | 0 | 0 |
| brand_product_review:003 | pending | 0 | 50 | 0 | 0 | 0 |
| brand_product_review:004 | pending | 0 | 50 | 0 | 0 | 0 |
| brand_product_review:005 | pending | 0 | 50 | 0 | 0 | 0 |
| brand_product_review:006 | pending | 0 | 50 | 0 | 0 | 0 |
| brand_product_review:007 | pending | 0 | 50 | 0 | 0 | 0 |
| brand_product_review:008 | pending | 0 | 38 | 0 | 0 | 0 |
| review_pii_screening:001 | pending | 0 | 50 | 0 | 0 | 0 |
| review_pii_screening:002 | pending | 0 | 50 | 0 | 0 | 0 |
| review_pii_screening:003 | pending | 0 | 50 | 0 | 0 | 0 |
| review_pii_screening:004 | pending | 0 | 50 | 0 | 0 | 0 |
| review_pii_screening:005 | pending | 0 | 15 | 0 | 0 | 0 |
| yolo_section_annotation:001 | pending | 0 | 50 | 0 | 0 | 0 |
| yolo_section_annotation:002 | pending | 0 | 50 | 0 | 0 | 0 |
| yolo_section_annotation:003 | pending | 0 | 50 | 0 | 0 | 0 |
| yolo_section_annotation:004 | pending | 0 | 50 | 0 | 0 | 0 |
| yolo_section_annotation:005 | pending | 0 | 5 | 0 | 0 | 0 |

## Rule

1. 모든 batch가 `complete`가 되어도 큐별 정식 preflight를 다시 실행해야 합니다.
2. 정식 preflight의 blank/pending/invalid count가 0인 큐만 apply 또는 promotion으로 넘깁니다.
