# 섹션 검출기 학습 게이트 — 해소 런북 (2026-06-13)

> 목적: b32 평가가 지목한 병목(범용 텍스트 검출기)을 **전용 영양제 섹션 검출기**로 교체하기 위한, 운영자 차단점(205 bbox) → 배선까지의 정확한 경로. 코드 배선은 이미 완료(커밋 56022a1f) — 남은 건 **학습 게이트 해소**다.
> 근거: 권위 산출물(gate/preflight/audit JSON·MD)의 확인값만. 사적 이미지·원본 OCR 미열람.

## 0. 한 줄 결론

**2026-06-09 yolo26s 모델은 잠정 배선하지 말 것.** 게이트는 우회 불가 — 운영자 205건 주석 + 라벨 보강 + 재학습이 진짜로 필요하다. 코드 측은 모델만 통과되면 즉시 켤 수 있게 준비됨.

## 1. 현재 게이트 상태 (확인값)

| 항목 | 값 | 출처 |
|---|---|---|
| 게이트 상태 | `blocked_by_annotation_review` | yolo-section-dataset-gate.json:83 |
| 미검토 bbox | **205** (`pending_human_bbox_review`) | yolo-section-annotation-preflight.strict.json:19,43 |
| 수락된 bbox | **0** (`accepted_for_training`) | preflight.strict.json:28 |
| 다음 운영자 액션 | `complete_supplement_section_bbox_review` | preflight.strict.json:17 |
| 큐 파일 | `outputs/generated/supplement-learning/2026-06-05/operator-review/yolo-section-annotation-bundle/annotation.todo.jsonl` (628KB·205행) | gather |
| 이미지 | 번들 내 사적 해시 사본(`images/yolo-section/detail-yolo-*.{jpg,webp}`), `private_hashed_fixture_copy_materialized` | annotation.todo.jsonl |

PASS 조건: 205행 전부 `annotation_status=accepted_for_training` + `training_export_allowed=true` + `human_review_required=false`. 4개 ready 플래그(strict_annotation/template_promotion/dataset_materialization/dataset_validation) 전부 true여야 학습 허용.

## 2. 왜 2026-06-09 모델을 잠정 배선하지 않는가 (확인값)

8개 라벨 전부 노출 → `_validate_model_class_contract` **로드는 통과**한다. 그러나 품질이 배선을 무의미하게 만든다:

| 지표 | 값 | 게이트/베이스라인 |
|---|---:|---|
| val mAP50 | **0.2349** | promotion 0.70 |
| holdout no-box fixtures | **27/52 (51.9%)** | — |
| holdout에서 한 번도 예측 안 된 클래스 | **4/8** (precautions·allergen_warning·intake_method·other_ingredients) | failure-analysis.json:25-39 |
| structured eval — full-image | macro **0.6002** | 현 베이스라인 |
| structured eval — detector ROI-first | macro **0.5119** | **full-image보다 나쁨** |

핵심: ROI-first가 full-image보다 **나쁘다**(0.5119 < 0.6002, improvement-plan.md:31-32). 51.9%는 박스가 없어 어차피 full-image로 폴백된다. 즉 지금 배선하면 **OCR 품질을 떨어뜨리고 지연만 추가**한다. → 잠정 배선 가치 없음.

## 3. 해소 경로 (운영자, 단계별)

> ⚠️ 1~2단계는 **사적 이미지 위 수동 작업** = 운영자 전용. Claude는 수행 불가.

1. **205 bbox 주석** — `annotation.todo.jsonl` 각 행에 8-class bbox 작성(번들 `README.md` 절차). 8-class 정규 순서(class_id 0–7): `product_identity·supplement_facts·ingredient_amounts·precautions·allergen_warning·intake_method·other_ingredients·functional_claims` (retraining.py:33-42). YOLO 포맷 `class_id x_center y_center w h`(정규화 0–1).
   - **라벨 보강 최소치**(improvement-plan §Phase1, recall 회복 전제): `other_ingredients` train≥100/val≥20/test≥20, `intake_method` train≥120/val≥25/test≥25(+홀드아웃 가시 패널 20+), `precautions`·`allergen_warning` val/test≥20씩. 현 지원량(other_ingredients 42/1/2 등)으론 recall 추정 불가.
