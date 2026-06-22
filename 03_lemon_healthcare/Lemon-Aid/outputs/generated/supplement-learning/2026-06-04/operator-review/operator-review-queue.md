# Supplement Operator Review Queue

Schema: `supplement-operator-review-queue-markdown-v1`

이 문서는 redacted summary만 기반으로 합니다. 원본 이미지, OCR 원문, provider payload, 로컬 경로, 제품 폴더 literal은 포함하지 않습니다.

- Queue count: `3`
- Pending operator action count: `808`
- Next queue: `brand_product_review`

| Queue | Status | Total | Pending | Blank | Valid | Next action |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| brand_product_review | pending_operator_review | 388 | 388 | 388 | 0 | complete_operator_brand_review |
| review_pii_screening | pending_operator_review | 215 | 215 | 215 | 0 | complete_operator_pii_review |
| yolo_section_annotation | pending_operator_review | 205 | 205 | 205 | 0 | complete_supplement_section_bbox_review |

## Safe Next Steps

1. 각 local review bundle에서 사람이 decision 또는 bbox를 채웁니다.
2. 해당 preflight를 다시 실행해 invalid/blank/pending count가 0인지 확인합니다.
3. 통과한 queue만 apply 또는 promotion 스크립트로 다음 artifact를 생성합니다.
4. 전체 readiness report를 다시 생성해 downstream gate 상태를 갱신합니다.
