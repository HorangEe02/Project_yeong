# Lemon Healthcare 백엔드 — 진행 TODO

> **마지막 갱신:** 2026-05-19
> **Branch:** `claude/inspiring-cannon-a70b91`
> **Worktree:** `/Users/yeong/99_me/00_github/03_lemon_healthcare/.claude/worktrees/inspiring-cannon-a70b91`
> **트랙 B HEAD:** `f7c698c6`
> **누적:** 6 commits / 132 files / +7,844 lines

---

## 📚 작업 시작 전 진단·계획 단계

- [x] 진단 보고서 작성 — `/Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md`
  - 사용자 의도 ①~⑧ vs 실제 구현 갭 매트릭스
  - 설계 결함 D1~D6 / 보안 위험 S1~S6 / 데이터·운영 위험 M1~M4
  - 트랙 A / 트랙 B / 트랙 C 분기 제안
- [x] 트랙 B 페이즈 plan 작성 — `/Users/yeong/.claude/plans/lemon-track-b/`
  - [x] `INDEX.md` (페이즈 지도, 의존성, OUT OF SCOPE)
  - [x] `phase-00-bootstrap.md`
  - [x] `phase-01-ocr-pipeline.md`
  - [x] `phase-02-ollama-llm-safety.md`
  - [x] `phase-03-nutrition-data.md`
  - [x] `phase-04-database-models.md`
  - [x] `phase-05-api-integration.md`

---

## ✅ 트랙 B — 백엔드 골격 (완료)

### Phase 00 — Bootstrap `521fa479` (31 files, +783)
- [x] `pyproject.toml` (Black/Ruff/mypy strict/pytest cov 80, pydantic.mypy plugin)
- [x] `requirements.txt` + `requirements-dev.txt`
- [x] `src/main.py` 앱 팩토리 + `/health`
- [x] **D1 수리** — `VisionAdapter.detect_regions(...) -> list[LabeledBoundingBox]`
- [x] **D2 수리** — `allow_external_llm` 삭제, `llm_provider: Literal["ollama"]`
- [x] **D3 수리** — `Settings.model_config extra="forbid"`
- [x] **D4 수리** — `image_retention_*_days` 3개 분리
- [x] **D5 수리** — `scripts/check_ollama_tags.py` (qwen3.5:9b/gemma4:e4b OK)
- [x] 빈 `__init__.py` 13개 (후속 페이즈 디렉터리 부트스트랩)
- [x] `tests/conftest.py` + autouse env 격리
- [x] `tests/unit/test_config.py` (8 cases) + `test_base_contracts.py` (6 cases)
- [x] `.github/workflows/ci-backend-yeong.yml`

### Phase 01 — OCR Pipeline `57bff48d` (18 files, +1,392)
- [x] `src/ocr/{exceptions, base, preprocessor, google_vision, pipeline}.py`
- [x] `src/cache/ocr_cache.py` (Redis SHA-256 키)
- [x] **S3 보안 게이트 4개**:
  - [x] ① MIME 위조 차단 (magic-byte sniff — libmagic 대체)
  - [x] ② Decompression bomb 차단 (`MAX_IMAGE_PIXELS=50M`)
  - [x] ③ EXIF metadata 전체 제거
  - [x] ④ 빈 / 손상 이미지 거부
- [x] `scripts/ocr_demo.py` (실 Google Vision PoC)
- [x] 단위·통합 테스트 (testcontainers Redis)

### Phase 02 — Ollama LLM + Safety `cb4bfdc0` (16 files, +1,018)
- [x] `src/llm/{exceptions, schemas, prompts, ollama, external}.py`
- [x] `src/safety/forbidden_terms.py` (의료법 금지표현 frozenset)
- [x] **S1 sandbox 토큰** — `<USER_OCR>...</USER_OCR>` 격리 + 이스케이프
- [x] **S2 forbidden term scanner** — raw + 파싱 필드 2단 검사
- [x] 외부 LLM 가드 (`ensure_external_llm_allowed` 항상 raise)
- [x] 단위·통합 테스트 (`RUN_OLLAMA_TESTS=1` 옵션)

### Phase 03 — Nutrition Data + Diagnosis `88914e32` (19 files, +1,479)
- [x] `data/reference/nutrient_codes.json` (30종)
- [x] `data/reference/disease_codes.json` (5종 만성질환)
- [x] `data/kdris/kdris_2020.csv` (84 row × 30 영양소 × 인구집단)
- [x] `data/mfds/functional_ingredients.csv` (32 원료 + alias)
- [x] `data/mfds/unit_conversions.json` (IU↔mg/μg)
- [x] `data/README.md` (출처·라이선스)
- [x] `src/models/schemas/nutrition.py` (5 모델 + `NutrientStatus` enum)
- [x] `src/nutrition/{kdris, unit_converter, mfds_matcher, diagnosis}.py`
- [x] `scripts/validate_data.py` (Pydantic CSV/JSON 검증, CI 통합)
- [x] 단위 테스트 + 진단 메시지 forbidden term 통과 증빙

### Phase 04 — Database + Alembic `2d71683c` (17 files, +1,109)
- [x] `docker-compose.yml` (Postgres 16 + Redis 7 + healthcheck)
- [x] `src/models/db/{base, user, consent, audit, supplement}.py`
- [x] `src/db/session.py` (AsyncEngine 싱글턴 + `get_session`)
- [x] Alembic 초기 마이그레이션 (5 tables + 인덱스 + CASCADE)
- [x] **컴플라이언스 강제**:
  - [x] `AccessAuditLog.ip_address_hash` only (raw IP 컬럼 부재)
  - [x] `Supplement.image_hash` only (raw image 컬럼 부재)
- [x] 단위 + 통합 테스트 (testcontainers Postgres)

### Phase 05 — API + Auth + Disclaimer `f7c698c6` (31 files, +2,063)
- [x] `Settings` 확장 (JWT secret/algorithm/TTL/CORS/rate-limit/IP hash salt)
- [x] `src/auth/{password, jwt}.py` (bcrypt 직접 + JWT round-trip)
- [x] `src/safety/{disclaimer, response_filter}.py`
- [x] `src/models/schemas/{auth, supplement}.py`
- [x] `src/services/{consent, audit, supplement}_service.py`
- [x] `src/api/{deps, middleware}.py`
- [x] `src/api/v1/{auth, consents, supplements}.py`
- [x] `src/main.py` 갱신 (CORS + RequestId + 3 라우터 + lifespan)
- [x] **컴플라이언스 게이트** (코드 레벨 강제):
  - [x] JWT 인증 (`get_current_user`)
  - [x] 동의 게이트 (`ConsentService.require`)
  - [x] 응답 안전 필터 (`assert_response_safe` — disclaimer 면제)
  - [x] 면책 고지 강제 주입 (3종 + 응급 자원)
  - [x] 감사 로그 (성공/실패/security_blocked/llm_refusal 모두 기록)
  - [x] rate limit (Redis fixed-window)
- [x] 49 신규 단위·통합 테스트

---

## 📊 트랙 B 최종 검증 상태

- [x] `black --check` — 106 files unchanged
- [x] `ruff check` — All checks passed
- [x] `mypy src --strict` — no issues, 57 source files
- [x] `pytest -m "not integration"` — **224 passed**, 8 deselected
- [x] **Coverage: 85.39%** (≥70% threshold)
- [x] `validate_data.py` — All data files passed
- [x] `check_ollama_tags.py` — qwen3.5:9b / gemma4:e4b OK
- [x] `alembic upgrade head --sql` — 5 tables valid SQL
- [x] End-to-end smoke test (mock): OCR → LLM → matcher → diagnose 통합 흐름 검증

---

## 🚧 후속 트랙 (새 세션에서 진행)

### 트랙 C — YOLO 영역 검출 + Gemma 4 Multimodal (미시작)

**진입 전 게이트 통과 필요** — `docs/17 §9`:
- [ ] 게이트 #1 통과 증빙: PoC 정확도·응답시간 / 표현 검수 / 환경변수 표
- [ ] 게이트 #2 통과 증빙: 검출 IoU·OCR 정확도 향상치 / 데이터 출처 / 의료법 검토

Phase 분해:
- [ ] **Phase C-0** — `lemon-track-c/INDEX.md` + phase plan 작성
- [ ] **Phase C-1** — YOLO 어댑터
  - [ ] `src/vision/yolo.py` (`YoloLabelDetector(VisionAdapter)`)
  - [ ] `scripts/fetch_yolo_weights.py`
  - [ ] OCR pipeline pre-crop step 통합
  - [ ] 단위·통합 테스트
- [ ] **Phase C-2** — Gemma 4 multimodal
  - [ ] `src/llm/multimodal.py` (`GemmaMultimodalAdapter`)
  - [ ] OllamaAdapter 멀티모달 라우팅 (`enable_multimodal_llm` 가드)
  - [ ] S1·S2 게이트를 이미지+텍스트 양쪽 적용
  - [ ] 단위·통합 테스트
- [ ] **Phase C-3** — 손글씨/얼굴 자동 모자이크 (`docs/17 §4.1`)
  - [ ] `src/ocr/preprocessor.py` `TODO[track-c]` 처리
  - [ ] 모자이크 후 OCR 흐름 단위 테스트
- [ ] **Phase C-4** — 게이트 산출물
  - [ ] `scripts/eval_yolo_iou.py`
  - [ ] `scripts/eval_multimodal_accuracy.py`
  - [ ] `docs/19-track-c-gate-evidence.md`

### 모바일 Flutter (미시작)

- [ ] **Phase M-0** — `lemon-mobile/INDEX.md` + phase plan 작성
- [ ] **Phase M-1** — Flutter 프로젝트 부트스트랩
  - [ ] `pubspec.yaml` (Dio, Riverpod, Freezed, image_picker/cropper, go_router)
  - [ ] `lib/main.dart` + `lib/app.dart`
  - [ ] `lib/core/network/dio_provider.dart` (Bearer 인터셉터)
  - [ ] `lib/core/storage/token_storage.dart` (`flutter_secure_storage`)
  - [ ] iOS Info.plist + Android AndroidManifest.xml 권한
  - [ ] `flutter analyze` + `flutter test` 통과
- [ ] **Phase M-2** — 인증 화면 (login + register)
  - [ ] 회원가입 시 동의 매트릭스 UI (`docs/10 §5.2`)
  - [ ] 401 → refresh 자동 시도 → 로그인 폴백
- [ ] **Phase M-3** — 영양제 사진 등록 화면
  - [ ] `lib/features/supplement/*`
  - [ ] SourceSelector (카메라/갤러리) + image_cropper + 업로드 진행률
  - [ ] 결과 카드 + **면책 위젯 필수** (`docs/10 §2.3`)
- [ ] **Phase M-4** — 면책 / 응급 자원 위젯
  - [ ] `lib/shared/widgets/disclaimer.dart` (`MedicalDisclaimer`,
    `EmergencyResources`)
- [ ] **Phase M-5** — Patrol integration_test 1 시나리오

### 정식 출시 보안 강화 (ISMS-P + 약물 상호작용) (미시작)

**진입 전 결정** — 사용자에게 확인:
- [ ] KMS 공급자 (AWS KMS / NCP KMS)
- [ ] 운영 환경 (NCP / AWS / GCP / 사내 GPU)
- [ ] ISMS-P 컨설팅 일정

Phase 분해:
- [ ] **Phase S-0** — `lemon-security-hardening/INDEX.md` + 사용자 확인
- [ ] **Phase S-1** — 약물–보충제 상호작용 (M2)
  - [ ] `data/dur/interactions.csv` (≥50 의약품×영양제 시드)
  - [ ] `src/nutrition/drug_interaction.py`
  - [ ] SupplementService 에 interaction warning 분기
  - [ ] 단위 테스트
- [ ] **Phase S-2** — AES-256 컬럼 암호화
  - [ ] `src/db/encryption.py` (KMS envelope encryption)
  - [ ] `chronic_diseases` / `medications` 암호화 TypeDecorator
  - [ ] Alembic 마이그레이션 (zero-downtime 3-step)
  - [ ] 통합 테스트
- [ ] **Phase S-3** — 자동 파기 cron
  - [ ] `scripts/purge_soft_deleted_users.py` (deleted_at + 90일)
  - [ ] `scripts/purge_old_audit_logs.py` (365일)
  - [ ] `scripts/purge_revoked_consents_history.py`
  - [ ] Kubernetes CronJob YAML 또는 APScheduler
- [ ] **Phase S-4** — secret rotation + 모니터링
  - [ ] JWT `kid` 헤더 + 키 회전 절차
  - [ ] Redis 기반 JWT blacklist 실 구현
  - [ ] structlog + Sentry 통합
  - [ ] 단위 테스트
- [ ] **Phase S-5** — 컴플라이언스 산출물
  - [ ] `docs/20-isms-p-controls-applied.md`
  - [ ] `docs/21-incident-response-runbook.md`
  - [ ] GitHub Actions: `pip-audit` / Trivy / CodeQL 보강

---

## 🔄 미해결 위험 (후속 트랙에서 닫힘)

| ID | 항목 | 닫힐 트랙 | 우선순위 |
|----|------|----------|----------|
| S4 | 인증·인가 (JWT) | ✅ **Phase 05에서 닫힘** | — |
| S5 | service-account JSON path 로그 노출 | Phase S-4 | 중 |
| S6 | 외부 OCR(GCP)에 PHI 송신 경로 | 트랙 C (로컬 OCR 후보) | 중 |
| M1 | KDRIs 시드 PoC 한계 | 정식 출시 전 영양사 검수 | 중 |
| M2 | 약물 상호작용 DB 부재 | **Phase S-1** | 높 |
| TODO[track-c] | 얼굴/손글씨 모자이크 | **Phase C-3** | 중 |

---

## 🎯 트랙 B 데모 명령

```bash
cd 03_lemon_healthcare/yeong-Vision-Nutrition

# 1. 인프라
docker compose up -d

# 2. 마이그레이션
cd backend
alembic upgrade head

# 3. Ollama 모델 + GCP 자격증명
ollama pull qwen3.5:9b
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export JWT_SECRET_KEY=$(openssl rand -hex 32)

# 4. 서버
uvicorn src.main:app --reload --port 8000

# 5. 데모
# - http://localhost:8000/docs (Swagger UI)
# - POST /api/v1/auth/register → /auth/login → /supplements/register
```

---

## 🔗 참조 문서

- 진단 보고서: [/Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md](/Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md)
- 트랙 B plan: [/Users/yeong/.claude/plans/lemon-track-b/](/Users/yeong/.claude/plans/lemon-track-b/)
- 프로젝트 컨텍스트: `03_lemon_healthcare/yeong-Vision-Nutrition/CLAUDE.md`
- 백엔드 규칙: `03_lemon_healthcare/yeong-Vision-Nutrition/backend/CLAUDE.md`
- 데이터 규칙: `03_lemon_healthcare/yeong-Vision-Nutrition/data/CLAUDE.md`
- 컴플라이언스: `docs/10-compliance-checklist.md`
- 게이트 매트릭스: `docs/17-image-collection-consent-plan.md`
- 의료법·약사법 표현: `docs/10-compliance-checklist.md §10`

---

## ✏️ 사용 메모

- 진행 중 체크박스를 `[x]`로 갱신
- 새 트랙 시작 시 해당 트랙의 Phase X-0 (plan 작성) 부터 시작
- 모든 phase 끝에 commit + Conventional Commits + Co-Authored-By
- 모든 변경 후 `black/ruff/mypy/pytest/validate_data.py` 그린 확인
- 컴플라이언스 표현 (진단·처방·치료 등) 절대 0건 유지

---

**작성:** 2026-05-19
**작성자:** Claude Code (트랙 B 실행자)
**다음 갱신 트리거:** 후속 트랙 1개 이상 phase 완료 시
