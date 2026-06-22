# 2026-06-04 YOLO Reviewed Annotation Extract

## Summary

- `supplement-yolo-reviewed-annotation-extract-v1` 도구를 추가해 blank bbox stub이 섞인 전체 YOLO annotation queue에서 검토 완료 row만 분리할 수 있게 했습니다.
- 출력 JSONL은 원본 annotation template 옆에만 쓸 수 있도록 제한했습니다. 이는 downstream promotion이 private relative fixture refs를 그대로 검증해야 하기 때문입니다.
- CLI summary/stdout은 source ref, image path, label, OCR 원문, provider payload, local absolute path를 출력하지 않습니다.
- strict YOLO dataset gate는 완화하지 않았습니다. reviewed-only output은 부분 dataset preview 입력 분리용이며, 전체 학습 허용은 여전히 strict gate가 판단합니다.

## Current Evidence

- Actual extraction status: `ok`
- Template rows: `205`
- Input annotation rows: `205`
- Reviewed annotation rows: `0`
- Blank annotation ignored rows: `205`
- Missing annotation rows: `0`
- Unmatched annotation rows: `0`
- Partial promotion ready: `false`
- Strict promotion ready: `false`

## Workpack / Work Order Integration

- `yolo_section_annotation` post-completion gates에 `extract_reviewed_yolo_annotations_for_partial_dataset_preview`를 추가했습니다.
- YOLO workpack Markdown completion rule에 reviewed-only extract와 partial YOLO dataset preview 분리 단계를 추가했습니다.
- 현재 next batch는 여전히 `brand_product_review:001`이므로 current work order에는 brand gate가 표시됩니다.
- YOLO batch가 next batch로 선택되면 work-order test 기준 새 extract gate가 표시됩니다.

## Safety Rules

- DB write 없음.
- OCR provider call 없음.
- LLM call 없음.
- Training 실행 없음.
- Source image read는 fixture SHA-256 integrity check 목적으로만 수행합니다.
- Summary/stdout에는 source ref, image path, label, local path, OCR/provider payload를 출력하지 않습니다.

## Verification

- Focused pytest: `29 passed`
- Focused ruff: `All checks passed`
- `git diff --check`: passed
- Actual reviewed-only dry-run: reviewed row `0`, blank ignored `205`, partial/strict promotion `false`
- Current operator workpack regeneration: `status=ok`, batch count `18`, workpack file count `19`

## References

- Ultralytics detection dataset format: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics detection task: <https://docs.ultralytics.com/tasks/detect/>
