# 2026-06-04 YOLO Section Dataset Gate

## Summary

- `supplement-yolo-section-dataset-gate-v1` gate를 추가해 영양제 상세 페이지 bbox annotation이 YOLO26 학습 데이터셋으로 넘어갈 수 있는지 판단하도록 했습니다.
- gate는 annotation preflight, template promotion summary, materialized dataset summary, optional dataset validation summary만 읽습니다.
- 원본 이미지, source ref, label row, OCR 원문, provider payload, DB row는 읽거나 출력하지 않습니다.

## Current Evidence

- Actual gate status: `blocked_by_annotation_review`
- Template rows: `205`
- Valid accepted rows: `0`
- Pending annotation rows: `205`
- Blank bbox rows: `205`
- Promoted items: `0`
- Materialized images: `0`
- Materialized labels: `0`
- Section YOLO training allowed now: `false`
- Model promotion allowed now: `false`

## Meaning

- 현재 YOLO26 학습 데이터셋 단계는 bbox 수동 검수가 끝나지 않아 차단됩니다.
- `yolo_section_annotation:001`부터 operator가 bbox를 채우고 `accepted_for_training`으로 승인해야 합니다.
- strict annotation preflight 통과 후에만 template promotion, dataset materialization, require-files validation, YOLO training 순서로 진행합니다.
- 모델 promotion은 학습과 별개로 metric gate가 통과하기 전까지 계속 차단합니다.

## Verification

- `pytest --no-cov` passed for `test_gate_supplement_yolo_section_dataset.py` and updated dependency audit tests: `13 passed`.
- `ruff check` passed for the new gate, dependency audit connection, and focused tests.
- Actual dry-run output was written to a local temp summary and returned `blocked_by_annotation_review`.
- Dependency audit now consumes the YOLO section dataset gate and reports `yolo_section_dataset -> blocked_by_annotation_review`.

## References

- Ultralytics detection dataset format: <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics detection task: <https://docs.ultralytics.com/tasks/detect/>
