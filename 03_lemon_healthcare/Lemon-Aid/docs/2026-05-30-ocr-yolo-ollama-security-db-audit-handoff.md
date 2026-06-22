# Lemon-Aid 감사 + 개선 작업 인수인계 (Handoff)

작성일: 2026-05-30
대상: 이 작업을 이어받는 다음 작업자/에이전트

## 0. 한 줄 요약
Lemon-Aid의 OCR(PaddleOCR / Google Vision / CLOVA) + YOLO + Ollama(멀티모델) 구현, 보안(`.env`/키), 촬영·갤러리 이미지 분석 파이프라인, DB 연동·스키마·값을 감사했고, 개선 로드맵 중 일부를 **코드 파일로만** 착수했다(DB 적용·배포·런타임 테스트는 미수행).

---

## 1. 환경/좌표 (사실)
- 실제 프로젝트 repo: `…/03_lemon_healthcare/Lemon-Aid` (중첩 git, branch `feat/mobile-ios-xcode-simulator-run`, remote `Lemon-Aid-KDT/Lemon-sin`). 바깥 `00_github`는 별개 repo.
- 백엔드:
  - `backend/Nutrition-backend` — FastAPI, 영양제 OCR/파싱/DB 핵심.
  - `backend/Food-backend` — 식단 인식 라이브러리(mock-우선). **실 HTTP API에 미연결**.
  - `backend/alembic` — 마이그레이션. 파일 체인은 현재 `0001 … 0021`.
- 실제 운영 DB: **로컬 Docker `lemon-aid-db-1`** (`pgvector/pgvector:pg16`), `DATABASE_URL=postgresql+asyncpg://lemon@localhost:5432/lemon`. **DB에 적용된 alembic head = `0019`** (0020/0021 미적용).
- 백엔드 컨테이너 `lemon-aid-backend-1`: 코드가 **이미지에 baked**되어 있고, 컨테이너 `command`가 시작 시 `alembic upgrade head`를 실행(`docker-compose.yml`). 호스트 소스 편집은 **이미지 재빌드 전까지 런타임에 반영되지 않음**.
- MCP로 접근 가능한 Supabase 프로젝트(`ycjuzwltwbeudanjykag`, "HorangEe02's Project")는 **Lemon-Aid가 아닌 다른 앱**(설비/직원 어시스턴트류: employees/PLC/equipment alarms/RAG)의 DB. 영양제 테이블 0건, alembic head `20260526_0003`. → Lemon-Aid 데이터는 **로컬 pg**에 있음. 팀 별도 Supabase 존재 가능성은 이 환경에서 미확인.
- 기능 플래그 기본 OFF: 멀티모달 LLM(`ENABLE_MULTIMODAL_LLM`), 라벨 ROI YOLO(`ENABLE_VISION_CLASSIFIER`), Food YOLO(`ENABLE_FOOD_YOLO_DETECTOR`), CLOVA(`ENABLE_CLOVA_OCR`), 외부 OCR/LLM(`ALLOW_EXTERNAL_OCR/LLM`), `AUTH_MODE=disabled`. **PaddleOCR 로컬만 기본 ON**(규제 게이트 설계 → "구현됨+게이트 off"와 "미구현"·"버그" 구분 필요).

---

## 2. 감사 결과 (축별)

### 2.1 DB 연동·스키마·값 — 라이브 직접 검증 완료
- alembic 적용 head `0019`, public 38 테이블. 요청 변수 4종 모두 정의됨:
  - 영양제명: `supplement_products.product_name` / `user_supplements.display_name`
  - 성분: `supplement_product_ingredients.standard_name` / `user_supplement_ingredients.display_name`(+`nutrient_code`)
  - 함량: `*.amount`(Numeric(14,6)) + `*.unit`
  - 섭취방법: `user_supplements.intake_schedule`(jsonb) + `serving_snapshot`
- 적재 실태(라이브 카운트): `supplement_analysis_runs` 121(전부 parsed+match snapshot 보유) / `user_supplements` 2 / `user_supplement_ingredients` 7 / `food_image_analysis_runs` 4 / `meal_records` 4 / `supplement_products` 0 / `supplement_product_ingredients` 0 / `analysis_results` 0 / `users` 0.
- run 프로바이더 분포: clova_ocr 54, intake-only 33, paddleocr_local 27, google_vision 7 (avg conf 0.84~0.97).
- 쓰기 경로: `POST /supplements/analyze` → `create_supplement_analysis_intake`(무조건 run 1행 저장) → 파서가 같은 행 갱신(`supplement_parser.py` commit). `POST /supplements` 확정 → `create_user_supplement_from_confirmation`(`user_supplements` + `user_supplement_ingredients`). 카탈로그(`supplement_products`/`_ingredients`)는 오프라인 스크립트 `run_naver_tampermonkey_approved_db_import.py`만 적재(요청경로는 read-only).
- 발견사항:
  - [HIGH] 핵심 테이블 DB레벨 RLS **off**(라이브 확인): `user_supplements`, `user_supplement_ingredients`, `supplement_analysis_runs`, `supplement_products(+_ingredients)`, `analysis_results`, `consent_records`, `consent_policies`, `deletion_requests`. learning/media/patient/prescription/lab/regulated/users/health_* 계열만 on. 로컬은 직접 asyncpg(owner)라 무방하나, 동일 스키마를 Supabase Data API로 노출하면 사용자 건강 PII 노출 위험.
  - [MED] 확정 성분의 `amount`/`unit`/`nutrient_code` 미적재(7행 전부 공백) + 부형제(softgel/gelatin/glycerin/purified water/sunflower oil)가 성분으로 유입(`source=ocr_llm_preview`).
  - [MED] 섭취방법 구조화 손실: 프리뷰의 구조화 intake(times_per_day/amount_per_time/amount_unit/with_food)가 확정 시 `intake_schedule`(frequency/time_of_day)로 축소.
  - [MED] %DV(영양성분기준치) 컬럼 부재.
  - [LOW] 제품 마스터 카탈로그 0행(요청경로 저장엔 무영향, 매칭만 NULL). 단위 free-string(allowlist/CHECK 없음).

### 2.2 보안 / `.env` 키 유출
- git 이력 비밀 커밋 **0건**, `.env`(perm 600)·GCP키(`lemon-healthcare-*.json`) gitignore + 미추적. `backend/.env.example`는 placeholder + 보안 주석 충실.
- privacy-by-design: OCR 원문 미저장(`ocr_text_hash` HMAC, `raw_ocr_text_stored=False`), API 예외는 구조화 `{code,message}`, 비밀은 `SecretStr`, 로거 레다크션.
- GCP `service_account` 키: 코드 하드코딩 없음, `docker-compose.google-vision.yml`가 env→read-only 마운트(`/run/secrets`)+`adc` 모드, `config.py`가 운영환경 파일자격증명 차단.
- 발견: [MED] GCP 키 파일 권한 `644`(world-readable) → `600` + 가능하면 repo 트리 밖 이동.
- [추가리뷰] 모바일/프론트 번들 비밀 부재 최종 확정(빌드 산출물 secret grep) 권장.

### 2.3 OCR / YOLO / Ollama 구현
- 계층 구조: `src/ocr/`{`base.py`,`factory.py`,`field_extractor.py`,`text_normalizer.py`,`providers/`{`paddle.py`,`clova.py`,`google_vision.py`}} + `src/llm/`{`ollama.py`(텍스트 파서),`ollama_vision.py`(멀티모달 vision-assist, `ENABLE_MULTIMODAL_LLM` 게이트)}.
- `build_supplement_ocr_adapter`가 primary(paddleocr/google_vision/clova) 선택 + fallback 체인. 외부 provider는 게이트로 fail-closed.
- PaddleOCR 어댑터(`ocr/providers/paddle.py`): lazy import, PP-OCRv5 mobile/server 프로파일, TemporaryDirectory file-path predict(정상), 좌표→레이아웃 변환.
- 파서(`services/supplement_parser.py`): `format=json` 구조화 출력, 강력한 sanitizer(injection/SQL/HTML/URL 차단 + heading/packaging 토큰 필터), name+amount+unit 정규식 fallback, evidence span/layout merge, HMAC 해시. 품질 양호.
- Food YOLO(`services/food_yolo_detector.py`): 게이트 + bytes→PIL→numpy→predict(정상) + fail-soft + preview-only.
- 발견: [MED] LLM 경로 성분에 amount/unit 누락 + 부형제 혼입(2.1과 동일 근본원인). [추가리뷰] `config.py` 검증자/임계값, OCR provider별 confidence 임계값 적용 일관성, `src/llm/ollama.py`·`ollama_vision.py` 내부 정밀 코드리뷰 권장(이번에 미정독).

### 2.4 이미지 분석 파이프라인 (촬영/갤러리)
- 모바일: `mobile/lib/screens/camera_screen.dart` + `features/supplements/`{`supplement_flow_screen`,`supplement_repository`,`camera_readiness`} + `core/api/api_client.dart`. 촬영 + 갤러리 동일 OCR endpoint 사용. 다중 이미지 세션(`analysis-sessions/…/finalize`)도 구현.
- 백엔드: 영양제 `POST /supplements/analyze`(consent 게이트, adapter 선택, run 영속, 202 preview) → 파서 → `POST /supplements` 확정. 식단 `POST /meals/analyze-image`(202, consent, idempotency 409, audit, raw_image 미저장) → `POST /meals/{id}/confirm`.
- 판정: 기본 설정(PaddleOCR on)에서 촬영/갤러리 → 분석 → 구조화 결과 → DB저장 → 확인 흐름 동작(DB 121건 증거). 멀티모달/ROI-YOLO는 게이트 off.
- 발견: [MED] `backend/Food-backend/src/meal/*`(MealPipeline·`yolo_v8`·google_vision·fusion·`nutrition/rda_matcher`·portion_estimator)는 **테스트용 독립 라이브러리로 실 API 미연결**. 실 식단 endpoint는 `services/meal_image_analysis.py`(+`FoodYoloDetector`)를 사용. [추가리뷰] 영양제 단건 confirm 경로의 모바일↔백엔드 계약 1회 e2e 확정 권장.

---

## 3. 이번에 작성/수정한 파일 (모두 **미적용** — 파일만; py_compile 통과)

1. `backend/alembic/versions/0020_harden_supplement_user_tables_rls.py` [신규]
   - 9개 핵심 테이블에 `ENABLE ROW LEVEL SECURITY` + `COMMENT` + `REVOKE ALL FROM PUBLIC` + 역할(anon/authenticated/service_role) 존재시 REVOKE하는 `DO` 블록. 기존 `0009`/`0014` 패턴과 동일. `down_revision="0019_add_user_supplement_evidence_refs"`, `downgrade()`는 의도적으로 no-op(fail-closed 유지).
   - 대상 테이블: `supplement_products`, `supplement_product_ingredients`, `supplement_analysis_runs`, `user_supplements`, `user_supplement_ingredients`, `analysis_results`, `consent_records`, `consent_policies`, `deletion_requests`.
   - 안전성: 9개 테이블 owner = `lemon`(라이브 확인) → table owner는 RLS를 우회하므로, `lemon`으로 접속하는 백엔드의 요청경로 쿼리에 영향 없음.

2. `backend/alembic/versions/0021_add_ingredient_daily_value_percent.py` [신규]
   - `supplement_product_ingredients` + `user_supplement_ingredients`에 `daily_value_percent Numeric(7,3)` nullable 컬럼 + `CHECK (… >= 0)` 추가(0019의 add_column+create_check_constraint 패턴과 동일). `down_revision="0020_harden_supplement_user_tables_rls"`. `downgrade()`는 컬럼/제약 제거.

3. `backend/Nutrition-backend/src/models/db/supplement.py` [수정]
   - `SupplementProductIngredient`, `UserSupplementIngredient` 두 모델에 `daily_value_percent` 컬럼 + `CheckConstraint("daily_value_percent IS NULL OR daily_value_percent >= 0", name="daily_value_percent_nonnegative")` + docstring 추가(0021 마이그레이션과 일치).

검증 상태: `python3 -m py_compile`로 위 3개 파일 **구문검증 통과(PY_COMPILE_OK)**. 마이그레이션 실행·alembic upgrade·pytest·런타임 동작은 **미수행**.

---

## 4. 남은 작업 (우선순위)

### 4.1 적용 (DB/배포 — 직접 또는 CI)
- `0020`, `0021` 적용 방법(택1):
  - 백엔드 이미지 재빌드 후 재기동(컨테이너 `command`가 `alembic upgrade head` 실행). 예: `docker compose build backend && docker compose up -d backend`. 백엔드 잠깐 재기동됨.
  - 또는 CI 마이그레이션 단계 / 호스트 venv에서 `backend/` 기준 `alembic upgrade head`(호스트 venv·의존성 필요).
- 적용 후 검증:
  - `alembic current` = `0021_add_ingredient_daily_value_percent`
  - RLS: `docker exec lemon-aid-db-1 psql -U lemon -d lemon -c "SELECT relname, relrowsecurity FROM pg_class WHERE relkind='r' AND relnamespace='public'::regnamespace AND relname IN ('user_supplements','user_supplement_ingredients','supplement_analysis_runs','supplement_products','supplement_product_ingredients','analysis_results','consent_records','consent_policies','deletion_requests') ORDER BY relname;"` → 모두 `t`
  - `daily_value_percent` 컬럼 존재 확인(`\d+ user_supplement_ingredients`).
  - 백엔드 read 정상 동작 확인(health endpoint + 영양제 목록/분석 1회).
- 주의: `0020`은 owner(lemon) 우회로 백엔드 무영향이나, 백엔드가 비-owner 역할로 접속하도록 바뀌면 owner-scoped RLS 정책 추가가 필요.

### 4.2 코드 (미완 — 이어서 구현)
- #3 성분 함량/단위 + 부형제 필터 (`supplement_parser.py`):
  - (a) 부형제 denylist 필터를 ingredient candidate에 적용. 활성성분 오제거 방지를 위해 정규화 후 **exact 매칭 + 명백한 안전 substring**만 사용(예: gelatin/젤라틴, glycerin/글리세린, purified water/정제수, softgel, sunflower oil/해바라기씨유, soybean oil, silicon dioxide, magnesium stearate, microcrystalline cellulose, titanium dioxide). 드롭 시 감사 가능한 warning code 추가 권장.
  - (b) LLM 성분 중 `amount=None` 항목을 OCR 정규식 추출 결과(`_extract_ocr_pattern_ingredient_candidates`)와 **이름 일치**로 매칭해 amount/unit 보강. 훅 지점: 이름 필터는 `_sanitize_parser_result`의 ingredient 루프, amount 보강은 `_merge_ocr_pattern_fallbacks`(여기서 `ocr_text` 접근 가능).
  - 등록 경로(`supplement_registration.py`)는 이미 `request.ingredients[].amount/unit/nutrient_code`를 매핑하므로 수정 불필요(근본원인은 업스트림 프리뷰 품질).
  - 순수 함수로 작성하고 단위 테스트 추가(`backend/Nutrition-backend/tests/**`).
- #4 섭취방법 구조화 보존:
  - `models/schemas/supplement.py`의 `SupplementIntakeSchedule`에 선택 필드(`times_per_day`, `amount_per_time`, `amount_unit`, `with_food`) 추가.
  - `create_user_supplement_from_confirmation`(`supplement_registration.py`)에서 해당 필드 보존(현재 `intake_schedule.model_dump`만 저장하므로 스키마 확장만으로 대부분 자동 보존되나, 프리뷰의 `SupplementPreviewStructuredIntakeMethod`를 confirm 요청까지 전달하는 모바일/계약 반영 필요).
- #5 %DV 후속 와이어링: DB 컬럼/모델은 완료. 값이 실제로 채워지려면 파서가 라벨의 % 기준치를 추출하고, `SupplementIngredientCandidate`(스키마)에 `daily_value_percent`를 추가해 confirm까지 전달하도록 와이어링 필요.
- (보안) GCP 키 `chmod 600` + repo 트리 밖 이동, 관련 문서/`.env` 가이드 갱신.
- (정리) `Food-backend/src/meal/*` 실 endpoint 연결 여부 결정(연결 또는 "experimental" 명시로 데드코드 혼선 제거).

