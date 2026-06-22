# 2026-06-02 작업 문서 인덱스

> 작성 기준: 2026-06-02 섹션 작업
> 범위: 모바일 분석 결과 그룹화, 서버 응답 점검, 네트워크 오류 처리 보완, OCR/YOLO 섹션 ROI 보완, 검증 및 GitHub 브랜치 푸시

---

## 문서 목록

- `2026-06-02-analysis-result-grouping-summary.md`
  - 여러 장의 영양제 이미지 분석 결과를 제품 단위로 묶는 모바일 결과 화면 변경 요약
  - 전면 라벨과 성분표 라벨이 분리 분석될 때 하나의 영양제로 보여주는 기준 정리

- `2026-06-02-server-runtime-response-check.md`
  - backend runtime이 실제로 살아 있는지 확인한 health/readiness/API 점검 기록
  - 모바일 base URL과 `/api/v1` prefix 혼동 가능성 정리

- `2026-06-02-server-network-hardening-summary.md`
  - Android emulator Host header 허용 기본값 보완
  - Flutter API client의 socket/client network failure 사용자 메시지 정규화
  - backend/mobile 단위 테스트 추가 사항 정리

- `2026-06-02-verification-and-git-publish.md`
  - 이번 커밋에 포함한 파일, 제외한 파일, 검증 명령, 커밋/푸시 기준 정리

- `2026-06-02-ocr-yolo-precaution-analysis.md`
  - 주의사항/알레르기 문구가 OCR 결과에 안정적으로 반영되지 않는 원인 조사 기록
  - YOLO ROI taxonomy, 다중 ROI OCR, OCR page merge, serving-size 오탐 후보를 분리해서 정리

- `2026-06-02-ocr-yolo-next-implementation-plan.md`
  - 코드 수정 전 설계 검토 결과와 다음 구현 순서
  - 테스트/검증 명령, 제외해야 하는 데이터, 공식 문서 기준 정리

- `2026-06-02-ocr-yolo-section-roi-implementation-summary.md`
  - 영양제 라벨 섹션 ROI taxonomy 확장, OCR page merge 보존, serving-size 오탐 제거 구현 요약
  - Ultralytics 공식 문서 기준과 custom section model 필요 조건 정리

- `2026-06-02-precaution-anchor-serving-fragment-followup.md`
  - 단수 `Warning`, 알레르기 정보, `Contains <allergen>` ROI가 `precautions` layout evidence로 잡히도록 보강한 내용
  - `1회 제공량(26g)` 줄 깨짐/앞뒤 텍스트 혼합 케이스가 성분 후보로 들어오지 않도록 회귀 테스트 추가

- `2026-06-02-ocr-yolo-section-roi-verification.md`
  - backend unit/ruff/regression/parser 직접 재현 검증 결과
  - 실제 Ultralytics runtime smoke가 막힌 이유와 다음 작업 정리

- `2026-06-02-yolo26-gemma-supplement-vision-design.md`
  - YOLO26 custom 영양제 섹션 detector와 Ollama/Gemma 검증/설명 파이프라인 설계
  - OCR layout `precautions` fallback 구현, 자체 설계 점검, 남은 blocker 정리

- `2026-06-02-ollama-vision-verification-summary.md`
  - local Ollama/Gemma vision model이 OCR 텍스트를 이미지와 직접 대조하는 structured verification 계약 구현 요약
  - `match | partial | mismatch | uncertain`, 필수 섹션 누락, backend warning 연결 및 검증 결과 정리

- `2026-06-02-supplement-analysis-profile-context-summary.md`
  - 영양제 OCR 분석 미리보기 설명에 사용자 최신 건강 프로필 snapshot을 opt-in으로 연결한 작업 요약
  - `sensitive_health_analysis` 동의 gate, sanitized profile bucket, audit flag, 회귀 테스트 결과 정리

- `2026-06-02-supplement-analysis-medical-context-summary.md`
  - 영양제 OCR 분석 미리보기 설명에 사용자 질환/복약 DB 요약 bucket을 opt-in으로 연결한 작업 요약
  - 원문 질환명/약명/용량을 LLM에 전달하지 않는 safe medical context, consent gate, audit flag 정리

