# review_pii_screening:003

Schema: `supplement-operator-review-workpack-markdown-v1`

이 파일은 redacted operator workpack입니다. row id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로를 포함하지 않습니다.

## Batch

- Queue: `review_pii_screening`
- Batch file: `review_pii_screening-003.jsonl`
- Batch review CSV: `none`
- Source editable file: `decisions.todo.jsonl`
- Row range: `101-150`
- Pending rows: `50`

## Source Bundle Files

- `decisions.todo.jsonl`
- `review-index.html`
- `README.md`

## Queue Guide

- `review 이미지 PII screening batch입니다.`
- `검수용 이미지만 보고 개인 정보 노출 여부를 판정합니다.`
- `텍스트 원문이나 보이는 개인 정보를 notes에 복사하지 않습니다.`

## Decision Schema Guide

- Decision object:
  - `pii_screening_decision`
- Allowed decisions:
  - `cleared_no_personal_data`
  - `contains_personal_data`
  - `needs_review`
- Required fields:
  - `reviewer_id_operator_prefix`
  - `reviewed_at_safe_token`
  - `reason_codes`
- Required approval attestations:
  - `attest_local_screening_completed`
  - `attest_no_personal_data_visible`
  - `attest_no_raw_text_copied`
  - `attest_teacher_ocr_transfer_allowed`
- Allowed reason codes:
  - `no_personal_data_visible`
  - `face_or_person_visible`
  - `contact_or_address_visible`
  - `account_or_identifier_visible`
  - `unclear_image`
- Invalid if:
  - `visible_text_copied_into_notes`
  - `local_path_or_url_literal_present`
  - `raw_ocr_or_provider_payload_copied`

## Checklist

- `inspect_hashed_fixture_image`
- `set_pii_screening_decision`
- `use_operator_prefixed_reviewer_id`
- `do_not_copy_visible_text_into_notes`

## Completion Rule

1. Batch JSONL을 검수합니다.
2. Reconcile 도구로 queue-level copy를 생성합니다.
3. reviewed-only extract를 실행해 blank stub이 섞인 전체 queue와 부분 teacher OCR preview 입력을 분리합니다.
4. Batch progress preflight와 PII decision preflight를 다시 실행합니다.
5. PII strict preflight 통과 전에는 teacher OCR transfer나 benchmark manifest 생성을 진행하지 않습니다.
