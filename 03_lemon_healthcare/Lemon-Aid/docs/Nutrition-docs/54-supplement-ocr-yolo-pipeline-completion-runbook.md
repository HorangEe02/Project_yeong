# Lemon-Aid 영양제 OCR/YOLO 학습 파이프라인 — 상태 검증 + 잔여 작업 실행 플랜

## Context
영양제 라벨 OCR/YOLO 학습 파이프라인(PaddleOCR 텍스트 추출 95% 목표)은 **인프라가 이미 완성**되어 있고, 병목은 자동화가 아니라 **사람 검토 게이트**다. 사용자 요청은 ① "완료"로 기재된 항목을 실제 상태와 대조 검증, ② 현재 상태 파악, ③ 상태에 맞는 상세 구현(실행) 플랜 md 작성, ④ PII screening(215)·YOLO annotation(205) 사람 검토 완료 + 권한 부여 후 OCR benchmark gate·YOLO dataset gate를 "확인 후 적용"이다.

이 문서는 그 실행 런북이다. **새로 구현할 코드는 없음**(26개 파이프라인 스크립트 + 양 게이트 전부 존재·정상 차단 확인). 잔여 작업은 (A) 운영자 사람 검토 → (B) 기존 스크립트 자동 실행 → (C) 게이트 통과 검증이다.

확정된 실행 방향(사용자 답변):
- **검토 완료 + 권한 부여 후 = 전체 post-review 체인 + 양 게이트를 내가 자동 실행하고 통과 증거 리포트.**
- **Teacher-OCR = PaddleOCR 로컬 단독** (Google Vision/CLOVA 외부 OCR 미사용 → 외부 opt-in 불필요, 외부로 이미지 전송 없음). 95% 게이트는 PaddleOCR 출력 vs 사람 정답(GT) 비교로 동작.

경로 기준: repo 루트 = `Lemon-Aid/`. 실행은 repo 루트에서 `backend/.venv/bin/python backend/scripts/<x>.py ...` (생성된 체크리스트가 repo-relative 경로로 명령을 발급). `outputs/`는 **repo 루트** 아래(주의: backend/outputs 아님). 운영 디렉터리: `outputs/generated/supplement-learning/2026-06-05/operator-review/`.

---

## Part 1 — 상태 검증 결과 ("완료" 주장 대조)

권위 소스: `outputs/.../operator-review/supplement-learning-completion-audit.json` (14요건: **8 verified / 3 pending / 3 blocked**, `overall_status=in_progress_blocked_by_missing_evidence`, `total_blank_row_count=420`) + 라이브 DB 읽기 전용 재검증.

| 사용자 "완료" 주장 | 검증 결과 | 증거 |
|---|---|---|
| 영양제 카테고리 43개 DB 매칭 | ✅ 일치 | 라이브 DB `supplement_categories` **active=43**; readiness `matched_category_count=43, missing=0` |
| 브랜드/제품 387 매핑 | ✅ 일치 | DB `supplement_products` source=`crawling_image_auto` **387**, product-category mapping **387**, missing 0 (36 brands, manufacturer null 14) |
| taxo59 food 59 + nutrition 59 | ✅ 일치 | DB `food_catalog_items=60`(59 taxo59 + 1 manual), `food_nutrition=59` |
| PII screening gate / 사전 OCR 차단 | ✅ 일치 | requirement `review_image_ground_truth_privacy_gate=pending`, `ocr_benchmark_gate:blocked_by_pii_screening` |
| YOLO section bbox gate | ✅ 일치 | `yolo-section-dataset-gate.json status=blocked_by_annotation_review, training_allowed=false, pending=205` |
| PaddleOCR 95% gate 분리 | ✅ 일치 | `gate_paddleocr_text_extraction_target.py` 존재, 정책 `stop_training_only_if_95_percent_target_reached` |
| workpack에 visual index/image count 추가 | ✅ **일치(직접 확인)** | `workpack/review_pii_screening-001.md` L22-27, `workpack/yolo_section_annotation-001.md` L23-28 에 "## Visual Review Index" + HTML index + 215/205 image count 실재 |
| 관련 테스트/ruff 통과 | ⚠️ 실행 재확인 필요 | 파이프라인 테스트 ~178개 존재(사용자 "5+30"은 focused 부분집합). 실행 단계에서 재실행 권장 |