- `2026-06-02-current-section-git-publish-summary.md`
  - 현재 섹션에서 완료한 OCR/YOLO/Ollama/사용자 context 작업과 GitHub 푸시 상태 정리
  - 다음 섹션에서 이어갈 custom supplement YOLO26 detector blocker와 안전 규칙 정리

- `2026-06-02-yolo26-model-readiness-check.md`
  - 현재 repo에 존재하는 YOLO 관련 모델/데이터를 점검한 결과 정리
  - 음식 YOLO 가중치와 영양제 섹션 detector를 혼동하지 않기 위한 다음 구현 기준 정리

- `2026-06-02-yolo26-model-contract-guard-summary.md`
  - COCO/food/label-only 모델이 영양제 섹션 detector로 잘못 사용되지 않도록 model class-name guard를 추가한 작업 요약
  - `/ready`에 안전한 supplement YOLO 계약 정보를 노출한 내용과 검증 결과 정리

- `2026-06-02-supplement-section-yolo-dataset-contract.md`
  - 영양제 섹션 YOLO26 custom detector 학습 전 dataset YAML과 validator를 추가한 작업 요약
  - `supplement_facts`, `precautions`, `intake_method`, `ingredients` class 계약과 annotation 준비 전 blocker 정리

- `2026-06-02-supplement-section-yolo-export-bridge.md`
  - privacy-reviewed annotation manifest를 supplement section YOLO 학습 export로 변환하는 bridge 추가 요약
  - semantic bbox label을 고정 class id로 변환하고 numeric-only/whole-label bbox를 거부하는 기준 정리

- `2026-06-02-supplement-section-yolo-materializer.md`
  - supplement section YOLO export artifact와 operator-only source map을 실제 Ultralytics image/label 디렉터리로 변환하는 작업 요약
  - source ref/path를 stdout에 노출하지 않고 생성 후 validator를 통과시키는 기준 정리

- `2026-06-02-current-ocr-yolo-training-pipeline-handoff.md`
  - OCR 주의사항 누락 보완부터 supplement section YOLO dataset/export/materializer까지 현재 섹션 전체 흐름 요약
  - 다음 섹션에서 이어갈 human-reviewed bbox annotation, YOLO26 학습, crop OCR, Gemma verification blocker 정리

- `2026-06-02-github-branch-publish-log.md`
  - 현재 브랜치, team remote, 이미 push된 commit, 이번 문서 커밋 대상과 제외 파일 기준 정리
  - GitHub push 전후 확인해야 할 명령과 privacy/Git 규칙 정리

- `2026-06-02-supplement-section-layout-candidate-snapshot.md`
  - OCR layout의 absolute section bbox를 YOLO normalized section label snapshot으로 변환하는 helper 추가 요약
  - raw OCR text 없이 기존 supplement section YOLO export bridge에 연결되는지 검증한 내용 정리

- `2026-06-02-current-work-final-publish-summary.md`
  - 2026-06-02 섹션에서 완료한 OCR/YOLO/Ollama/개인화 context 작업과 현재 GitHub 게시 상태 정리
  - 이번 문서 커밋 대상, 제외 파일, 다음 blocker, 공식 문서 링크 정리

- `2026-06-02-next-section-continuation-prompt.md`
  - 다음 Codex 섹션에서 이어서 사용할 수 있는 repo/branch/remote/검증/규칙/다음 구현 순서 프롬프트
  - AnnotationTask review queue 연결과 training export guard 구현 방향 정리

- `2026-06-02-supplement-section-annotation-review-guard.md`
  - OCR layout 기반 YOLO section 후보를 pending `AnnotationTask` 계약으로 만드는 helper와 검수 전 export 차단 guard 구현 요약
  - `MediaObject` source 연결이 없는 상태에서 service insert를 보류한 이유와 다음 schema/service 작업 정리

- `2026-06-02-annotation-source-link-analysis.md`
  - `MediaObjectStore`와 `LearningImageObjectStore`의 source 연결 차이를 확인한 분석 기록
  - `AnnotationTask.learning_image_object_id` 추가 방향, privacy scrubber, service enqueue guard, 다음 검증 기준 정리

- `2026-06-02-annotation-learning-source-enqueue-summary.md`
  - `AnnotationTask.learning_image_object_id` migration/ORM/service 연결 구현 요약
  - learning consent가 열린 경우에만 OCR layout 후보를 pending review task로 enqueue하고 중복 task를 막는 기준 정리

- `2026-06-02-current-session-status-and-publish.md`
  - 현재 섹션에서 완료한 OCR/YOLO/Ollama/AnnotationTask 작업과 GitHub 게시 상태 정리
  - 이번 문서 커밋에서 제외해야 할 untracked 항목과 검증 기록 정리

- `2026-06-02-next-work-todo.md`
  - accepted `AnnotationTask`를 `LearningDatasetItem`으로 승격하는 다음 구현 TODO 정리
  - human-reviewed bbox, YOLO26 학습, crop OCR, Gemma/Ollama verification, 모바일 UI 후속 작업 정리

- `2026-06-02-annotation-task-dataset-promotion.md`
  - accepted `supplement_roi_box` task를 `LearningDatasetItem`으로 승격하는 operator CLI 구현 요약
  - reviewer-approved source image bbox만 YOLO training export로 넘어가도록 검증/중복/source guard를 추가한 내용 정리

---

## 현재 핵심 상태

- `AnalysisResultScreen`은 다중 이미지 분석 결과를 단순 이미지 탭이 아니라 영양제 단위 탭으로 묶어 표시한다.
- 제품명/제조사만 있는 전면 이미지와 성분표만 있는 이미지가 같은 영양제로 이어지는 경우, 성분 후보와 누락 섹션을 병합해 보여준다.
- Android/iOS에서 이전 분석 결과를 새 분석 결과로 오해하지 않도록, 탭 개수와 표시 라벨이 제품 단위로 정리되는 테스트를 추가했다.
- backend는 `/health`, `/ready`, `/api/v1/dashboard/summary` 기준으로 응답을 다시 확인했다.
- Android emulator 기본 Host인 `10.0.2.2`를 backend 개발 기본 allowlist에 포함했다.
- Flutter API client는 `SocketException`과 `http.ClientException`을 `network_unavailable` 오류로 정규화해 사용자에게 backend 실행 상태/API 주소 확인 메시지를 보여준다.
- 이번 Git 작업은 팀 repo `Lemon-Aid-KDT/Lemon-sin.git`의 현재 브랜치 `docs/docs-2026-05-31-backend-ocr-security`에 커밋/푸시한다.
- OCR/YOLO 추가 조사에서는 코드 변경 전 원인 분석을 우선 진행했으며, 주의사항 누락과 `1회 제공량(26g)` 성분 후보 오탐은 서로 다른 문제로 분리했다.
- backend OCR/YOLO 구현은 섹션 ROI label(`supplement_facts`, `precautions`, `intake_method`, `ingredients`)을 인식하고 OCR merge에서 layout page를 보존하도록 갱신했다.
- `1회 제공량(26g)`, `Serving Size`, `Amount Per Serving` 계열은 성분 후보에서 제외하고, 실제 성분명과 함량이 있는 문장은 유지하도록 테스트를 추가했다.
- 실제 이미지 기반 YOLO runtime smoke는 custom supplement section `.pt` 모델과 backend vision runtime 설치가 필요해 다음 단계로 남겼다.
- OCR layout에 `precautions` 섹션이 보이면 LLM parser가 놓쳐도 structured `precautions` 배열로 승격하도록 보완했다.
- 단수 `Warning`, `Allergy Information`, heading 없는 `Contains soy and milk` 같은 ROI OCR row도 `precautions` anchor로 분류하도록 추가 보강했다.
- `1회 제공량(26g)`은 줄 깨짐, 괄호 공백, 앞뒤 텍스트 혼합 케이스까지 성분 후보 오탐 회귀 테스트를 추가했다.
- Gemma/Ollama 기반 멀티모달 검증은 기존 OCR 유사도 비교에서 OCR 텍스트와 이미지/ROI를 직접 대조하는 structured verification 계약으로 보완했다.
- 분석 미리보기 설명은 `include_profile_context=true`일 때 민감 건강 동의 확인 후 최신 body profile snapshot의 sanitized bucket을 설명 context에 포함한다.
- 분석 미리보기 설명은 `include_medical_context=true`일 때 민감 건강 동의 확인 후 사용자 의료정보 DB의 질환/복약 요약 bucket을 설명 context에 포함한다.
- 개인 맞춤 설명의 다음 단계는 모바일 요청 연결, comprehensive nutrition engine 결합, 실제 local Ollama/Gemma live smoke다.
- 현재 repo에서 확인된 `.pt` 가중치는 음식 YOLO 실험 `best.pt`뿐이며, 영양제 섹션 전용 custom YOLO26 detector는 아직 확인되지 않았다.
- 다음 구현에서는 default COCO/food model을 영양제 섹션 detector로 오인하지 않도록 class-name/readiness guard와 데이터셋 계약을 먼저 추가해야 한다.
- backend Ultralytics runner는 이제 모델 class names가 supplement ROI taxonomy와 섹션 class를 포함하지 않으면 inference 전에 fail-closed 처리한다.
- `/ready`는 raw model path를 노출하지 않고 supplement YOLO의 allowed label과 required section label 계약만 노출한다.
- 영양제 섹션 detector dataset YAML은 `data/supplement_images/section_yolo/dataset.yaml`로 고정했다.
- dataset validator는 class 계약 검증을 통과했지만, 실제 annotation image/label 파일은 아직 없어 `--require-files` 검증은 다음 단계 blocker로 남아 있다.
- `supplement_section_yolo_detection` export kind를 추가해 privacy-reviewed annotation이 semantic section label 기준으로만 YOLO 학습 export에 들어가도록 제한했다.
- 숫자 class id만 있는 bbox나 `supplement_label` 전체 라벨 bbox는 section detector 학습 입력으로 거부된다.
- `materialize_supplement_section_yolo_dataset.py`를 추가해 export artifact를 `processed/section_yolo/images|labels` 구조로 생성하는 trusted worker 단계를 붙였다.
- materializer는 생성 후 dataset validator의 file-level 검증을 수행하며, stdout에는 source ref/source path/raw label row를 노출하지 않는다.
- 현재까지의 YOLO26 섹션 detector 작업은 training-ready data pipeline 계약까지이며, 실제 detector 학습 완료 상태는 아니다.
- 다음 단계는 human-reviewed section bbox annotation과 operator-only source map을 준비한 뒤 실제 dataset materialize, `--require-files` 검증, YOLO26 custom 학습, crop OCR, Ollama/Gemma verification 순서로 진행한다.
- OCR layout에서 나온 `LabelBox`는 이제 `build_supplement_section_yolo_label_snapshot`을 통해 raw OCR text 없이 normalized YOLO section bbox 후보로 변환할 수 있다.
- 이 후보 snapshot은 privacy review/human review를 거치면 기존 `build_supplement_section_yolo_detection_export` 경로로 들어갈 수 있다.
- 다음 구현은 후보 snapshot을 `AnnotationTask` operator review queue에 연결하고, review 승인 전 training export를 막는 guard를 추가하는 것이다.
- OCR layout 후보 snapshot은 이제 `training_export_allowed=false`, `human_review_required=true`, `coordinate_space=ocr_page`로 생성되며, 검수 전 supplement section YOLO export에서 거부된다.
- `AnnotationTask` 생성 helper는 추가됐지만, 실제 service insert는 원본 이미지 source가 `MediaObject` 또는 안전한 source map으로 연결된 뒤 진행해야 한다.
- 현재 확인 결과 `MediaObjectStore`는 삭제 전용이고 `LearningImageObjectStore`가 이미 consent-gated `put_image/get_image/delete_image`를 제공하므로, 다음 구현은 `AnnotationTask.learning_image_object_id`를 추가해 기존 learning image source를 검수 queue에 연결하는 방향이 가장 작다.
- `AnnotationTask.learning_image_object_id`가 추가되어 consent-gated learning image source가 있는 supplement analysis는 OCR layout section 후보를 pending review task로 enqueue할 수 있다.
- 같은 learning image source에 active `supplement_roi_box` review task가 이미 있으면 중복 생성하지 않는다.