2. **상태 전환** — 각 행 `accepted_for_training` + `training_export_allowed=true` + `human_review_required=false`.
3. **preflight 재실행** — `rerun_yolo_annotation_preflight_require_all_reviewed`가 205행 전부 전환됐는지 검증(전환 전엔 실패).
4. **export → materialize → validate** (외부 호출 0, 명령은 §4):
   - export 생성(`build_supplement_section_yolo_detection_export`, schema `supplement-section-yolo-detect-export-v1`, retraining.py:26,267) — `training_export_allowed=false` 행 있으면 RetrainingSecurityError.
   - `materialize_…`(운영자 사적 source-map 필요) → image/label 파일 생성.
   - `validate_… --require-files` → 8개 필수 라벨·파일쌍·정규화 행 검증.
5. **데이터셋 게이트** — `gate_supplement_yolo_section_dataset.py`로 4 ready 플래그 PASS 확인.
6. **재학습(A100)** — improvement-plan §Phase3 순서 고정: **`yolov8s.pt` 먼저**(imgsz 1280, epochs 150, patience 30, batch 0.70), `yolo26s.pt`는 동일 데이터 paired 비교로만. **300-epoch no-early-stop 금지**(곡선이 epoch 175 이후 악화 — improvement-plan.md:28-30,88).
7. **검출기 promotion 게이트** — val mAP50≥0.70 · `ingredient_amounts`/`supplement_facts` recall≥0.85 · `other_ingredients` recall≥0.65(지원 val/test≥20) · holdout no-box≤10% · `ingredient_amounts` presence≥80% · `intake_method` presence≥65% (improvement-plan §Phase4).
8. **배선(코드 0)** — 게이트 통과 모델 `best.pt`로:
   ```
   VISION_CLASSIFIER_MODEL=<best.pt 경로>
   ENABLE_VISION_CLASSIFIER=true
   OCR_ROI_PREPROCESSING_POLICY=crop_before_primary
   ```
   운영 활성화는 docs/17 §9 **게이트 #2 승인** 필요(`validate_runtime_security`). `/ready`의 `section_roi_model_configured`(커밋 56022a1f)가 stock가 아닌 모델 배선 여부를 가시화한다.

## 4. 정확한 명령 (검증된 CLI)

```bash
# 4-1 materialize (운영자 사적 source-map)
python backend/scripts/materialize_supplement_section_yolo_dataset.py \
  --export <export.json> --source-map <source_map.json> --dataset-yaml <dataset.yaml>

# 4-2 validate (require-files 계약)
python backend/scripts/validate_supplement_section_yolo_dataset.py <dataset.yaml> --require-files

# 4-3 데이터셋 게이트
python backend/scripts/gate_supplement_yolo_section_dataset.py \
  --annotation-preflight <preflight.json> \
  --template-promotion-summary <promotion.json> \
  --dataset-materialize-summary <materialize.json> \
  --dataset-validation-summary <validation.json> \
  --output <gate.json> --markdown-output <gate.md>

# 4-4 학습 (A100, plan §Phase3 권장 = yolov8s 먼저)
python backend/scripts/train_ultralytics_section_detector.py \
  --data <dataset.yaml> --model yolov8s.pt --project <runs_dir> --name sec_v3_yolov8s \
  --imgsz 1280 --epochs 150 --patience 30 --batch 0.70 --device 0 --workers 2

# 4-4 (대안) Windows A100 detached 런처
python backend/scripts/a100_section_detector_spawn_detached.py \
  --base G:\lemon-aid\section_dataset_v3 --python <env python> \
  --model yolov8s.pt --name sec_v3_yolov8s --imgsz 1280 --epochs 150 --patience 30 \
  --batch 0.70 --workers 2 --min-free-mib 52000
```
원격(A100 155.230.153.222) 실행·사적 데이터 전송은 **사용자 승인 후**. 원본 dataset(`rec_dataset\v2`) 불가침.

## 5. 참조

- 개선 플랜(권위, official-doc 근거): `outputs/generated/…/reconciled/a100-section-detector-structured-eval-20260609/2026-06-09-section-detector-structured-extraction-improvement-plan.md`
- 코드 배선 결정: [2026-06-13 OCR 결정 §6](2026-06-13-ocr-benchmark-required-section-decision.md) (커밋 020a35d4), 코드 커밋 56022a1f.
- 2026-06-09 모델 `best.pt`: `outputs/generated/…/datasets/a100-section-detectors/2026-06-09-yolo26s-300ep-noearly-52g-b070-pyspawn-v2/best.pt`(promotion blocked).
