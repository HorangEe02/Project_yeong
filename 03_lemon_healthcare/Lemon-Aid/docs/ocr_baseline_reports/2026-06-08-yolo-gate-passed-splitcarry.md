# YOLO section dataset gate PASSED (split-carry fix) — 2026-06-08

Stage 3 체인이 실제 사람 박스 + 제품-split로 **게이트 통과**.

## split-carry 보강
- 문제: 템플릿→LS→export→extract 라운드트립에서 v2 product-split 유실 → promote가 전부 train(val/test 0) → validate 실패/게이트 차단.
- 수정: `inject_v2_split_into_promote_template.py` — v2 candidate 매니페스트(candidate_id→v2_split)에서 split 재부착. promote가 `row["split"]` 사용.

## 결과 (현재 운영자 23 fixtures)
- inject: 23/23 매칭 → **train 11 / val 3 / test 9** (제품-split, 누수 없음).
- materialize ok(23 img, proper splits) → validate ok(23/23) → preflight `--require-all-reviewed` → `ready_for_strict_promotion: True`.
- **GATE: `ready_for_section_yolo_training_dataset`, `section_yolo_training_allowed_now: True`.**

## 의미
- 전체 Stage 3→게이트 체인이 실주석으로 완전 검증 + 통과. 데이터셋이 A100 detector 학습에 적격(기술적).
- 단 23장은 PoC 규모 — 강한 detector/0.90엔 주석 확대 권장. 더 많은 export가 오면 동일 turnkey 흐름(convert→extract→**inject-split**→preflight strict→promote→materialize→validate→gate)으로 재실행.

## 다음
주석 확대 → 위 흐름 재실행(게이트 통과) → **A100 detector 학습** → `build_roi_first_oracle_bundle`에 진짜 detector/사람 박스 입력으로 ROI-first 재평가 → `gate_supplement_structured_extraction_target`(0.90).
