# yolo_section_annotation:003

Schema: `supplement-operator-review-workpack-markdown-v1`

이 파일은 redacted operator workpack입니다. row id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로를 포함하지 않습니다.

## Batch

- Queue: `yolo_section_annotation`
- Batch file: `yolo_section_annotation-003.jsonl`
- Batch review CSV: `none`
- Source editable file: `annotation.todo.jsonl`
- Row range: `101-150`
- Pending rows: `50`

## Source Bundle Files

- `annotation.todo.jsonl`
- `annotation-index.html`
- `README.md`

## Queue Guide

- `상세 페이지 section bbox annotation batch입니다.`
- `allowed label만 사용해 원본 이미지 기준 normalized xywh bbox를 채웁니다.`
- `OCR 원문, provider payload, 로컬 경로는 label snapshot에 저장하지 않습니다.`

## Decision Schema Guide

- Decision object:
  - `label_snapshot`
- Allowed decisions:
  - `accepted_annotation`
  - `needs_annotation`
  - `skip_unusable_image`
- Required fields:
  - `supported_section_labels_only`
  - `normalized_xywh_boxes`
  - `training_export_allowed_after_review`
- Required approval attestations:
  - `boxes_checked_against_image`
  - `labels_checked_against_allowed_taxonomy`
  - `no_raw_ocr_or_provider_payload_copied`
- Allowed reason codes:
  - `supplement_facts`
  - `ingredient_amounts`
  - `intake_method`
  - `precautions`
  - `other_ingredients`
  - `product_identity`
- Invalid if:
  - `unsupported_label_present`
  - `box_coordinates_outside_normalized_range`
  - `relative_or_absolute_local_path_leaked`

## Checklist

- `draw_required_section_bbox`
- `use_supported_section_labels_only`
- `set_training_export_allowed_after_review`
- `do_not_export_until_preflight_passes`

## Completion Rule

1. Batch JSONL을 검수합니다.
2. Reconcile 도구로 queue-level copy를 생성합니다.
3. reviewed-only extract를 실행해 blank stub이 섞인 전체 queue와 부분 YOLO dataset preview 입력을 분리합니다.
4. Batch progress preflight와 YOLO annotation preflight를 다시 실행합니다.
5. YOLO annotation preflight 통과 전에는 dataset promotion이나 training export를 진행하지 않습니다.
