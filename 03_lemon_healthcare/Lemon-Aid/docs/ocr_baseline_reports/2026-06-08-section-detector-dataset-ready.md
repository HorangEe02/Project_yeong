# Section detector 데이터셋 완성 + YOLO gate 통과 (실주석 305) — 2026-06-08

운영자가 Label Studio에서 거의 전량 bbox 주석 → 전체 체인 통과.

## 데이터셋 (gitignored datasets/)
- export: 307 fixtures, 3,530 boxes.
- extract: accepted_for_training 305, pending 4(무박스).
- split (product-level, 누수 없음): **train 216 / val 32 / test 57**.
- 라벨 분포: ingredient_amounts 1259, supplement_facts 878, product_identity 491, functional_claims 352, precautions 230, intake_method 142, allergen_warning 139, other_ingredients 16.
- materialize/validate ok(305 img/labels). **GATE: ready_for_section_yolo_training_dataset, training_allowed_now=True.**
- dataset.yaml: `…/datasets/supplement-section-roi-v2/section-dataset/dataset.yaml` (8 classes, train/val/test).

## 다음
A100(또는 로컬) YOLO detect 학습(model=yolo26n/yolov8n) → best.pt → `build_roi_first_oracle_bundle`에 detector 박스 입력으로 holdout ROI-first 재평가 → `gate_supplement_structured_extraction_target`(0.90).