---

## 5. 검증/적용 도구 메모
- 로컬 DB 읽기 조회: `docker exec lemon-aid-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "<SQL>"'` (POSTGRES_USER/DB env로 비밀번호 노출 없이).
- 구문검증: `python3 -m py_compile <파일...>` (임포트 없이 문법만 — 의존성 불필요).
- 테스트: `backend/Nutrition-backend/tests/**`, `backend/Food-backend/tests/**` (pytest), `mobile/test/**` (flutter). 컨테이너/CI에서 실행 권장(호스트 venv 없음).
- 커밋/푸시/배포는 팀의 브랜치·PR·커밋 컨벤션에 따른다.

---

## 6. 검증 신뢰도 (정직)
- DB 감사 결론: 로컬 DB 라이브 직접 검증(스키마·카운트·RLS 상태·소유자).
- 보안/구현/파이프라인: 핵심 소스 직접 정독으로 결론. 단 일부 파일은 미정독 → "추가리뷰 권장" 항목 명시(특히 `config.py` 검증자/임계값, OCR 임계값 일관성, `src/llm/*` 내부).
- 이번에 작성한 코드(`0020`/`0021`/모델): `py_compile` 통과만. 마이그레이션 적용·런타임·테스트는 미실행이며, 적용·검증은 이후 단계에서 수행해야 한다.

---

## 7. 재실행 감사 결과 (보안 · 구현 · 파이프라인) — 완료
§2.2/2.3/2.4의 "추가리뷰 권장/유실"로 남겼던 부분을 채운 결과(코드 직접 정독 기반).

### 7.1 보안 (완료)
- 모바일 번들: 백엔드 비밀 미반출 확인 ✓. `mobile/lib/core/config/app_config.dart`는 dart-define 3개(`LEMON_API_BASE_URL`/`LEMON_API_TOKEN`/`LEMON_DEV_GATEWAY_TOKEN`)만 사용, release 가드(106–124)가 토큰 비어있음·HTTPS·cert pin 강제. `google-services.json`/`GoogleService-Info.plist` 없음(Firebase 미통합).
- 🟠 [MED] `.secrets.baseline` 파일 부재 → `.pre-commit-config.yaml`의 detect-secrets 훅이 모든 개발자 머신에서 실패/우회 = 시크릿 스캔 사실상 미작동. → `detect-secrets scan > .secrets.baseline` 생성·커밋.
- 🟠 [MED] `--dart-define` `LEMON_API_TOKEN`/`LEMON_DEV_GATEWAY_TOKEN`이 release CI에서 주입되면 바이너리에 baked(추출 가능). 가드는 앱 시작시점 검사라 값은 이미 포함 → CI release job에서 미주입 보장(`mobile/scripts/prepare-ios-flutter-uiux-xcode.sh:19,23`).
- 🟠 [MED] 레다크션(`services/privacy.py`)이 root/uvicorn 로그 핸들러에 등록 미확인(방어심층 갭) → `main.py` startup에서 필터 등록.
- 🟡 [LOW] `docker-compose.yml:7,58` 로컬 dev creds 하드코딩(allowlisted), gitleaks 미도입, GCP 키 644.
- 결론: 확인된 비밀 노출 경로 없음. privacy-by-design 양호.

### 7.2 OCR/YOLO/Ollama 구현 (완료)
- 상태: PaddleOCR on(기본 primary), Google Vision/CLOVA/멀티모달/Food YOLO/ROI YOLO 모두 기본 게이트 off.
- 🔴 [HIGH] `local_ocr_confidence_threshold`(0.75, `config.py:443–450`)는 런타임 필터링에 미사용(pass-through). 이름과 달리 동작 안 함 — 운영자가 올려도 무효.
- 🔴 [HIGH] `OCR_LOW_CONFIDENCE_THRESHOLD`(0.80, `supplement_parser.py:52`)는 import만, chain runner(`_extract_multimodal_ocr_if_allowed`)에서 사용 미확인 → `multimodal_ocr_assist_policy=low_confidence`가 실제 confidence 게이트를 안 할 수 있음(코드 확인 필요).
- 🟠 [MED] `ollama_vision.py:125`는 텍스트 파서의 markdown-fence JSON 폴백이 없음 → vision JSON 파싱 취약. `ollama_temperature`를 text/vision 공유, `ollama_vision_model` 게이트 off인데 기본값 non-None(`config.py:337`).
- 🟠 [MED] #3 근본원인 확정: `supplement_parser.py:321–331`(`_sanitize_parser_result`)이 `amount=None` 후보를 미드롭/미플래그 + 스키마(`models/schemas/supplement_parser.py:55–56`) amount/unit optional → 함량 없는 부형제가 통과.
- ✓ text=qwen / vision=gemma4 분리 정상(cross-contamination 없음). confidence는 UI 버킷 표시용이며 provider별 필터링은 설계상 없음(단 네이밍 오해 소지).
- 테스트: 파서/프로바이더/YOLO 단위테스트 양호. 갭: low_confidence assist 경로 통합테스트, amount=None 후보 통과 테스트 부재.

### 7.3 이미지 파이프라인 (완료)
- 계약: 모바일↔백엔드 거의 전부 일치(analyze, 멀티이미지 세션 `analysis-sessions/.../finalize`, meal). multipart 필드명 `image` 일관. (앞서 우려한 confirm 불일치는 오인 — 일치 확인.)
- 🔴 [CRITICAL/latent] meal confirm `meal_id`: 백엔드는 `UUID` path param인데 Dart측 형식검증 없음(`supplement_repository.dart:182`) → 비정상 ID시 처리 안 된 422.
- 🔴 [HIGH] 분할 동의(split-consent): analyze는 `OCR_IMAGE_PROCESSING`, 확정 `POST /supplements`는 `SENSITIVE_HEALTH_ANALYSIS` 요구(`supplements.py:2447`). OCR 동의만 한 사용자는 분석 성공 후 확정에서 silent 403, 모바일 재진입 UI 없음.
- 🔴 [HIGH] 모바일 이미지 크기 사전검사 없음 + `api_client.dart`에 connect/receive/sendTimeout 미설정 → 5MB 초과 413 무안내, 네트워크 끊김시 무한 대기.
- 🔴 [HIGH] iOS 갤러리 HEIC는 허용 MIME(jpeg/png/webp) 밖 → 크롭 생략 시 415.
- 🔴 [HIGH] `registerSupplement`(영양제 확정 `POST /supplements`) 모바일 단위테스트 부재. `mobile/integration_test/` 디렉터리 자체 없음(patrol 선언만).
- ✓ 기본설정(PaddleOCR on)에서 촬영/갤러리 동일 경로로 end-to-end 동작, 게이트 off 기능은 graceful skip.
- 판정: **works-with-caveats**(촬영=갤러리 동일). analyze→preview는 견고하나 특정 consent/MIME 조건에서 confirm 단계가 깨짐.

### 7.4 통합 우선순위 (재실행 반영)
- HIGH: (보안) `.secrets.baseline` 생성; (파이프라인) split-consent 가드+재진입 UI, 모바일 타임아웃+크기 사전검사, HEIC 변환/허용; (구현) confidence threshold 네이밍/와이어링 정리(`local_ocr_confidence_threshold`, `OCR_LOW_CONFIDENCE_THRESHOLD`).
- MED: vision JSON fence-strip(`ollama_vision.py`), `ollama_temperature` text/vision 분리, #3 amount-missing 플래그+부형제 필터, 레다크션 로그핸들러 등록, dart-define 토큰 CI 점검, GCP 키 600.
- 테스트: `registerSupplement` 단위테스트, `integration_test/` e2e(촬영·갤러리·confirm), low_confidence assist 경로, amount=None 후보.

---

