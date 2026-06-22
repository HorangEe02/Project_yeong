# 36. Post-P1 실행 계획 보정 - CI, PR Gate, OCR, 학습, regulated intake

> 작성일: 2026-05-15
> 상태: 실행 계획 보정 및 구현 순서 기준
> 기준 문서: `docs/23`, `docs/32`, `docs/33`, `docs/35`, `docs/37`, `docs/38`, `docs/39`, `docs/Nutrition-docs/dev-guides/07`, `docs/Nutrition-docs/dev-guides/09`, `docs/Nutrition-docs/dev-guides/25`, `docs/Nutrition-docs/dev-guides/29`

---

## 1. 이 문서의 목적

P1 안정화 이후 작업은 CI, PR gate, Google Vision OCR, 3-tier OCR, learning/vector DB, 처방전/검사표 OCR intake가 한 번에 섞이기 쉽다. 이 문서는 현재 프로젝트 구현 상태를 기준으로 작업 순서를 다시 맞추고, 어떤 항목을 오늘 바로 적용할지와 어떤 항목은 별도 sign-off 뒤에 구현해야 하는지를 분리한다.

오늘 바로 적용하는 범위는 CI hardening, PR checklist 보강, 후속 구현 계획 문서화다. Google Vision provider, YOLO 실제 추론 연결, vector DB, 처방전/검사표 OCR endpoint는 기능 구현 범위가 크고 regulated gate가 필요하므로 이 문서에서는 진입 조건과 검증 기준을 먼저 확정한다.

---

## 2. 현재 프로젝트 상태 매핑

| 항목 | 현재 상태 | 이번 보정 방향 |
| --- | --- | --- |
| CI hardening | backend 경로 중심으로 검증됨 | KDRIs/reference/config 변경도 backend CI를 실행하도록 path filter 확장 |
| KDRIs validator | 로컬 검증 스크립트 존재 | CI에 `validate_kdris_dataset.py --require-approved` 추가 |
| regulated flags | production validator와 default-off 플래그 존재 | CI smoke에서 default-off 상태를 명시적으로 확인 |
| PR gate | 일반 checklist 중심 | P1 안정화 체크 항목을 별도 섹션으로 분리 |
| Google Vision OCR | `docs/35` 기준 구현 계획 단계 | `GOOGLE_CLOUD_API_KEY` 기반 MVP 후 production 인증 방식 결정 |
| 3-tier OCR | `docs/33` 기준 계획, 일부 adapter 골격 존재 | Google Vision MVP 이후 YOLO ROI, Ollama vision fallback, PaddleOCR/CLOVA 재평가 순서로 진행 |
| Learning/vector DB | gate와 adapter 골격 중심 | pgvector migration, embedding runner, upsert worker, object storage를 별도 PR로 분리 |
| 처방전/검사표 OCR | regulated flag default-off | intake-only endpoint와 금지 표현 테스트를 별도 regulated PR에서 진행 |

---

## 3. 우선순위

### P0. 오늘 바로 잠글 항목

CI hardening 상세 설계는 [37-ci-hardening-design-plan.md](./37-ci-hardening-design-plan.md)를 기준으로 한다.
Stabilization PR gate 상세 설계는 [38-stabilization-pr-gate-design-plan.md](./38-stabilization-pr-gate-design-plan.md)를 기준으로 한다.
커밋 단위 정리 상세 설계는 [39-commit-unit-splitting-design-plan.md](./39-commit-unit-splitting-design-plan.md)를 기준으로 한다.

1. Backend CI trigger에 다음 경로를 추가한다.
   - `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/kdris/**`
   - `03_lemon_healthcare/yeong-Lemon-Aid/data/nutrition_reference/nutrient/**`
   - `03_lemon_healthcare/yeong-Lemon-Aid/config/**`
2. CI에 KDRIs 승인 데이터 검증을 추가한다.
   - `python scripts/validate_kdris_dataset.py --require-approved`
