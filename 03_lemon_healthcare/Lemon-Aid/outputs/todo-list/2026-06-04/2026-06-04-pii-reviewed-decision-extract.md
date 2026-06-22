# PII Reviewed-Only Decision Extract

## 목적

- `review_pii_screening` queue도 `brand_product_review`와 동일하게 mixed queue에서 reviewed row만 분리할 수 있도록 했습니다.
- operator batch reconcile 이후 전체 queue에 blank stub이 남아 있어도, 검수된 일부 row만 PII apply와 teacher OCR preview로 넘길 수 있게 하기 위한 단계입니다.
- strict PII screening gate는 완화하지 않습니다.

## 구현 내용

- `extract_supplement_pii_reviewed_decisions.py`를 추가했습니다.
- 입력은 PII candidate manifest와 operator decision JSONL입니다.
- blank decision stub은 counted ignored로 처리합니다.
- non-blank invalid, duplicate, stale/unmatched row는 fail-closed로 중단합니다.
- 출력 summary는 aggregate-only이며 DB write, OCR provider call, PaddleOCR training, source image read를 수행하지 않았음을 명시합니다.

## 실제 현재 상태

- 실제 PII candidate row는 215개입니다.
- reconciled PII queue 입력 decision row도 215개입니다.
- reviewed decision은 0개입니다.
- blank decision ignored는 215개입니다.
- partial apply와 strict apply 모두 아직 준비되지 않았습니다.

## Downstream No-op 검증

- reviewed-only output이 비어 있을 때 PII preflight는 `complete_operator_pii_review` 상태로 유지됩니다.
- PII apply는 pending 215개, teacher OCR allowed 0개로 안전하게 no-op 처리됩니다.
- 따라서 operator가 일부 row를 채운 뒤에는 reviewed-only extract 결과만 downstream에 넣을 수 있고, 아직 비어 있는 row는 teacher OCR transfer로 넘어가지 않습니다.

## 보안/품질 메모

- 제품명, 리뷰 원문, 이미지 경로, provider payload, 로컬 절대 경로는 문서와 CLI summary에 포함하지 않습니다.
- source doc URL은 명시 citation 용도로만 유지하고, PII applier의 unsafe URL 검사에는 포함하지 않도록 별도 안전 검사 wrapper를 사용했습니다.
- 이는 문서 출처 표시와 operator-facing redaction 정책을 동시에 만족시키기 위한 처리입니다.