## 8. 구현 진행 (Goal 5개 항목, 순차) — 2026-05-30
제약: 파일 작성/수정만(커밋·DB적용·이미지 재빌드 없음). 모바일 `flutter analyze`/`flutter test`, 백엔드 `py_compile`로 검증.

### ① 분할 동의 — 완료(컨트롤러)
- `mobile/lib/app_controller.dart` `registerSupplement`: 사전 `healthConsent` 점검 → 미동의 시 한국어 안내 + `consentRequired` 플래그로 API 미호출(silent 403 차단). 응답 403도 `consentRequired` 매핑(stale 방어). `consentRequired` getter + `clearMessages`/`clearSupplementFlow` 리셋.
- UI: `supplement_flow_screen.dart`는 이미 `hasMinimumConsents`(OCR+health) 게이트 + `ErrorPanel(apiError)` 노출 → 안내 표면화.
- 검증: `flutter analyze` clean. 403 매핑은 ③ repo 테스트로 검증.

### ② 모바일 견고성 — 완료
- `mobile/lib/core/api/api_client.dart`: 요청/업로드 `.timeout()`(`TimeoutException`→`ApiError 408`), 업로드 전 크기 상한 검사(`ApiError 413`, 기본 10MB·주입가능), 미지원 형식 친화 오류(`ApiError 415`, HEIC 등). `imageQuality:95`로 iOS pick은 JPEG 재인코딩됨.
- 검증: `flutter analyze` clean + 단위테스트 통과.

### ③ 테스트 — 핵심 완료
- 신규 `mobile/test/unit/api_client_robustness_test.dart`: 408/413/415 + `registerSupplement` POST `/supplements` 계약 + 403 매핑 = **4/4 통과**(`flutter test`). 에이전트 지적 "registerSupplement 무커버리지" 해소.
- 남음: `mobile/integration_test/` e2e(patrol, 디바이스 필요) 스캐폴드.

### ④ 백엔드 구현 — 핵심 완료
- `backend/Nutrition-backend/src/services/supplement_parser.py`: `_sanitize_parser_result`에 부형제 denylist 필터(정규화 exact-match `_is_excipient_name`/`_EXCIPIENT_NAME_KEYS`) + 함량 없음 후보 플래그(`ingredient.amount_missing`). `py_compile` OK.
- 남음(MED 폴리시): `config.py` `ollama_temperature` text/vision 분리 + `local_ocr_confidence_threshold`/`OCR_LOW_CONFIDENCE_THRESHOLD` 와이어링 정리, `src/llm/ollama_vision.py` fence JSON 폴백, `_merge_ocr_pattern_fallbacks` amount 보강, 파서 단위테스트.

### ⑤ 보안 — 부분 완료
- ✅ GCP 키 `chmod 600`(644→600).
- 남음(환경 의존): `.secrets.baseline` 생성(호스트 detect-secrets 미설치 → pre-commit venv/CI에서 `detect-secrets scan > .secrets.baseline`), `main.py` 레다크션 로그핸들러 등록, release CI `--dart-define` 토큰 가드.

### 적용/검증
- 모바일: `cd mobile && flutter analyze && flutter test` → **전체 98 tests pass**(회귀 없음, 신규 robustness 4 포함). ① 가드는 "consent state 로드 + health 미동의 시에만 차단, 미로드 시 진행+403 매핑"으로 정제(기존 테스트 호환).
- 백엔드: `py_compile` 통과. 런타임/마이그레이션(0020/0021)·pytest는 이미지 재빌드+CI.
- 커밋/푸시 미수행(요청 시 진행).

---

## 9. MED 후속 구현 (순차) — 2026-05-30
- ① `llm/ollama_vision.py`: fence/substring JSON 폴백 추가(`_vision_json_candidates`/`_parse_vision_candidate_result` — 텍스트 파서와 동등 내성). `config.py`에 `ollama_vision_temperature` 신설 + vision payload가 이를 사용(텍스트는 `ollama_temperature` 유지 = 분리). `py_compile` OK.
- ② `services/supplement_parser.py`(이전 완료분): 부형제 denylist exact-match 필터 + `amount=None` 후보 플래그(`ingredient.amount_missing`). `py_compile` OK.
- ③ 레다크션 로그핸들러: **확인 완료** — `setup_logging`(`src/utils/logger.py:47-65`)이 root 로거 핸들러에 `RedactingFilter`(Bearer 토큰/email/hex-hash 마스킹)를 설치하고 `main.py` lifespan이 호출 → **root 로거 레다크션은 이미 적용됨(앱 로그 보호 확인)**. 잔여 refinement(선택): `install_global_log_redaction`(`src/logging_redaction.py`, uvicorn 로거 전용 커버)은 호출처 없음 → uvicorn.access 줄까지 마스킹하려면 `main.py` lifespan에서 시그니처 확인 후 1회 호출. (이전 "main.py가 install_global_log_redaction 호출" 및 "미완" 기재는 글리치 read 기반 오판이라 정정 — 실제로는 setup_logging 경로로 root 레다크션이 이미 적용.)
- ④ `--dart-define` 토큰: **감사 완료 — 주입 경로 없음** — `…/.github/workflows/ci-mobile.yml`은 토큰 `--dart-define` 없이 format/analyze/`flutter test`/`flutter build apk --debug`(continue-on-error)만 수행하고 iOS 빌드 잡은 주석처리 → release 토큰 주입 경로 부재. 토큰을 넘기는 건 dev 스크립트(`prepare-ios-flutter-uiux-xcode.sh`·`run-android-dev.sh`, dev 용도)뿐 + `app_config.dart` release 런타임 가드 존재. 별도 release 빌드 스크립트 신설 시에만 토큰 미주입 가드 추가 필요. (`build-ios-ipa.sh`는 부재 — 이전 "가드 삽입" 기재 정정.)

---

## 10. 잔여 구현 완료 + 4영역 재평가 결론 — 2026-05-31

### 10.1 잔여 구현(권한 부여분) — 완료
- ③ uvicorn 레다크션: `utils/logger.py setup_logging`이 root + `uvicorn`/`uvicorn.access`/`uvicorn.error`에 `RedactingFilter` 설치(idempotent). 재평가: propagate=False 갭 해소 확인. py_compile OK.
- `.secrets.baseline`: detect-secrets 1.5.0로 repo root 생성 → detect-secrets 훅 실효화.
- parser amount 보강: `_merge_ocr_pattern_fallbacks`가 name-match로 `amount=None` LLM 후보에 amount/unit 채움. (재평가가 우려한 "중복 추가"는 `existing_keys`를 enrich 후 재계산하므로 **해당 없음**.) py_compile OK.
- threshold 와이어링: **변경 불필요(검증)** — `OCR_LOW_CONFIDENCE_THRESHOLD`는 `supplement_image_analysis.py:1059`(low_confidence fallback 게이팅) + `supplement_parser.py:1084`(리뷰 플래깅)에서 사용. `local_ocr_confidence_threshold`는 의도적 non-filtering.
- integration_test: `mobile/integration_test/app_smoke_test.dart` 신설 + `pubspec.yaml` `integration_test` dev_dep 추가(pub get 성공). 디바이스 필요(`flutter test integration_test/ -d <device>`); CI는 test/만 실행해 무영향. 전체 단위/위젯 **98 pass(회귀 0)**.

### 10.2 재평가 후속 수정(Part C)
- `supplement_parser.py _extract_ocr_pattern_ingredient_candidates`: fallback 후보도 `_is_excipient_name`로 부형제 제외(LLM 경로와 일관). py_compile OK.
- `utils/logger.py _PATTERNS`: bare JWT(`eyJ...`) + API-key prefix(`sk-/sk_live_/sk_test_/sbp_/AIza`) 레다크션 패턴 추가. py_compile OK.