**결론: 미진행으로 잘못 기재된 항목 없음.** "완료" 주장은 전부 실제 상태와 일치(visual index 포함 — 초기 탐색의 "누락" 보고는 오탐이었고 직접 확인 시 실재). 26개 참조 스크립트 전부 존재. 미완 항목은 사용자가 "남은 작업"으로 정확히 기술한 사람 검토 병목과 그 하류뿐.

**부수 발견(비차단, 정리 후보):**
- `supplement_categories` = **all 53 / active 43**. 메모리상 lowercase 중복 10건은 삭제되었어야 하나 현재 10건이 inactive로 잔존(active=43은 정확, 파이프라인 영향 없음). 선택적 정리 대상.
- 테스트 총수는 ~178개로 사용자 표기(5+30)보다 많음(문제 아님, focused 집합 표기).

---

## Part 2 — 현재 상태 요약

- **8 verified**: 구조 audit, taxonomy staging(431행), brand/product DB import(387), category seed preflight/verify, taxonomy DB import verify, private-image tracking guard, privacy/safety controls.
- **3 pending(사람 검토)**: `review_image_ground_truth_privacy_gate`(PII 215, 5배치), `detail_page_yolo_bbox_annotation`(YOLO 205, 5배치), `section_yolo_dataset_ready`.
- **3 blocked(하류)**: `manual_ocr_ground_truth`(PII 후), `teacher_ocr_paddleocr_comparison`(→ PaddleOCR-local로 축소), `paddleocr_training_loop_ready`(GT+benchmark 후).
- 현재 blocker batch: `review_pii_screening:001`(blank 50). 큐 총 blank: PII 215, YOLO 205.

병목은 두 개의 독립 사람 검토 큐. 각 큐 완료 후 자동화 체인이 게이트까지 이어진다.

---

## Part 3 — 잔여 작업: 두 개의 사람-게이트 체인

각 단계에 **[사람]** = 운영자 검토 / **[자동:나]** = 검토 완료 후 내가 실행 표시. 명령은 생성된 체크리스트(`operator-next-command-checklist.md`, repo-relative)가 권위 소스이며, 큐가 바뀌면 재생성된다.

### Chain A — PII screening → OCR benchmark gate → PaddleOCR 95% (PaddleOCR 로컬 단독)
근거: `operator-next-command-checklist.md`(18-step) / `operator-post-completion-command-plan.md`(17-step).

