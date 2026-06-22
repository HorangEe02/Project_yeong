# 2026-06-02 현재 섹션 작업 및 GitHub 게시 상태

## 범위

- 작업 repo: `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 브랜치: `docs/docs-2026-05-31-backend-ocr-security`
- 팀 원격: `origin -> https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
- 개인 원격: `personal -> https://github.com/HorangEe02/Project_yeong.git`
- 이번 섹션 Git 작업은 팀 원격 `origin`만 대상으로 한다.

## 현재까지 완료한 핵심 작업

### OCR/성분 후보 보정

- `Warning`, `Allergy Information`, `Contains ...` 계열 문장을 `precautions` layout evidence로 분류하도록 보강했다.
- `1회 제공량(26g)`, `Serving Size`, `Amount Per Serving` 계열 serving metadata가 성분 후보로 들어오는 오탐을 제거했다.
- 실제 성분명과 함량이 있는 문장은 유지하면서 serving-size fragment만 제외되도록 회귀 테스트를 추가했다.

### Supplement Section YOLO26 준비

- 영양제 섹션 detector class 계약을 `supplement_facts`, `precautions`, `intake_method`, `ingredients`로 고정했다.
- 음식 YOLO 또는 COCO 기본 모델을 영양제 섹션 detector로 잘못 쓰지 않도록 class-name guard를 추가했다.
- section YOLO dataset YAML, validator, export bridge, materializer를 추가해 human-reviewed bbox annotation 이후 학습 데이터로 연결할 수 있는 구조를 만들었다.
- 현재 상태는 training-ready pipeline 계약까지이며, 실제 custom supplement YOLO26 model 학습은 아직 완료되지 않았다.

### OCR Layout 후보와 Annotation Review Queue 연결

- OCR layout section 후보를 raw OCR text 없이 normalized section bbox snapshot으로 변환하는 helper를 추가했다.
- 검수 전 후보는 `training_export_allowed=false`, `human_review_required=true`, `coordinate_space=ocr_page`로 생성되며 training export에서 거부된다.
- `AnnotationTask.learning_image_object_id`를 추가해 consent-gated learning image source가 있는 분석 건을 pending review task로 enqueue할 수 있게 했다.
- 같은 learning image source의 active `supplement_roi_box` task가 있으면 중복 생성하지 않는다.

### Privacy/Safety 기준

- API/operator output에는 raw OCR, provider payload, local image path, object URI, owner hash, source ref를 노출하지 않는 기준을 유지했다.
- `LearningImageObject` 삭제/철회 흐름에서 `AnnotationTask.learning_image_object_id`도 scrub 대상에 포함했다.
- reviewer-approved source image 좌표와 export flag가 있는 snapshot만 YOLO 학습 export로 승격될 수 있도록 fail-closed guard를 유지했다.

## 최근 게시된 커밋

- `cc5c819 feat(learning): derive supplement section YOLO labels from OCR layout`
- `a95d56a docs(todo): record current OCR YOLO handoff`
- `5865afb feat(learning): gate supplement section annotation export`
- `299b380 docs(todo): record annotation source link analysis`
- `136be3f feat(learning): enqueue supplement section review tasks`

## 검증 기록

- backend focused tests: `77 passed`
- ruff focused check: `All checks passed!`
- `git diff --check`: clean
- `git diff --cached --check`: clean
- changed tracked files 대상 `detect-secrets scan`: clean

## 이번 문서 커밋에서 제외할 항목

다음 untracked 항목은 이번 문서 정리와 무관하므로 stage하지 않는다.

- `.omc_probe_1780240220778875000.txt`
- `data/nutrition_reference/crawling-image/`
- `data/nutrition_reference/sample-image/`
- `frontend/public/`
- `frontend/src/app/tech/`
- `mobile/assets/app_icon/Mascot_AppIcon_Rebuild_Assets/`
- `mobile/scripts/select_naver_gallery_samples.py`
- `mobile/uiux/LemonAid_Mascot_AppIcon_Rebuild_Assets/`
- `mobile/uiux/logo/`
- `outputs/todo-list/2026-05-31/*`