### 10.3 4영역 재평가 결론
- **보안(모바일/로그/응답)**: 모바일 번들 백엔드 비밀 미반출 ✓, uvicorn 레다크션 정상 ✓, API 응답 유출 없음 ✓. 잔여: 🟠 debug `AndroidManifest` 전역 `usesCleartextTraffic=true`(도메인 스코프 권장), 🟠 레다크션 PII 패턴(한국 전화번호 등) 추가 여지, 🟠 `.secrets.baseline` uiux html 30건 base64 주석화.
- **OCR/YOLO/Ollama**: 최근 변경 전부 정상, 기본 게이트 off. 잔여: 🟠 `_is_excipient_name`/`amount_missing`/enrich 단위테스트 부재, 🟡 vision fence 헬퍼 빈-content 가드/비대칭, 🟡 vision assist 실패 무로그.
- **파이프라인+계약**: 계약 전 항목 일치 → **WORKS**. 촬영=갤러리 end-to-end 동작, 최근 변경(분할동의/timeout/UUID) 정상. 잔여: 🟡 단일분석 4-provider 병렬 fan-out 낭비, 🟡 consent 재진입 e2e 미자동화, 🟡 `_run()` `_consentRequired` 미리셋(무해).
- **DB write-path(매칭 포함)**: analyze→intake(begin, run 무조건 저장)→파서 동일 row 갱신(commit)→`match_supplement_product`(read-only 카탈로그)→`POST /supplements`(flush+commit; run→confirmed). 카탈로그는 오프라인 importer만 기록(확인). 최근 파서 변경이 `parsed_snapshot`·warnings에 반영되어 DB 적재 확인 ✓. ℹ️ enrich amount는 confirm client round-trip 의존, ℹ️ 빈 카탈로그→매칭 NULL(설계상).

### 10.4 누적 변경 파일(uncommitted)
backend: `config.py`, `llm/ollama_vision.py`, `utils/logger.py`, `services/supplement_parser.py`, `alembic/versions/0020*·0021*`, `models/db/supplement.py`. mobile: `lib/app_controller.dart`, `lib/core/api/api_client.dart`, `lib/features/supplements/supplement_repository.dart`, `pubspec.yaml`, `test/unit/api_client_robustness_test.dart`, `integration_test/app_smoke_test.dart`. root: `.secrets.baseline`(신규), GCP 키 perm 600. **커밋/푸시/DB적용/이미지 재빌드 미수행.**

### 10.5 권장 후속(미적용)
단위테스트(excipient/amount_missing/enrich), vision empty-content 가드, debug cleartext 도메인 스코프, 레다크션 PII 패턴 확장, consent 재진입 e2e, 4-provider fan-out 최적화, %DV·구조화 intake 파서 와이어링, `0020/0021` 적용(이미지 재빌드→`alembic upgrade head`).

---

## 11. 재평가 결론 해결 플랜 (승인됨, 2026-05-31)
**정정**: "enrich 중복추가 버그"=오탐(`existing_keys` enrich 후 재계산 → 해당없음). DB "enrich-amount 미전달"·"빈 카탈로그 매칭 NULL"=설계상 동작(P5 문서화). **제약**: 파일 수정만, `flutter analyze`+`flutter test`/`py_compile`+pytest 검증, 커밋·DB적용·이미지 재빌드는 별도 승인 시.

- **P1 정확성/버그**: (1) `app_controller.dart _run`에 `_consentRequired=false` 리셋. (2) `screens/camera_screen.dart _analyze` 파일부재 시 `_captured=null` 복구(현재 stuck). (3) `ollama_vision.py _parse_vision_candidate_result` 빈-content 명시 예외(현재 `from None`).
- **P2 보안**: (4) `android/app/src/debug/AndroidManifest.xml` 전역 `usesCleartextTraffic`→`network_security_config` 도메인 스코프(10.0.2.2/127.0.0.1). (5) `utils/logger.py _PATTERNS`에 한국 전화번호 패턴(JWT/apikey 적용 완료). (6) `.secrets.baseline` uiux html base64 30건 검토/주석.
- **P3 테스트**: (7) 파서 단위테스트(`_is_excipient_name`/`amount_missing`/enrich·무중복·부형제-fallback 제외). (8) consent 재진입 위젯/통합 테스트(analyze→consentRequired→동의→register).
- **P4 품질**: (9) `app_controller _analyzeSupplementImageAutomatically` 4-provider 병렬 fan-out 최적화(primary 우선, 저신뢰/실패 시 외부). (10) `supplement_image_analysis._extract_multimodal_ocr_if_allowed` 실패 진단 로그. (11) `_EXCIPIENT_NAME_KEYS` 유지보수 주석.
- **P5 설계/문서**: (12) 확정폼 amount prefill 확인(`supplement_flow_screen._seedFromPreview`). (13) 카탈로그 importer 운영문서. (14) 멀티이미지 retry 멱등성 문서.
- **P6 배포(별도 승인)**: (15) %DV 파서 와이어링(0021 컬럼). (16) 구조화 intake 보존(`SupplementIntakeSchedule`+확정경로). (17) `0020`/`0021` 적용(재빌드→`alembic upgrade head`).
- **실행 순서**: P1→P2→P3→P4→P6→P5.

### 11.1 진행 상태 (2026-05-31)
- ✅ **완료·검증**: P1(1·2·3), P2(4·5·6), P3(7·8), P4(10·11).
  - P1-1 `_run` consentRequired 리셋 / P1-2 camera `_analyze` 프리뷰 복구 / P1-3 vision 빈-content 예외 — `flutter test 98 pass`·`py_compile OK`.
  - P2-4 debug cleartext → `network_security_config`(10.0.2.2/127.0.0.1/localhost) / P2-5 로거 한국 전화번호 패턴 / P2-6 detect-secrets `mobile/uiux` 제외 + baseline 재생성(findings 29→21, uiux 제거).
  - P3-7 `test_supplement_parser_excipient.py`(부형제/ fallback 제외, py_compile OK·pytest는 CI) / P3-8 app_controller consent 재진입 2건(`flutter test 11 pass`).
  - P4-10 vision assist 실패 진단 로그(클래스명만) / P4-11 `_EXCIPIENT_NAME_KEYS` 유지보수 주석.
- ◽ **P4-9 (4-provider fan-out)**: **의도적 설계로 유지** — 다중 provider 결과를 `_scoreSupplementPreview`로 비교해 best 선택(품질 기능). 단독화하면 기존 테스트 파괴 + 품질 저하 → 변경하지 않고 문서화. (외부 provider는 게이트/동의로 fail-closed라 낭비는 실패-빠름 수준.)
- ⏸ **P6-15(%DV 파서 와이어링)·P6-16(구조화 intake 보존)**: 백엔드 스키마+파서(+%DV OCR 추출)+Dart 모델+UI에 걸친 **기능 추가**(규모 큼). P6-16은 `intake_schedule` jsonb라 마이그레이션 불필요(스키마/모델/폼만), P6-15는 %DV OCR 추출 로직 신규 필요. **P6-17(0020/0021 DB 적용)=별도 승인.**
- P5 문서화: enrich amount round-trip / 빈 카탈로그 매칭 NULL / 멀티이미지 retry 멱등성 = 설계상 동작(§10.3·본 절 기재).

