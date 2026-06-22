# Stage 3 체인 end-to-end 검증 — 실제 사람 박스로 게이트까지 (2026-06-08)

운영자가 Label Studio에서 일부(23 fixtures) bbox를 그려 export → 전체 자동 체인을 실제 박스로 통과시킴.

## 입력 (운영자 export)
- `project-3-at-2026-06-08-01-16-…json`: 23 fixtures, 95 boxes.
- 라벨 분포: ingredient_amounts 36, supplement_facts 16, product_identity 13, precautions 3, allergen_warning 2, intake_method 2.

## 체인 실행 결과 (전 단계 정상)
| 단계 | 스크립트 | 결과 |
|---|---|---|
| convert | `convert_label_studio_yolo_annotations` | 23 fixtures / 95 boxes (percent→normalized, fixture_id 조인) ✓ |
| extract | `extract_supplement_yolo_reviewed_annotations` | accepted_for_training 23, pending 286 무시 ✓ |
| promote | `promote_supplement_yolo_annotation_template` | 23 promoted ✓ |
| materialize | `materialize_supplement_section_yolo_dataset` | 23 img/label, schema ok ✓ (PoC: split 미전달로 전부 train) |
| validate | `validate_supplement_section_yolo_dataset --require-files` | ok ✓ |
| **gate** | `gate_supplement_yolo_section_dataset` | **status=`blocked_by_annotation_review`, training_allowed_now=False** ✓(정상 차단) |

## 결론
- **체인이 실제 사람 박스로 end-to-end 검증됨** — 모든 스크립트가 v2 번들+실주석에서 동작.
- **게이트가 올바르게 차단**: 23/309만 리뷰 → 학습 금지(strict 안전장치 정상 동작).
- 통합 중 해결한 이슈: source_ref `#`→safe-token, category NFD→NFC, GT키 매핑, LS 이미지 서빙(localhost CORS), materialize는 dataset.yaml 선존재 필요 + dest-exists 비멱등.

## 다음 (게이트 통과 → 학습)
1. **운영자 주석 확대**: 더 많은 fixture(이상적으로 309 또는 게이트 임계 이상) bbox 확정 + 제품-split 유지(현 PoC는 split 미전달로 train 편중 → 실행 시 split 전달 보강 필요).
2. 재실행: convert→…→**gate 통과(ready_for_section_yolo_training_dataset)**.
3. **A100 detector 학습** → `build_roi_first_oracle_bundle`에 **진짜 detector/사람 박스** 입력으로 ROI-first 재평가 → `gate_supplement_structured_extraction_target`(0.90).

## 보조 도구(이번에 추가, 운영자 작업 단축)
- `serve_annotation_images`(CORS static, localhost:8090) — LS 이미지 서빙.
- `label-studio-tasks.http.json` — LS import용(이미지 http URL + ingredient pre-fill 282건).
- 향후: split을 promote-template까지 전달하도록 어댑터 보강(현재 train 편중 회피) + ingredient 토큰박스→영역 자동병합(선택).

> 모든 데이터 산출물(datasets/·reconciled/)은 gitignore. 본 문서만 커밋.
