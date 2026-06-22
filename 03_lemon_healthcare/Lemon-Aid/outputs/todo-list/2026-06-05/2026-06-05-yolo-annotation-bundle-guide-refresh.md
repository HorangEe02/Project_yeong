# 2026-06-05 - YOLO section annotation bundle guide refresh

## Summary

- Detail-page YOLO section annotation remains pending human bbox review.
- The local annotation bundle was refreshed so reviewers can see the normalized
  `xywh` box schema and the section class guide before editing
  `annotation.todo.jsonl`.
- The refreshed preflight still fails closed: no accepted boxes exist yet, and
  YOLO dataset training is not allowed.

## Updated Artifacts

| Artifact | Status |
| --- | --- |
| `outputs/generated/supplement-learning/2026-06-05/operator-review/yolo-section-annotation-bundle/README.md` | Includes bbox schema example and section guide |
| `outputs/generated/supplement-learning/2026-06-05/operator-review/yolo-section-annotation-bundle/annotation-index.html` | Includes bbox format and section guide |
| `outputs/generated/supplement-learning/2026-06-05/operator-review/yolo-section-annotation-bundle/annotation.todo.jsonl` | Includes `box_schema_example` and `section_label_guide` |
| `outputs/generated/supplement-learning/2026-06-05/operator-review/yolo-section-annotation-preflight.json` | Pending human bbox review |
| `outputs/generated/supplement-learning/2026-06-05/operator-review/yolo-section-dataset-gate.json` | Blocked by annotation review |

## Current Gate State

| Field | Value |
| --- | ---: |
| Reviewable rows | 205 |
| Pending bbox rows | 205 |
| Accepted bbox rows | 0 |
| Invalid rows | 0 |
| Training allowed now | false |

## Safety

- No DB write was performed.
- No OCR provider call was performed.
- No LLM call was performed.
- No training job was started.
- Raw OCR text, provider payloads, local absolute paths, and product folder
  literals were not added to public summaries.

## Next Step

Human reviewers still need to draw section boxes for the detail-page images and
set accepted rows before promotion/materialization can run.

## Official References

- Ultralytics detection dataset format: https://docs.ultralytics.com/datasets/detect/
- Ultralytics detect task: https://docs.ultralytics.com/tasks/detect/