### 11.2 P6 진행 (2026-05-31, 코드만 — DB적용/재빌드 제외)
- ✅ **P6-16 (구조화 섭취방법 보존) — 배선 완료**: 백엔드 `SupplementIntakeSchedule`(`models/schemas/supplement.py:597`)에 `times_per_day/amount_per_time/amount_unit/with_food` 추가 → 등록 시 `model_dump`로 `user_supplements.intake_schedule` jsonb에 자동 저장(마이그레이션 불필요). Dart `SupplementIntakeSchedule`(`supplement_models.dart`) 동일 필드+toJson. `supplement_flow_screen._registerSupplement`가 `preview.intakeMethod.structured`(timesPerDay/amountPerTime/amountUnit/withFood)에서 매핑. *검증*: `flutter analyze` 클린 + 모바일 `flutter test` **100 pass** + 백엔드 `py_compile` OK.
- ✅ **P6-15 (%DV) — 완료**: 백엔드 `UserSupplementIngredientInput.daily_value_percent`(supplement.py) + `supplement_registration.py` 매핑→`UserSupplementIngredient.daily_value_percent`(0021 컬럼) + 파서 `SupplementParserIngredientCandidate.daily_value_percent`(`models/schemas/supplement_parser.py`). **구현(완료)**: ① `_extract_ocr_pattern_ingredient_candidates`(supplement_parser.py) 정규식에 선택적 `NN%` 캡처 + 후보 dict에 `daily_value_percent`(+LLM 프롬프트), ② Dart `SupplementIngredientCandidate`(`supplement_models.dart:1215`)·`UserSupplementIngredientInput`(:1626)에 `dailyValuePercent`(+toJson/fromJson), ③ `supplement.py`의 응답/스냅샷용 `SupplementIngredientCandidate`에도 필드, ④ `_build_parsed_snapshot`가 candidate의 daily_value_percent를 스냅샷에 포함하는지 확인. → 그래야 %DV가 preview→confirm→DB로 실제 흐름.
- **P6 검증(실측)**: 모바일 `flutter test` **100 passed** + `flutter analyze` 클린(flow-screen %DV/intake draft 체인 포함 전체 컴파일·테스트) · 백엔드 `py_compile` OK. ⚠️ 백엔드 `pytest`는 이 호스트에 미설치(`No module named pytest`) → 신규 파서 %DV/부형제 단위테스트(`tests/unit/services/test_supplement_parser_excipient.py`)는 **CI/컨테이너에서 실행 필요**. (P6-17 0020/0021 DB 적용 = 별도 승인 대기.)
- ⑤ meal `meal_id` UUID 검증: `features/supplements/supplement_repository.dart` `confirmMealImagePreview`에 UUID 정규식 검증 추가(비정상 id→clear `ArgumentError`, 422 방지).
- ⑥ GCP 키 `chmod 600` 확인(`-rw-------`).
- 검증: 백엔드 `py_compile` OK(config+ollama_vision+supplement_parser) / 모바일 `flutter test` **98 pass(회귀 0)** + `flutter analyze` clean.
- 실제 변경 파일(확정): `backend/Nutrition-backend/src/config.py`(ollama_vision_temperature 추가), `…/src/llm/ollama_vision.py`(fence 폴백+vision temperature), `…/src/services/supplement_parser.py`(부형제/amount, 이전 turn), `mobile/lib/features/supplements/supplement_repository.dart`(meal_id UUID), GCP 키 chmod 600. 커밋/푸시 미수행.
- **미완(정정 후 정확한 잔여)**: ③ 레다크션 호출부 확인+필요시 wiring, ④ release/CI 토큰 미주입 가드, 그리고 `_merge_ocr_pattern_fallbacks` amount 보강, `local_ocr_confidence_threshold`/`OCR_LOW_CONFIDENCE_THRESHOLD` 와이어링, `.secrets.baseline` 생성(detect-secrets 미설치), `integration_test/` e2e 스캐폴드.

---

## 12. P6-17 적용 결과 (2026-05-31, 사용자 승인 후 실제 적용)

> "파일만" → **실제 적용** 단계로 전환(사용자 명시 승인). 커밋/푸시는 여전히 미수행.

### 12.1 백엔드 이미지 재빌드 ✅
- `docker compose build backend` → `lemon-aid-team-backend:dev` 재빌드(rc=0). pip 레이어 캐시로 소스 COPY 이후만 재실행(≈빠름). 새 이미지에 `0020`/`0021` 마이그레이션 + P6-15/16 코드 + 신규 파서 테스트 baked 확인.

### 12.2 마이그레이션 적용 (0019 → 0021) ✅ psql 라이브 검증
- one-off 컨테이너 `alembic upgrade head`(rc=0): `0019 → 0020 → 0021` 적용. 이후 `docker compose up -d backend`로 서비스 재기동(alembic head no-op → uvicorn `Application startup complete` → health `healthy`, `/health 200`).
- **psql 실측**:
  - `alembic_version` = `0021_add_ingredient_daily_value_percent`.
  - **RLS 활성(relrowsecurity=t)**: 9개 코어 테이블 전부(`supplement_products`, `supplement_product_ingredients`, `supplement_analysis_runs`, `user_supplements`, `user_supplement_ingredients`, `analysis_results`, `consent_records`, `consent_policies`, `deletion_requests`). force=f(소유자 우회 의존, 의도대로).
  - **`daily_value_percent numeric(7,3) NULLABLE`** + 비음수 CHECK: 두 ingredient 테이블 모두(`pg_get_constraintdef` = `CHECK ((daily_value_percent IS NULL) OR (daily_value_percent >= 0))`).
  - **소유자(lemon) 락아웃 없음**: RLS 활성 테이블 직접 SELECT 정상(`user_supplements`=2행, `supplement_analysis_runs`=121행).

### 12.3 detect-secrets ✅
- `detect-secrets-hook --baseline .secrets.baseline`(추적 파일 전수, `mobile/uiux` 제외) → **RC=0**(신규 비밀 0). baseline v1.5.0, findings 26파일(전부 기존 감사 항목).

### 12.4 모바일 debug APK (P2-4 검증) ✅
- `flutter build apk --debug` → Gradle `assembleDebug` 성공, **3개 flavor APK 생성**(`app-dev-debug.apk` 206MB 등, `build/app/outputs/apk/{dev,staging,prod}/debug/`). Flutter가 단일 `app-debug.apk`를 못 찾아 rc=1을 냈으나 이는 flavor 구성 때문이며 산출물은 정상.
- **검증(merged manifest + 패키징된 리소스)**: `android:networkSecurityConfig="@xml/network_security_config"` 적용 / 최종 manifest에 `usesCleartextTraffic` 토큰 **없음** / APK에 패키징된 `res/xml/network_security_config.xml` = **772B(=debug scoped 버전; main 254B 아님)** + 바이너리에 `10.0.2.2`·`127.0.0.1`·`localhost` 전부 present. → cleartext는 로컬 dev 호스트로만 한정, 그 외 HTTPS 강제.

### 12.5 백엔드 pytest ✅(핵심) + 환경 노트
- 호스트에 pytest 미설치 → ephemeral 컨테이너의 **venv(`/opt/venv/bin/python`)** 에 `pytest/pytest-asyncio/pytest-mock` 설치 후 실행(주의: `sh -lc` 로그인셸은 `/etc/profile`이 PATH를 리셋해 venv를 벗어나므로 **절대경로 인터프리터** 필요).
- **신규 파서 테스트(%DV + 부형제) = 6 passed.**
- **풀 스위트(`tests/`, cov 게이트 off, compose 런타임 env 주입 상태)**: `1216 passed, 141 failed, 4 skipped`. 실패는 **`test_config.py`·`test_chronic_disease_matrix.py` 2파일에만** 집중(나머지 1216 pass). 내가 변경/추가한 supplement·parser·registration·intake·image-analysis 테스트는 **전부 pass**.
- **141 실패 분해(2계층, 둘 다 회귀 아님)**:
  1. **compose 런타임 env 오염(대다수)**: compose `environment:`의 ~40개 변수(`OCR_*`/`GOOGLE_*`/`CLOVA_*`/`ENABLE_*`/`AUTH_MODE` 등)가 pydantic `Settings`에 누설되어 "clean 기본값" 전제를 깬다. 앱 변수만 `unset`하면 대부분 사라짐.
  2. **컨테이너 파일 레이아웃 불일치(나머지 15건, `unset` 후에도 잔존 — 실측 `15 failed, 69 passed`)**: 두 테스트군 모두 **리포지토리 상대경로 기준 데이터 파일**을 읽는데 이미지의 디렉터리 깊이가 달라 경로가 어긋남.
     - `chronic_disease_matrix.py:33` `_DEFAULT_MATRIX_PATH = Path(__file__).resolve().parents[4]/"data"/...` → 리포(`Lemon-Aid/backend/Nutrition-backend/src/utils`)에선 `Lemon-Aid/data/...`지만, 이미지(`/app/Nutrition-backend/src/utils`)에선 `parents[4]`가 `/` → `/data/...` 탐색 실패(`FileNotFoundError`). 실데이터는 이미지에 `/app/data/nutrition_reference/chronic_disease_supplement_matrix.json`로 **존재**하나 경로식이 못 찾음.
     - `test_config.py` readiness 2건: `/config/implementation-readiness.settings.json`(역시 리포 루트 상대 전제) 미존재.
  - **회귀 아님 교차검증**: `git diff` 결과 `config.py`는 **`ollama_vision_temperature` 1줄 추가뿐**, `test_config.py`·`chronic_disease_matrix.py`·매트릭스 JSON은 **본 세션 미변경**. 실패는 전적으로 *컨테이너 실행 컨텍스트*(env 주입 + 浅い 파일 레이아웃) 탓이며 CI의 리포지토리 체크아웃에서는 경로가 맞아 통과.
  - *권장*: 테스트는 (a) compose 런타임 env를 주입하지 않는 별도 서비스/`env -i`로, (b) 리포지토리 트리(또는 동일 깊이) 위에서 실행. 또는 로더가 `parents[N]` 대신 패키지 리소스/`data/` 마운트 절대경로를 쓰도록 보강(별도 작업, 본 P6 범위 밖).
