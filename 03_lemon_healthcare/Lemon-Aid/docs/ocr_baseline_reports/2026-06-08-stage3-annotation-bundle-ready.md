# Stage 3 — section bbox 주석 번들 준비 완료 (운영자 리뷰 시작 가능)

작성: 2026-06-08. v2 후보 → 사람 bbox 리뷰(Label Studio) 번들 구축 + ingredient 부트스트랩 pre-fill 완료.

## 산출물 (gitignored datasets/ — teacher 파생)
`outputs/.../datasets/supplement-section-roi-v2/annotation-bundle/`:
- `annotation-index.html` — 운영자 시각 리뷰 인덱스
- `label-studio-tasks.json` — **309 태스크, 282개에 ingredient bbox 예측 pre-fill**(1,461 박스)
- `annotation-images/` — 309 materialized 이미지(해시 픽스처)
- `annotation.todo.jsonl`, `summary.json`, `README.md`

## 파이프라인 (신규 어댑터 2개 + 기존 체인)
1. **adapter(신규)** `build_supplement_v2_yolo_annotation_candidates.py`: v2 후보(297 ingredient + 12 intake = 309) → `supplement-detail-page-yolo-annotation-candidate-v1`. `image_ref_hash=sha256(crawl상대경로)`, sha 무결성 검증, category NFC 정규화(macOS NFD 대응), source_ref safe-token.
2. `export_supplement_yolo_annotation_template.py`(기존): 309 materialize + 템플릿(0 skip).
3. `build_supplement_yolo_annotation_review_bundle.py`(기존): 309 Label Studio 태스크.
4. **injector(신규)** `inject_supplement_yolo_bbox_predictions.py`: teacher `section_bboxes_yolo` → LS predictions(282/309). 운영자는 그리는 대신 **확인/보정**.

## 운영자 작업 (사람 게이트 — 권한 필요)
- Label Studio에 `label-studio-tasks.json` import(또는 `annotation-index.html` 사용).
- 8섹션(`product_identity, supplement_facts, ingredient_amounts, precautions, allergen_warning, intake_method, other_ingredients, functional_claims`) bbox 확정:
  - **ingredient_amounts**: pre-fill된 산발 박스를 **전체 표 영역으로 병합/조정**(현 박스는 토큰 단위).
  - **intake_method**: pre-fill 거의 없음(코퍼스 희소) → 직접 그리기.
  - empty 27 태스크: 처음부터 그리거나 제외 판정.

## 이후 체인 (운영자 리뷰 완료 후, 자동)
`extract_supplement_yolo_reviewed_annotations` → `preflight_supplement_yolo_annotation_decisions --require-all-reviewed`(strict) → `promote_supplement_yolo_annotation_template` → `materialize_supplement_section_yolo_dataset` → `validate_supplement_section_yolo_dataset --require-files` → **`gate_supplement_yolo_section_dataset`**(통과=ready_for_section_yolo_training_dataset) → **A100 detector 학습** → **진짜 박스로 ROI-first 재평가**(`build_roi_first_oracle_bundle`에 사람 박스 입력) → **structured gate**(`gate_supplement_structured_extraction_target`, 목표 0.90).

## 주의
- pre-fill 박스는 **토큰 단위(보조용)** — 최종 라벨 아님. 운영자가 영역으로 정리.
- bundle은 teacher 파생 이미지 포함 → gitignored. 본 문서 + 스크립트만 커밋.
- 실행 환경: detached 셸은 `set -a; . .env; set +a` 필요(CLOVA/DB env). 이번 번들 단계는 CLOVA 불필요(이미 teacher 보유).
