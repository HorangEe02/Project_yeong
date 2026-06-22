# v2 ROI 검출기 + structured GT 벤치마크 → ROI-first 평가 → structured gate 분리 — 연결 절차

작성: 2026-06-08. 목적: text-F1 0.33의 precision scope-cap를 "scoping(ROI) + 지표 분리"로 해소(설계: `2026-06-08-text-f1-improvement-design.md`).

## 핵심 확인 (요청한 점검) — "OCR 이미지 수 증가"가 아니라 "section bbox/ROI 학습셋 + structured GT v2"인가?
- **그렇다(설계상).** v2 candidate pool은 단순 이미지 추가가 아니라:
  - 제품별 **GT-bearing 이미지 선택**(ingredient/intake 패널 탐지) + **하드케이스 오버샘플**(fragmented/long/low-signal),
  - 각 fixture에 **section bbox 슬롯**(ingredient_amounts/intake_method/supplement_facts/product_identity) + **structured GT 슬롯**,
  - **제품 단위 split**(누수 차단)로 설계됨.
- **단, 라벨은 아직 비어 있음(scaffold).** 실제 section bbox + structured GT는 **Stage 2~3(CLOVA 부트스트랩 + 사람 리뷰)** 에서 채워진다. 즉 "v2 구조/대상은 구축됨, 라벨 채움은 다음 게이트"가 정확한 상태.

## 전체 체인 (각 단계: 자동/사람/비용 표시)
| Stage | 작업 | 스크립트 | 상태 |
|---|---|---|---|
| 0 | v2 candidate pool(이미지 선택+스키마+split) | `build_supplement_benchmark_v2_candidate_pool.py` | ✅ 자동(완료) |
| 1 | PII screening 배치 생성 → 운영자 cleared | `build_supplement_pii_screening_review_bundle` → `export_supplement_operator_review_batch_files` → `apply_supplement_review_pii_screening_decisions --require-all-reviewed` | 자동 생성 / **사람 리뷰** |
| 2 | CLOVA teacher: per-field bbox+text → **8섹션 bbox 부트스트랩**(박스 기하 클러스터) + structured GT 초안 | `build_clova_ground_truth` (+ 신규 박스→섹션 매퍼) | **CLOVA 비용** |
| 3 | **section bbox review**(부트스트랩 박스 확인/수정) | `build_supplement_yolo_annotation_review_bundle` → Label Studio → `extract_supplement_yolo_reviewed_annotations` → `preflight_supplement_yolo_annotation_decisions --require-all-reviewed` → `promote_supplement_yolo_annotation_template` | **사람 리뷰(권한)** |
| 4 | **YOLO dataset gate** | `materialize_supplement_section_yolo_dataset` → `validate_supplement_section_yolo_dataset --require-files` → `gate_supplement_yolo_section_dataset` | 자동(권한 후) |
| 5 | **A100 section detector 학습** | `yolo detect train model=yolo26n.pt`(또는 PP-DocLayout_plus-L RT-DETR) | **A100** |
| 6 | **ROI-first PaddleOCR 평가** | (신규 구축 예정) `paddleocr_roi_first_eval.py` | ❌ **구축 필요** |
| 7 | **structured extraction gate 분리** | `build_supplement_structured_extraction_eval_summary.py` → `gate_supplement_structured_extraction_target.py` | ✅ **구축 완료** |
| — | 벤치마크 병합(203 frozen + new) + product-split | `build_supplement_ocr_benchmark_manifest` → `assign_paddleocr_benchmark_splits` | 자동 |

## Stage 7 — structured gate 분리 (완료, 실측)
char-LCS text gate(`gate_paddleocr_text_extraction_target`, 0.95)와 **별개**로, 필드 단위 추출을 게이팅:
- summary: `build_supplement_structured_extraction_eval_summary.py`(eval JSON + splits → holdout field_match macro/micro + ingredient_recall + 실패모드 카운트, redacted).
- gate: `gate_supplement_structured_extraction_target.py`(기본 target 0.90, ingredient_recall 0.85, min_fixtures 30 → `structured_target_reached`).
- **현 최적(p10) holdout 실측**: field_match_ratio_macro **0.486**, micro 0.475, ingredient_recall 0.466 → gate=`continue_extraction_improvement`(blockers: macro/micro/ingredient). 실패모드: field_zero 12, field<50% 22, ingredient_all_missed 21 (holdout 52 기준).
- 의미: 이 0.486을 **0.90**으로 올리는 것이 structured 목표(= ROI scoping이 직접 때리는 지표).

## Stage 6 — ROI-first 평가 (구축 설계, 다음 단계)
신규 `paddleocr_roi_first_eval.py`:
1. 입력: 평가 이미지 + **section boxes**(소스 택1: (a) 학습된 detector 추론, (b) CLOVA/GT bbox = oracle 상한 측정용).
2. 4 GT 섹션 box만 crop(+패드) → 각 crop에 PaddleOCR(det precision 프로파일: box_thresh↑/unclip↓) → 텍스트 concat.
3. 채점: **in-scope** char P/R/F1 + 필드 단위 field_match를 동시 산출(기존 eval과 동일 GT 정규화).
4. 출력: eval JSON(per_image + aggregate) → Stage 7 summary/gate에 그대로 투입.
> oracle 모드(CLOVA box로 crop)를 먼저 돌려 **달성가능 천장**을 확정한 뒤 detector 모드와 비교(detector 손실 분리).

## 데이터 역할 분리 (요청 구조 반영)
- **frozen v1 (203)**: 회귀 비교용 holdout. split 보존. recognizer/eval 회귀 추적.
- **new (~297)**: section **detector/ROI 학습셋**(bbox) + structured GT 확장. product-level split(train/val/test), 203 제품과 disjoint.
- **v2 (500)**: 병합 벤치마크(product-split 재산정). char full-text LCS GT는 별도 벤치마크에서만(혼용 금지).

## 권한/비용 게이트 (사용자 결정 필요)
- Stage 2 **CLOVA 비용**(~297 이미지 teacher pass) — 승인 필요.
- Stage 3 **section bbox 사람 리뷰** — 운영자 + 권한.
- Stage 5 **A100** — GPU(키 등록됨; 동시 실행 승인됨).
- Stage 6 코드는 비용/권한 없이 선구축 가능.

## redaction
모든 산출물: 해시/플래그/카운트/비율만. 원문 OCR·provider payload·절대/제품명 경로 금지. teacher-text는 운영자 승인 `datasets/`(gitignore)만. 프록시 OCR 텍스트는 선택에만 쓰고 폐기.