3. CI settings smoke에서 다음 기본값이 꺼져 있는지 확인한다.
   - `allow_external_llm`
   - `enable_multimodal_llm`
   - `enable_vision_classifier`
   - `enable_image_learning_pipeline`
   - `enable_pgvector_storage`
   - `feature_prescription_ocr_intake`
   - `feature_lab_result_ocr_intake`
   - `feature_dosage_change_recommendation`
   - `feature_medication_safety_alert`
4. PR template에 P1 안정화 gate를 별도 체크리스트로 추가한다.

완료 기준:

- data/config/backend 변경 시 backend CI가 실행된다.
- 승인되지 않은 KDRIs 데이터는 CI에서 실패한다.
- regulated 또는 AI/OCR/YOLO/학습 플래그가 기본 ON이 되면 CI smoke에서 실패한다.
- PR 작성자가 raw image/raw OCR text 저장 금지, feature flag sign-off, JWT/OIDC production-path 테스트를 체크하게 된다.

### P1. Google Vision OCR provider MVP

Google Vision은 `docs/35` 기준으로 다음 순서로 착수한다.

1. 로컬 개발 기본 인증은 `.env`의 `GOOGLE_CLOUD_API_KEY`만 사용한다.
2. credential JSON은 저장소에 두지 않는다.
3. production 인증은 API key 제한 또는 attached service account 중 하나를 별도 보안 검토로 결정한다.
4. 다음 설정을 추가한다.
   - `OCR_PRIMARY_PROVIDER=none`
   - `ALLOW_EXTERNAL_OCR=false`
   - `GOOGLE_CLOUD_PROJECT`
   - `GOOGLE_VISION_TIMEOUT_SECONDS`
   - `GOOGLE_VISION_MAX_RETRIES`
5. 별도 동의 타입과 policy를 추가한다.
   - `EXTERNAL_OCR_PROCESSING`
6. `GoogleVisionOCRAdapter`와 factory를 구현한다.
7. `/api/v1/supplements/analyze`에서 이미지 intake, OCR, parse preview가 한 번의 흐름으로 연결되도록 한다.
8. fake client 기반 unit/integration test를 먼저 작성한다.
9. 실제 Google smoke test는 명시 opt-in 환경 변수 뒤에서만 실행한다.

완료 기준:

- 기본 설정에서는 외부 OCR이 호출되지 않는다.
- `ALLOW_EXTERNAL_OCR=true`와 필요한 consent가 모두 있을 때만 Google Vision adapter가 동작한다.
- raw image와 raw OCR text는 DB, 로그, audit event에 저장되지 않는다.
- API 응답은 preview이며 사용자 확인 전 확정 데이터로 취급하지 않는다.

### P2. OCR 3-tier 확장

Google Vision MVP가 통과한 뒤 `docs/33`을 기준으로 확장한다.

1. 1차 OCR: Google Vision `DOCUMENT_TEXT_DETECTION`
2. 전처리: YOLO ROI 실제 추론을 OCR 입력 crop 후보로만 사용
3. 보조 검증: Ollama multimodal fallback은 OCR이 비어 있거나 confidence가 낮을 때만 사용
4. 로컬 fallback: PaddleOCR을 우선 검토하고, CLOVA는 privacy, 비용, 운영 계약 조건을 확인한 뒤 재평가
5. label fixture 기준 정확도와 latency 리포트를 작성
6. 발주처 리뷰 gate 산출물을 준비

완료 기준:

- YOLO 결과는 OCR ROI 후보일 뿐 제품명, 성분명, 의학 판단으로 사용하지 않는다.
- Ollama vision assist 결과는 fallback candidate로 표시하며 primary OCR 결과를 조용히 덮어쓰지 않는다.
- 정확도와 latency는 fixture 기준으로 측정하고 임의 성능 수치를 만들지 않는다.

### P3. Learning/vector DB

현재는 gate와 disabled adapter 골격을 유지한 채 pgvector migration, object storage adapter, embedding runner, upsert worker의 초기 구현이 추가되었다. 운영 활성화 전에는 다음 작업을 별도 PR 또는 opt-in smoke로 분리해 검증한다.