1. **[사람]** `batches/review_pii_screening-001.jsonl` … `-005.jsonl`의 215행 채움. 각 행 `pii_screening_decision` ∈ {`cleared_no_personal_data`,`contains_personal_data`,`needs_review`} + 필수 attestation(`attest_local_screening_completed`/`attest_no_personal_data_visible`/`attest_no_raw_text_copied`/`attest_teacher_ocr_transfer_allowed`) + reason_codes. **시각 검토는 `review-pii-screening-bundle/review-index.html`로만**, 원문/경로/payload 복사 금지.
2. **[자동:나]** 배치별 `preflight_supplement_operator_review_batch_file.py`(complete 확인) → `reconcile_supplement_operator_review_batch_files.py`(reconciled 큐 사본, source 미덮어쓰기) → `preflight_supplement_operator_review_batch_progress.py`(큐 진행 확인).
3. **[자동:나]** `extract_supplement_pii_reviewed_decisions.py`(reviewed/blank 분리) → `preflight_supplement_review_pii_screening_decisions.py --require-all-reviewed`(**strict: blank/pending/invalid 0이어야 통과**) → `apply_supplement_review_pii_screening_decisions.py --require-all-reviewed`(teacher-safe candidate manifest 발행, OCR 호출 없음).
4. **[자동:나]** `export_supplement_ocr_ground_truth_template.py`(PII-cleared 행으로 GT 템플릿) → `build_supplement_ocr_ground_truth_review_bundle.py`(편집용 bundle).
5. **[사람]** `ocr-ground-truth-review-bundle/ground-truth.todo.jsonl`에 각 cleared 이미지의 **정답 라벨 텍스트** 입력(필수 섹션: ingredient_amounts/intake_method/precautions/allergen_warnings). 시각 검토 bundle 사용, 원문 복사 규칙 준수.
6. **[자동:나]** `preflight_supplement_ocr_ground_truth_manifest.py`(GT 완성 확인) → `build_supplement_ocr_benchmark_manifest.py`(human-reviewed benchmark fixtures) → `assign_paddleocr_benchmark_splits.py`(product-hash 그룹 leakage-safe split).
7. **[자동:나 — 게이트 #1]** `gate_supplement_ocr_benchmark.py --require-ready-for-teacher-ocr-eval` (pii-preflight + GT bundle summary + GT preflight + benchmark summary + split summary 모두 검사). **통과 = `ready_for_teacher_ocr_eval`.**
8. **[자동:나]** `collect_supplement_ocr_observations.py --providers paddleocr_local` (**로컬만 — 외부 미호출 → 외부 opt-in 불필요**) → `merge_paddleocr_text_observations_into_benchmark.py`(redacted, no-raw-merge).
9. **[자동:나]** `preflight_paddleocr_text_target_chain.py --eval-split holdout --min-fixtures 30` → `build_paddleocr_text_extraction_eval_summary.py --provider paddleocr_local --eval-split holdout --leakage-check-passed --privacy-review-cleared`.
10. **[자동:나 — 게이트 #2 / 95% stop-gate]** `gate_paddleocr_text_extraction_target.py --min-fixtures 30`. 정책 `stop_training_only_if_95_percent_target_reached`. **≥95% → 목표 달성·학습 중단. <95% → 추가 학습/평가 루프**(`paddleocr_training_loop_ready` 요건의 finetune plan/improvement triage 단계).

### Chain B — YOLO section bbox annotation → YOLO dataset gate
근거: 존재 확인된 스크립트 `build_supplement_yolo_annotation_review_bundle` / `preflight_supplement_yolo_annotation_decisions` / `extract_supplement_yolo_reviewed_annotations` / `promote_supplement_yolo_annotation_template` / `materialize_supplement_section_yolo_dataset` / `validate_supplement_section_yolo_dataset` / `gate_supplement_yolo_section_dataset`.

1. **[사람]** `batches/yolo_section_annotation-001.jsonl` … `-005.jsonl`의 205행 채움. 각 행 `label_snapshot` = allowed section label(supplement_facts/ingredient_amounts/intake_method/precautions/allergen_warning/other_ingredients/product_identity) + **normalized xywh bbox** + `training_export_allowed_after_review` + attestation. 시각 검토는 `yolo-section-annotation-bundle/annotation-index.html`(또는 label-studio-tasks.json)로.
2. **[자동:나]** `reconcile_supplement_operator_review_batch_files.py`(YOLO 큐 포함 reconcile) → `preflight_supplement_operator_review_batch_progress.py`.
3. **[자동:나]** `extract_supplement_yolo_reviewed_annotations.py`(reviewed/blank 분리) → `preflight_supplement_yolo_annotation_decisions.py --require-all-reviewed`(**strict**) → `promote_supplement_yolo_annotation_template.py`(export artifact + source-map).
4. **[자동:나]** `materialize_supplement_section_yolo_dataset.py`(train/val/test 이미지·라벨 + dataset.yaml) → `validate_supplement_section_yolo_dataset.py --require-files`(contract + 라벨 taxonomy 검증).
5. **[자동:나 — 게이트 #3]** `gate_supplement_yolo_section_dataset.py`(annotation completeness + promotion + materialization + validation 집계). **통과 = `ready_for_section_yolo_training_dataset`, `section_yolo_training_allowed_now=true`.**

> 정확한 인자/경로: PII 큐 완료 후 `build_supplement_operator_next_command_checklist.py` 와 `build_supplement_operator_post_completion_command_plan.py` 를 **재생성**하면 현재 blocker(=YOLO)에 맞는 repo-relative 명령이 발급된다. 실행 시 그 생성물을 신뢰원천으로 사용.

---

## Part 4 — "확인 후 적용"할 게이트 (권한 부여 후)

| 게이트 | 스크립트 | 선행조건 | 통과 신호 |
|---|---|---|---|
| OCR benchmark gate | `gate_supplement_ocr_benchmark.py --require-ready-for-teacher-ocr-eval` | PII strict preflight + 수동 GT preflight + benchmark manifest + split 전부 ready | `ocr-benchmark-gate.json` status=`ready_for_teacher_ocr_eval` |
| (PaddleOCR 95% stop-gate) | `gate_paddleocr_text_extraction_target.py --min-fixtures 30` | PaddleOCR-local eval summary(holdout, ≥30 fixtures, privacy-cleared) | ≥95% → stop/done, <95% → 루프 |
| YOLO dataset gate | `gate_supplement_yolo_section_dataset.py` | YOLO strict preflight + promote + materialize + validate | `yolo-section-dataset-gate.json` status=`ready_for_section_yolo_training_dataset` |

적용 절차: 운영자 검토 완료 신호 → 해당 체인의 [자동:나] 단계 순차 실행 → 게이트 실행 → 게이트 JSON status·blocker_codes(빈 배열)·`*_allowed_now=true` 를 증거로 리포트. 어느 strict preflight라도 실패하면 중단하고 미완 행을 보고(자동 우회·auto-fill 금지).

---

## Part 5 — 제약·정책 (반드시 유지)
- **프라이버시**: outputs에 raw OCR 텍스트·provider payload·로컬/절대 경로·source ref·제품 폴더 literal 저장 금지(redaction scan이 거부). DB write·외부 호출은 이 런북 범위 밖(게이트가 차단).
- **외부 OCR 미사용**(이번 결정): `collect_supplement_ocr_observations`는 `--providers paddleocr_local`로만. `allow_external_ocr`/external opt-in env 불필요. (향후 외부 teacher 비교를 원하면 별도 opt-in + 자격증명 단계로 분기.)
- **PaddleOCR 목표 95%**: stop-gate가 유일한 종료 조건. 미달이면 학습/평가 루프 반복.
- **strict preflight**: PII·YOLO 모두 `--require-all-reviewed`로 **전 행 검토 필수**(부분 통과 없음). 사람 검토·attestation 없이는 게이트가 구조적으로 통과 불가 → 내가 PII 판정/ bbox 작성/ GT 전사를 대신할 수 없음(설계상 사람 필수).

---

## Part 6 — 검증 (실행 단계에서)
1. **DB 재검증(읽기 전용)**: `supplement_categories` active=43, `supplement_products`(crawling_image_auto)=387, `food_catalog_items`=60, `food_nutrition`=59 — 모두 통과 확인됨(재실행 가능).
2. **게이트 통과 증거**: 각 게이트 JSON의 `status`/`blocker_codes`([])/`*_allowed_now` 필드를 인용.
3. **completion audit 재생성**: `build_supplement_learning_completion_audit.py` 재실행 → 14요건 중 verified 증가 + `overall_status` 전이 확인.
4. **테스트/품질**: 실행 단계에서 workpack-focused + operator-regression(+ ocr/yolo/paddleocr 게이트 테스트) pytest 재실행. pyproject `addopts`가 `--cov`를 강제하므로 `-o addopts="-q"` override로 대상 테스트만 빠르게 확인. ruff clean + `git diff --check` 유지.
5. **커밋**: 사용자 요청 시에만. 사용자 OCR/security WIP는 명시 경로로만 add.

---

## Part 7 — 이번 턴 산출물 / 다음 행동
- 이번 턴: 이 플랜 md(런북). 게이트는 검토 미완으로 어차피 blocked → 실행 없음.
- 실행 단계(승인 + 사람 검토 + 게이트 권한 부여 후): Chain A → 게이트 #1·#2, Chain B → 게이트 #3 전체 자동 실행 + 증거 리포트.
- (선택) 이 플랜을 repo 내부에도 둘 경우 제안 위치: `Lemon-Aid/docs/Nutrition-docs/` 또는 `outputs/generated/supplement-learning/2026-06-05/operator-review/`. 승인 시 사본 배치.