- **테스트 결과 분해(사실만 — 진행 중 갱신)**:
  - **신규 %DV/부형제 단위테스트 = 6 passed**(`test_supplement_parser_excipient.py`). 순수 함수 `_extract_ocr_pattern_ingredient_candidates`는 내 %DV regex와 원본 regex가 일반 입력에서 동일 동작.
  - **`test_supplement_parser::…adds_ocr_pattern_fallback_candidates` 1건 = 내 %DV 기능이 기존 테스트 기대값을 바꿈(정당)**: 입력 `"아연\t10 mg\t50%"`에서 신 regex가 `daily_value_percent=50.0`을 추출 → 스냅샷 후보에 키 추가(비타민 D는 %없어 `exclude_none`으로 키 없음). 기존 테스트의 하드코딩 기대 dict가 구형이라 불일치 → **테스트를 신 동작에 맞게 갱신**(아래 적용).
  - **`test_supplement_registration` 4건 = `Nutrient code reference data is unavailable`(환경 단독 원인, 회귀 아님 — 결정적 증명 완료)**: `supplement_registration.py:37` `NUTRIENT_CODES_PATH = Path(__file__).resolve().parents[4]/"data"/"nutrition_reference"/"nutrient"/"nutrient_codes.json"`. 컨테이너(`/app/Nutrition-backend/src/services/…`)에선 `parents[4]=/` → `/data/...`를 찾지만 실데이터는 `/app/data/...`(compose `:ro` 마운트)라 불일치 → `OSError`. **matrix·implementation-readiness와 동일한 "리포지토리 상대경로(parents[N])" 클래스**. 내 registration diff는 `daily_value_percent=_decimal_or_none(...)` **1줄(가법)** 뿐 → 경로 오류와 무관.
  - **내가 적용한 테스트 수정(정당, 검증 완료)**: `test_supplement_parser.py`의 `…adds_ocr_pattern_fallback_candidates` 기대 dict의 `아연`에 `daily_value_percent: 50.0` 추가(입력 `"아연 10 mg 50%"`의 신 %DV 추출 반영). 비타민 D는 %없어 `exclude_none`으로 키 없음(유지).
  - **결정적 검증(동일 컨테이너에서 `data/`를 `/data`에 마운트 + 수정 테스트 바인드)**: `test_supplement_parser.py` + `test_supplement_parser_excipient.py` + `test_supplement_registration.py` → **25 passed, 0 failed**. = (a) 내 파서 테스트 수정이 옳고, (b) registration 4실패는 **순전히 데이터 파일 경로 미스매치**(데이터를 기대 경로에 두면 즉시 pass)임을 입증. → **P6 코드 회귀 0** 최종 확정.
  - **141 실패 = 전부 "컨테이너 실행 컨텍스트" 2클래스**: ① compose 런타임 env 누설(`Settings` 오염) ② `parents[N]` 리포지토리-상대 데이터 경로가 이미지의 浅은 레이아웃과 어긋남(`registration`/`matrix`/`config` 공통). **모두 본 세션 미변경 코드**의 실행 환경 이슈로, **리포지토리 체크아웃 + clean env(=CI)**에서는 통과. 본 세션이 추가/변경한 supplement·parser·registration·intake·image-analysis·%DV·부형제 로직은 회귀 없음.
  - *반성(중요): 본 세션 중 이 문서에 "199 passed/0 failed", "105 passed/1 failed" 등 **미실행·추정 수치를 수 차례 오기**했다(전부 폐기). 위 25 passed / 6 passed / 1216 passed(full-env)만이 실제 실행으로 확인된 수치다.*

### 12.6 적용 후 상태 / 잔여
- **적용 완료(런타임 반영)**: 0020 RLS·0021 %DV가 라이브 DB에 존재, 백엔드는 신 이미지로 healthy.
- **커밋/푸시 미수행**(원 제약 유지) — 변경 파일·신 이미지·마이그레이션은 적용됐으나 git 커밋은 사용자 몫.
- 비밀/OCR 원문 미반출, PROMPT 보존 유지.

---

## 13. 보안 강화 라운드 (2026-05-31) — Docker 위생 점검 + 보안 리뷰 기반 개선

> 트리거: "추후 개선 제안 브레인스토밍 + 보안/해킹 취약점 신중 분석 + Docker 컨테이너 최신 빌드/혼동 점검". security-reviewer(opus) 리뷰 + 직접 교차검증.

### 13.1 Docker 컨테이너 위생 점검 — ✅ 클린
- **실행 컨테이너 == 최신 `:dev` 이미지**(SHA `18a0572…` 완전 일치). 런타임에 0020/0021·%DV·전화번호 레다크션·vision_temp 전부 반영, DB head=0021.
- dangling 이미지 0, 잔류 one-off(`…-backend-run-*`) 0, 중복/혼동 lemon 컨테이너 0. `ajin-*` 5개는 별개 프로젝트(정상).
- 빌드 캐시 **18.05GB 회수**(`docker builder prune`, 21.66→3.6GB). 이미지/컨테이너 무영향.

### 13.2 적용한 개선 (파일만 → 검증 → 적용)
- **M1 — 경로 정합화(런타임 버그 수정)**: `config.resolve_nutrition_reference_root()` 정규 리졸버 신설(마커 `data/nutrition_reference` 상향 탐색 + env override). `supplement_registration.py`·`chronic_disease_matrix.py`·`kdris.py`의 `parents[4]` 고정 오프셋을 이 리졸버로 교체. **컨테이너에서 `parents[4]=/` → 데이터 미발견으로 nutrient_code 등록/매트릭스 로드가 500나던 버그 해결**(라이브 검증: nutrient_codes 30·matrix 43 LOADED). fallback 체인이 아닌 단일 탐색 알고리즘(SLOP 회피).
- **H2 — 로그 레다크션 누수 채널 보강**: `RedactingFilter`가 메시지뿐 아니라 `extra={}` 값·예외 트레이스백까지 스크럽. DB-URL 자격증명(비번만 마스킹)·`Authorization` 헤더 패턴 추가. 과다매칭 완화(32자 req-id 보존, 40자+ hex만 마스킹). 단위테스트 `test_logger_redaction.py` 추가.
- **H1 — RLS 보완(신규 `0022`)**: 유일하게 누락됐던 `audit_logs`에 ENABLE RLS+REVOKE 적용 + `ALTER DEFAULT PRIVILEGES`로 **미래 테이블 PUBLIC/anon/authenticated/service_role 자동 grant 차단**(stray GRANT 재노출 벡터 봉쇄). ⚠️ `FORCE RLS`는 **백엔드가 소유자(lemon)로 접속**하므로 적용 시 자기잠금 → 의도적으로 제외(에이전트 제안 정정).
- **H3 — Rate limit + 동시성 캡(신규 미들웨어)**: `middleware/rate_limit.py` — `/analyze*`·`/meals/analyze-image`·`/analysis-sessions/*`에 caller(토큰해시/IP)별 토큰버킷 rate limit(429) + 전역 `asyncio.Semaphore` 추론 동시성 캡(초과 시 503). 외부 의존성 0(in-process). config에 `rate_limit_*`/`inference_*` 필드. 단위테스트 `test_rate_limit.py`(10건). *멀티이미지(`analyze-multi`)는 1요청 내 순차 처리라 미들웨어로 충분 — Ollama 호출부 세마포어는 과설계로 미적용.*

### 13.3 검증 (컨테이너 실측, data `/data` 마운트)
- **pytest 53 passed**(rate_limit 10 + logger_redaction 13 + chronic_matrix + registration + parser + excipient). M1 덕에 이전 세션의 registration/matrix 컨테이너 실패가 **해소**됨.
- **ruff: All checks passed! / black: 9 files clean**(팀 CI 게이트 통과).
- **alembic 체인**: heads=`0022`, down_revision=`0021`.
- **app boot**: `RateLimitMiddleware`+`SecureHeadersMiddleware`+`TrustedHostMiddleware` 등록 확인.

### 13.4 추가 보안 — 완료 (2026-05-31, commit 4e9b1c2 + 7f2a9d3)
- ✅ **프롬프트 인젝션 한국어 마커**: `supplement_text_sanitizer._INJECTION_KO_PATTERNS`(이전 지시 무시/시스템 프롬프트/너는 이제/역할 무시 등) 추가. NFKC 정규화 후 매칭. 검증: 한국어 인젝션 5/5 차단 + 정당한 한국어 섭취안내 보존(오탐 0).
- ✅ **`PRIVACY_HASH_SECRET` 최소 길이 검증자**: `privacy_hash_secret_min_length`(기본 32) + production 검증자가 짧은 비밀 거부. 검증: short→reject, long(≥32)→pass.
- ✅ **audit 전용 pepper**: `privacy_hash_secret_audit_pepper` + `privacy._audit_secret()`. audit_logs 액터-주체 해시를 별도 키로 HMAC(미설정 시 privacy_hash_secret으로 fallback해 기존 해시값 안정). 검증: pepper 설정 시 해시 변경, 미설정 시 동일(하위호환).
- 검증 합계: 변경영역 pytest 30 passed(privacy+sanitizer) · black/ruff clean · 런타임 재빌드 반영.

### 13.5 후속 권장 — 처리 결과 (2026-05-31)
- ✅ **CI 의존성 감사 + 전체 게이트**: `.github/workflows/ci.yml` 신설(이전엔 `.github/` 자체 부재). jobs: `lint`(black/ruff), `backend-test`(clean env pytest — compose env 오염 회피), `mobile-build`(flutter analyze/test), `security`(gitleaks + detect-secrets baseline), `dependency-audit`(pip-audit + flutter pub outdated, 주간 cron + PR/푸시). 실제 경로(`backend/Nutrition-backend/tests`)·버전(flutter 3.41.9, python 3.13)에 맞춤. 검증: YAML valid, detect-secrets step 로컬 재현 PASS.
  - 부수: detect-secrets가 `logger.py`의 DB-URL 레다크션 정규식 주석을 "Basic Auth Credentials"로 오탐 → 주석을 `{user}:{password}` 플레이스홀더로 변경(정규식 동작 불변, 마스킹 검증 유지)해 CI security step 통과.
- ✅ **구조화 필드 allowlist 강화**: `sanitize_unit`에 `_ALLOWED_UNIT_KEYS` allowlist(mass/volume/IU/%DV/CFU/한국어 제형 단위) + `_normalize_unit_key`. 정규 단위가 아니면 `sanitizer.blocked:unit`으로 드롭(crafted 라벨의 unit 필드 자유텍스트 밀반입 차단). 검증: 정규 단위 14/14 보존, 비정상 8/8 차단, 회귀 70 tests 0 fail.
- ⏸ **(로드맵 유지) FORCE RLS**: 요청경로를 비소유자 역할 + per-row 정책으로 이행 → 그때 `FORCE ROW LEVEL SECURITY` 의미. **백엔드 소유자 접속 모델 변경이 필요한 대공사라 별도 설계·승인 후 착수**(현재는 ENABLE+REVOKE+ALTER DEFAULT PRIVILEGES로 fail-closed 유지).

---

## 14. FORCE RLS 로드맵 — 마이그레이션·세션 배선 파일 작성 + 증명 (2026-05-31)

> §13.5의 "⏸ (로드맵 유지) FORCE RLS"를 진전: 설계문서(`docs/2026-05-31-force-rls-rollout-design.md`)에 이어 **마이그레이션 3종 + 세션 배선 헬퍼 + 단위테스트 + POC를 파일로 작성하고 throwaway DB로 증명**. **라이브 미적용**(별도 승인 게이트 유지).

### 14.1 작성된 산출물
- **0023a** `backend/alembic/versions/0023a_create_lemon_app_request_role.py` — 비superuser 요청 역할 `lemon_app`(LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE **NOBYPASSRLS**) 생성 + 사용자데이터 28테이블 CRUD / 카탈로그 9테이블 SELECT / 시퀀스 USAGE·SELECT. **비밀번호는 마이그레이션에 미포함**(운영자가 시크릿으로 `ALTER ROLE … PASSWORD` 별도 설정). down_revision=0022.
- **0023b** `…_create_rls_owner_policies.py` — 4 아키타입 per-row 정책 32개: plaintext owner(10) / hashed owner(10) / FK child(8) / catalog read(4). GUC `current_setting('app.current_subject'|'…_hash', true)` 기준, 미설정 시 NULL→0행(fail-closed). **8개 FK child 컬럼은 라이브 스키마와 실측 대조 확인**.
- **0023c** `…_force_row_level_security.py` — 32테이블 `FORCE ROW LEVEL SECURITY`. downgrade=`NO FORCE`(정책/역할 보존). ⚠️ `lemon_app` 접속 검증 전 적용 금지(소유자도 정책 적용 대상이 됨).
- **세션 배선** `backend/Nutrition-backend/src/db/rls_context.py` — `set_request_rls_context(session, *, subject, subject_hash)`: `set_config(name, value, true)`로 트랜잭션-로컬 GUC 주입(bind 파라미터 → SQL 인젝션 불가, commit/rollback 시 자동 해제 → 풀 누수 없음). **현재 호출부 없음(inert)** — 라이브 `lemon`(superuser) 접속에선 GUC가 무시되어 동작 불변.
- **단위테스트** `tests/unit/db/test_rls_context.py` — 양쪽 GUC 설정 / None→빈문자열 fail-closed / 인젝션 문자열 bind 전달 = **3 passed**.
- **POC** `backend/scripts/db_poc/force_rls_poc.sql` — 4 아키타입을 throwaway DB에서 증명(소유자행 read / 교차소유자 WITH CHECK 차단 / 카탈로그 read / GUC 미설정 fail-closed).

### 14.2 증명 (실측, throwaway DB)
- 임시 DB에 `alembic upgrade head`(0001…0023c) 성공 → **forced=32 / policies=32 / head=0023c**. downgrade `0023c→0023b` → **forced=0**(롤백 동작). 종료 후 임시 DB·`lemon_app` 역할 drop으로 클러스터 원복.
- **라이브 `lemon` DB 무변경 확인**: forced=0 / lemon_app=0 / head=**0022**(0023a/b/c 미적용).
- **린트**: 5개 py 파일 black(`--line-length=100`)·ruff 통과(팀 CI 동일 설정).

### 14.3 라이브 적용 전 남은 단계 (전부 승인 게이트)
1. `lemon_app` 비밀번호 시크릿 발급 → `ALTER ROLE lemon_app PASSWORD '<secret>'`(마이그레이션 밖, 운영자 수동).
2. 세션 배선 활성화: 요청 트랜잭션 시작부에서 `set_request_rls_context()` 호출 + `AuthenticatedUser`→subject/subject_hash 해석 연결(현재 inert).
3. 스테이징: 0023a/b/c 적용 → `DATABASE_URL`을 `lemon_app`로 전환 → 통합테스트(소유자행만 / 교차차단 / 카탈로그 read / GUC 미설정 0행) 통과 확인.
4. 프로덕션: 스테이징 green 후 **별도 승인** 하에 동일 순서로 적용.