상세 설계와 구현 플랜은 [docs/Nutrition-docs/41-learning-vector-db-implementation-design-plan.md](./41-learning-vector-db-implementation-design-plan.md)를 기준으로 한다. 특히 raw image가 필요한 시점은 analyze 요청 중이고, 학습 metadata로 사용할 수 있는 값은 confirmation 이후에 확정되므로 object 저장, embedding job enqueue, vector upsert worker를 분리한다.

1. 실제 PostgreSQL 환경에서 pgvector extension migration 적용 확인
2. image embedding table의 실제 insert/upsert smoke
3. embedding model runner의 실제 model probe와 dimension 확정
4. vector upsert worker의 실제 object storage + pgvector 연동 smoke
5. S3 또는 S3-compatible image object storage 연동 smoke
6. raw image/raw OCR text 저장 금지 회귀 테스트 유지

완료 기준:

- `enable_image_learning_pipeline=false`, `enable_pgvector_storage=false` 기본값을 유지한다.
- 명시 동의 없이 이미지나 OCR 원문을 학습 데이터로 적재하지 않는다.
- vector metadata는 가명화된 참조값과 확인된 structured field만 포함한다.

### P4. Prescription/lab OCR intake

처방전과 검사표 OCR은 regulated 영역이므로 intake-only로 시작한다.

상세 설계와 구현 플랜은 [docs/Nutrition-docs/42-prescription-lab-ocr-intake-design-plan.md](./42-prescription-lab-ocr-intake-design-plan.md)를 기준으로 한다. 구현은 처방 생성, 질병 진단, 복용량 변경 안내가 아니라 원문 이미지 memory-only OCR, 사용자 확인 preview, 전문가 상담 CTA로 제한한다.

1. 처방전 OCR intake endpoint
2. 검사표 OCR intake endpoint
3. 별도 민감 동의
4. 원문 이미지 자동삭제 정책
5. 사용자 확인 단계
6. 전문의 상담 CTA
7. 직접 복용량 변경 안내 금지 테스트

완료 기준:

- `feature_prescription_ocr_intake=false`, `feature_lab_result_ocr_intake=false` 기본값을 유지한다.
- OCR 결과는 intake preview이며 처방 변경, 복용량 변경, 검사 해석 확정 안내로 사용하지 않는다.
- 사용자 확인 전에는 medication/safety workflow로 전달하지 않는다.

---

## 4. 권장 커밋 단위

큰 변경을 하나로 묶지 않고 다음 단위로 분리한다.

1. `fix(config): default non-P1 regulated flags to disabled`
   - 이유: 아직 검증되지 않은 기능이 production에서 실수로 켜지지 않도록 하기 위함.
2. `data(kdris): import reviewed 2025 KDRIs reference rows`
   - 이유: 영양 분석 기준을 샘플 데이터에서 승인된 2025 데이터로 바꾸기 위함.
3. `fix(security): harden JWT JWKS verification path`
   - 이유: 운영 로그인 토큰 검증에서 잘못된 토큰을 더 안전하게 거부하기 위함.
4. `feat(nutrition): apply chronic-condition nutrient priority lookup`
   - 이유: 만성질환 정보가 있을 때 확인 우선순위를 더 잘 보여주기 위함.
5. `docs(status): refresh P1 stabilization map`
   - 이유: 팀이 현재 구현 상태와 남은 범위를 같은 기준으로 보게 하기 위함.
6. `ci(backend): add data and settings stabilization gates`
   - 이유: 로컬 검증 기준을 GitHub Actions에서도 반복 가능하게 만들기 위함.

커밋을 나눌 때는 기존 작업자가 수정한 파일을 되돌리지 말고, 각 커밋에 들어갈 파일 범위를 `git diff --name-only`로 먼저 확인한다.

---

## 5. 공식 문서 참고

- GitHub Actions workflow syntax: https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax
- GitHub pull request templates: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-issue-and-pull-request-templates
- Google Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- Google Cloud Vision `images:annotate` REST API: https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate
