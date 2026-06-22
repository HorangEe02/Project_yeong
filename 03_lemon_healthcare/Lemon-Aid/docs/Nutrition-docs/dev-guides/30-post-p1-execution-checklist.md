# dev-guides/30 - Post-P1 실행 체크리스트

> Phase: Post-P1 stabilization
> 기준 문서: `docs/Nutrition-docs/23-p1-stabilization-plan.md`, `docs/Nutrition-docs/33-three-tier-ocr-pipeline-implementation-guide.md`, `docs/Nutrition-docs/35-google-vision-ocr-provider-implementation-plan.md`, `docs/Nutrition-docs/36-post-p1-execution-plan.md`, `docs/Nutrition-docs/37-ci-hardening-design-plan.md`, `docs/Nutrition-docs/38-stabilization-pr-gate-design-plan.md`, `docs/Nutrition-docs/39-commit-unit-splitting-design-plan.md`

---

## 1. 오늘 바로 확인할 항목

### CI hardening

- [ ] Backend CI path filter에 `data/nutrition_reference/kdris/**`, `data/nutrition_reference/nutrient/**`, `config/**`가 포함되어 있다.
- [ ] CI에서 `python scripts/validate_kdris_dataset.py --require-approved`가 실행된다.
- [ ] CI settings smoke가 AI/OCR/YOLO/학습/regulated intake flag의 default-off 상태를 확인한다.
- [ ] docs-only 변경은 docs CI로 분리되고, backend/data/config 변경은 backend CI를 실행한다.

### PR gate

상세 설계: `docs/Nutrition-docs/38-stabilization-pr-gate-design-plan.md`

- [ ] root `.github/PULL_REQUEST_TEMPLATE.md`와 project-local `03_lemon_healthcare/.github/PULL_REQUEST_TEMPLATE.md`의 P1 gate 문구가 같은 기준을 사용한다.
- [ ] KDRIs 데이터 변경 시 승인 데이터 validator 결과를 남긴다.
- [ ] JWT/OIDC/security 변경 시 production-path 테스트 결과를 남긴다.
- [ ] 만성질환 우선순위 문구 변경 시 금지 표현이 없는지 확인한다.
- [ ] feature flag를 `true`로 바꾸면 sign-off 문서와 production guard 테스트를 같이 제출한다.
- [ ] OCR/LLM/이미지 변경 시 raw image/raw OCR text 저장 금지 테스트를 확인한다.

### Commit split

상세 설계: `docs/Nutrition-docs/39-commit-unit-splitting-design-plan.md`

- [ ] `fix(config)`, `data(kdris)`, `fix(security)`, `feat(nutrition)`, `docs(status)`, `ci(backend)` 순서로 stage한다.
- [ ] `git add .`를 사용하지 않고 커밋별 파일 범위를 확인한다.
- [ ] `00_plusultra/**`, `assets/mascot/**`, `outputs/generated/**`, `records/meetings/**`는 이번 P1 backend stabilization 커밋에서 제외한다.

---

## 2. 로컬 검증 명령

Backend 기준 작업 디렉터리:

```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
```

기본 검증:

```bash
black --check src tests alembic
ruff check src tests alembic
mypy src tests --strict
python scripts/validate_kdris_dataset.py --require-approved
pytest --cov-report=term-missing
```

Settings/OpenAPI smoke:

```bash
python -m json.tool ../config/implementation-readiness.settings.json > /tmp/implementation-readiness.settings.json
python -c "from src.config import Settings; s=Settings(_env_file=None); assert not s.allow_external_llm and not s.enable_multimodal_llm and not s.enable_vision_classifier and not s.enable_image_learning_pipeline and not s.enable_pgvector_storage and not s.feature_prescription_ocr_intake and not s.feature_lab_result_ocr_intake and not s.feature_dosage_change_recommendation and not s.feature_medication_safety_alert"
python -c "from src.main import create_app; schema=create_app().openapi(); assert '/api/v1/supplements/analyze' in schema['paths']; assert '/api/v1/supplements/analyses/{analysis_id}/ocr-text' in schema['paths']; assert '/api/v1/nutrition/kdris' in schema['paths']; assert '/api/v1/nutrition/analyze' in schema['paths']"
```

---

## 3. 다음 구현 진입 조건

### Google Vision OCR MVP

- [ ] `.env`에는 key 값만 입력한다. 변수명은 `GOOGLE_CLOUD_API_KEY`를 사용한다.
- [ ] credential JSON 파일을 저장소에 두지 않는다.
- [ ] `OCR_PRIMARY_PROVIDER=none`, `ALLOW_EXTERNAL_OCR=false` 기본값을 먼저 추가한다.
- [ ] `EXTERNAL_OCR_PROCESSING` 동의와 active policy를 추가한다.
- [ ] fake client 기반 unit/integration test를 먼저 작성한다.
- [ ] 실제 Google smoke test는 opt-in 환경 변수 뒤에서만 실행한다.

### OCR 3-tier 확장

- [ ] Google Vision full-image OCR MVP가 먼저 통과되어 있다.
- [ ] YOLO ROI는 OCR crop 후보로만 사용한다.
- [ ] Ollama vision assist는 OCR empty 또는 low-confidence fallback으로만 호출한다.
- [ ] PaddleOCR/CLOVA 우선순위는 fixture 결과, privacy, 운영 조건을 보고 결정한다.
- [ ] label fixture 기준 정확도/latency 리포트를 작성한다.

### Learning/vector DB

- [ ] `docs/Nutrition-docs/41-learning-vector-db-implementation-design-plan.md`의 LVB 단계와 sign-off 조건을 리뷰했다.
- [ ] pgvector extension migration이 준비되어 있다.
- [ ] image embedding table schema가 raw image/raw OCR text 저장 금지 기준을 만족한다.
- [ ] embedding model runner와 vector upsert worker가 분리되어 있다.
- [ ] image object storage와 자동삭제 정책이 설계되어 있다.

### Prescription/lab OCR intake

- [ ] `docs/Nutrition-docs/42-prescription-lab-ocr-intake-design-plan.md`의 RGI 단계와 금지 output을 리뷰했다.
- [ ] 처방전 OCR intake endpoint와 검사표 OCR intake endpoint는 default-off flag 뒤에 둔다.
- [ ] 별도 민감 동의를 요구한다.
- [ ] 원문 이미지는 자동삭제 정책을 따른다.
- [ ] 사용자 확인 단계를 거친다.
- [ ] 전문의 상담 CTA를 제공한다.
- [ ] 직접 복용량 변경 안내 금지 테스트를 작성한다.

---

## 4. 공식 문서 참고

- GitHub Actions workflow syntax: https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax
- GitHub pull request templates: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-issue-and-pull-request-templates
- Google Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- Google Cloud Vision `images:annotate` REST API: https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate
